-- Migration 04: Handoff persistence (secretarias y escalaciones)
-- Idempotente y compatible con ejecución repetida en Supabase / Postgres

CREATE TABLE IF NOT EXISTS secretarias (
  phone text PRIMARY KEY,
  display_name text,
  tenant_key text NOT NULL,
  capacity integer NOT NULL DEFAULT 1,
  assigned integer NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS escalaciones_handoff (
  case_id text PRIMARY KEY,
  telefono_usuario text NOT NULL,
  motivo text,
  tenant_key text NOT NULL,
  estado text NOT NULL, -- open|queued|claimed|resolved|released
  assigned_to text NULL REFERENCES secretarias(phone) ON UPDATE CASCADE ON DELETE SET NULL,
  historial jsonb,
  queued_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_escalaciones_tenant_estado ON escalaciones_handoff(tenant_key, estado, created_at);
CREATE INDEX IF NOT EXISTS idx_escalaciones_queue ON escalaciones_handoff(tenant_key, estado, queued_at);

-- Funciones (se crean o reemplazan siempre; son idempotentes)
CREATE OR REPLACE FUNCTION set_updated_at_secretarias()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION set_updated_at_escalaciones()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

-- Triggers (crear sólo si no existen)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_secretarias_updated_at') THEN
    CREATE TRIGGER trg_secretarias_updated_at
    BEFORE UPDATE ON secretarias
    FOR EACH ROW EXECUTE FUNCTION set_updated_at_secretarias();
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_escalaciones_updated_at') THEN
    CREATE TRIGGER trg_escalaciones_updated_at
    BEFORE UPDATE ON escalaciones_handoff
    FOR EACH ROW EXECUTE FUNCTION set_updated_at_escalaciones();
  END IF;
END $$;
