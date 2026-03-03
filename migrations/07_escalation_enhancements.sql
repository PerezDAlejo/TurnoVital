-- Migration 07: Enhanced escalation system with comprehensive tracking
-- Adds fields for better escalation management, status tracking, and integration

-- Add new columns to escalaciones_handoff table
ALTER TABLE escalaciones_handoff
ADD COLUMN IF NOT EXISTS priority text DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
ADD COLUMN IF NOT EXISTS escalation_type text DEFAULT 'manual' CHECK (escalation_type IN ('auto', 'manual', 'urgent')),
ADD COLUMN IF NOT EXISTS patient_data jsonb,
ADD COLUMN IF NOT EXISTS medical_info jsonb,
ADD COLUMN IF NOT EXISTS assigned_at timestamptz,
ADD COLUMN IF NOT EXISTS resolved_at timestamptz,
ADD COLUMN IF NOT EXISTS resolution_notes text,
ADD COLUMN IF NOT EXISTS resolution_type text CHECK (resolution_type IN ('completed', 'transferred', 'cancelled', 'timeout')),
ADD COLUMN IF NOT EXISTS response_time_minutes integer,
ADD COLUMN IF NOT EXISTS total_interactions integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_patient_message_at timestamptz,
ADD COLUMN IF NOT EXISTS last_secretary_message_at timestamptz,
ADD COLUMN IF NOT EXISTS tags text[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}';

