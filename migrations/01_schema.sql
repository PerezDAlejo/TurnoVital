-- Esquema ampliado para soporte de memoria conversacional, auditoría y citas enriquecidas
-- Ejecutar en Supabase / Postgres (verificar extensión pgcrypto o uuid-ossp si se requiere)
-- Ajuste: se crea la tabla 'pacientes' si no existía para evitar error 42P01 en entornos limpios.

-- Extensión para UUID (en Supabase normalmente ya está, pero idempotente)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Tabla base de pacientes (si ya existía, se conserva; si no, se crea con columnas principales)
CREATE TABLE IF NOT EXISTS pacientes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombres text,
  apellidos text,
  documento text UNIQUE,
  telefono text,
  email text,
  preferencia_contacto text,             -- agregado directamente (evita ALTER posterior si tabla es nueva)
  tipo_paciente text,                   -- 'primera_vez' | 'control'
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Pacientes (ampliar si ya existe)
ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS preferencia_contacto text;
ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS tipo_paciente text; -- 'primera_vez' | 'control'
ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Nueva tabla citas_enriquecida (temporal mientras se migra desde 'citas')
CREATE TABLE IF NOT EXISTS citas_enriquecida (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paciente_id uuid REFERENCES pacientes(id) ON DELETE CASCADE,
  especialista_id text NOT NULL,
  tipo_cita text NOT NULL,
  estado text NOT NULL DEFAULT 'scheduled',
  fuente text NOT NULL DEFAULT 'whatsapp',
  start_at timestamptz NOT NULL,
  end_at timestamptz NOT NULL,
  duracion_min int NOT NULL,
  notas text,
  cancelled_at timestamptz,
  cancellation_reason text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_citas_enriq_paciente ON citas_enriquecida(paciente_id);
CREATE INDEX IF NOT EXISTS idx_citas_enriq_especialista ON citas_enriquecida(especialista_id, start_at);
CREATE INDEX IF NOT EXISTS idx_citas_enriq_estado ON citas_enriquecida(estado);

-- Historico de cambios de cita
CREATE TABLE IF NOT EXISTS citas_historial (
  id bigserial PRIMARY KEY,
  cita_id uuid NOT NULL,
  evento text NOT NULL, -- created | updated | cancelled
  snapshot jsonb,
  timestamp timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_citas_historial_cita ON citas_historial(cita_id);

-- Conversaciones
CREATE TABLE IF NOT EXISTS conversaciones (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paciente_id uuid REFERENCES pacientes(id),
  canal text NOT NULL DEFAULT 'whatsapp',
  estado text NOT NULL DEFAULT 'abierta',
  started_at timestamptz DEFAULT now(),
  last_message_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conversaciones_paciente ON conversaciones(paciente_id);

-- Mensajes
CREATE TABLE IF NOT EXISTS mensajes_conversacion (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversacion_id uuid REFERENCES conversaciones(id) ON DELETE CASCADE,
  rol text NOT NULL, -- usuario | bot
  texto text NOT NULL,
  embedding_hash text,
  timestamp timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mensajes_conversacion_conv ON mensajes_conversacion(conversacion_id, timestamp);

-- Adjuntos (órdenes médicas, imágenes)
CREATE TABLE IF NOT EXISTS adjuntos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversacion_id uuid REFERENCES conversaciones(id) ON DELETE CASCADE,
  paciente_id uuid REFERENCES pacientes(id) ON DELETE CASCADE,
  tipo text NOT NULL, -- orden_medica | otro
  storage_key text,
  url_publica text,
  procesado boolean DEFAULT false,
  extracted_text text,
  created_at timestamptz DEFAULT now()
);

-- Logs de acciones
CREATE TABLE IF NOT EXISTS logs_acciones (
  id bigserial PRIMARY KEY,
  accion text NOT NULL,
  metadata jsonb,
  timestamp timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_logs_acciones_accion ON logs_acciones(accion, timestamp);