-- Add new columns to secretarias table
ALTER TABLE secretarias
ADD COLUMN IF NOT EXISTS skills text[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS specialties text[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS availability_status text DEFAULT 'available' CHECK (availability_status IN ('available', 'busy', 'offline')),
ADD COLUMN IF NOT EXISTS performance_score decimal(3,2) DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS total_cases_handled integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS avg_response_time_minutes decimal(5,2),
ADD COLUMN IF NOT EXISTS last_activity_at timestamptz DEFAULT now(),
ADD COLUMN IF NOT EXISTS notification_preferences jsonb DEFAULT '{"urgent_cases": true, "queue_updates": true, "system_alerts": false}';

-- Create escalation_events table for detailed tracking
CREATE TABLE IF NOT EXISTS escalation_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id text NOT NULL REFERENCES escalaciones_handoff(case_id) ON DELETE CASCADE,
    event_type text NOT NULL CHECK (event_type IN ('created', 'queued', 'assigned', 'patient_message', 'secretary_message', 'status_update', 'resolved', 'transferred', 'timeout', 'cancelled')),
    event_data jsonb DEFAULT '{}',
    created_by text, -- phone number or 'system'
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Create secretary_performance table for analytics
CREATE TABLE IF NOT EXISTS secretary_performance (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    secretary_phone text NOT NULL REFERENCES secretarias(phone) ON DELETE CASCADE,
    period_start date NOT NULL,
    period_end date NOT NULL,
    cases_assigned integer DEFAULT 0,
    cases_completed integer DEFAULT 0,
    cases_transferred integer DEFAULT 0,
    avg_response_time_minutes decimal(5,2),
    avg_resolution_time_hours decimal(5,2),
    satisfaction_score decimal(3,2),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(secretary_phone, period_start)
);

-- Create escalation_queue table for advanced queue management
CREATE TABLE IF NOT EXISTS escalation_queue (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id text NOT NULL REFERENCES escalaciones_handoff(case_id) ON DELETE CASCADE,
    position integer NOT NULL,
    priority_score decimal(5,2) DEFAULT 0,
    estimated_wait_minutes integer,
    entered_queue_at timestamptz NOT NULL DEFAULT now(),
    last_updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(case_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_escalation_events_case_id ON escalation_events(case_id, created_at);
CREATE INDEX IF NOT EXISTS idx_escalation_events_type ON escalation_events(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_secretary_performance_period ON secretary_performance(secretary_phone, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_escalation_queue_priority ON escalation_queue(priority_score DESC, entered_queue_at ASC);
CREATE INDEX IF NOT EXISTS idx_escalaciones_priority ON escalaciones_handoff(priority, estado, created_at);
CREATE INDEX IF NOT EXISTS idx_secretarias_availability ON secretarias(availability_status, assigned, capacity);

-- Function to update secretary performance metrics
CREATE OR REPLACE FUNCTION update_secretary_performance()
RETURNS TRIGGER AS $$
BEGIN
    -- Update last activity timestamp
    UPDATE secretarias
    SET last_activity_at = now()
    WHERE phone = COALESCE(NEW.assigned_to, OLD.assigned_to);

    -- Update performance metrics when case is resolved
    IF (TG_OP = 'UPDATE' AND OLD.estado != 'resolved' AND NEW.estado = 'resolved') THEN
        -- Calculate response time if assigned_at and resolved_at exist
        IF NEW.assigned_at IS NOT NULL AND NEW.resolved_at IS NOT NULL THEN
            UPDATE secretarias
            SET total_cases_handled = total_cases_handled + 1,
                avg_response_time_minutes = COALESCE(avg_response_time_minutes, 0) * 0.9 + EXTRACT(EPOCH FROM (NEW.resolved_at - NEW.assigned_at))/60 * 0.1
            WHERE phone = NEW.assigned_to;
        END IF;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Function to manage queue positions
CREATE OR REPLACE FUNCTION update_queue_positions()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Assign position based on priority
        UPDATE escalation_queue
        SET position = (
            SELECT COUNT(*) + 1
            FROM escalation_queue eq2
            WHERE eq2.priority_score > NEW.priority_score
               OR (eq2.priority_score = NEW.priority_score AND eq2.entered_queue_at < NEW.entered_queue_at)
        )
        WHERE id = NEW.id;
    ELSIF TG_OP = 'DELETE' THEN
        -- Reorder remaining queue items
        UPDATE escalation_queue
        SET position = sub.new_position
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (ORDER BY priority_score DESC, entered_queue_at ASC) as new_position
            FROM escalation_queue
        ) sub
        WHERE escalation_queue.id = sub.id;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Triggers
DROP TRIGGER IF EXISTS trg_escalation_performance ON escalaciones_handoff;
CREATE TRIGGER trg_escalation_performance
    AFTER INSERT OR UPDATE ON escalaciones_handoff
    FOR EACH ROW EXECUTE FUNCTION update_secretary_performance();

DROP TRIGGER IF EXISTS trg_queue_positions ON escalation_queue;
CREATE TRIGGER trg_queue_positions
    AFTER INSERT OR DELETE ON escalation_queue
    FOR EACH ROW EXECUTE FUNCTION update_queue_positions();

-- Function to log escalation events automatically
CREATE OR REPLACE FUNCTION log_escalation_event()
RETURNS TRIGGER AS $$
DECLARE
    event_type text;
    event_data jsonb := '{}';
BEGIN
    -- Determine event type based on operation and state changes
    IF TG_OP = 'INSERT' THEN
        event_type := 'created';
        event_data := jsonb_build_object('initial_state', NEW.estado);
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.estado != NEW.estado THEN
            CASE NEW.estado
                WHEN 'queued' THEN event_type := 'queued';
                WHEN 'assigned' THEN
                    event_type := 'assigned';
                    event_data := jsonb_build_object('assigned_to', NEW.assigned_to, 'assigned_at', NEW.assigned_at);
                WHEN 'resolved' THEN
                    event_type := 'resolved';
                    event_data := jsonb_build_object('resolution_type', NEW.resolution_type, 'resolved_at', NEW.resolved_at);
                ELSE event_type := 'status_update';
            END CASE;
        ELSE
            -- No state change, skip logging
            RETURN COALESCE(NEW, OLD);
        END IF;
    END IF;

    -- Insert event log
    INSERT INTO escalation_events (case_id, event_type, event_data, created_by)
    VALUES (COALESCE(NEW.case_id, OLD.case_id), event_type, event_data, 'system');

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_log_escalation_events ON escalaciones_handoff;
CREATE TRIGGER trg_log_escalation_events
    AFTER INSERT OR UPDATE ON escalaciones_handoff
    FOR EACH ROW EXECUTE FUNCTION log_escalation_event();