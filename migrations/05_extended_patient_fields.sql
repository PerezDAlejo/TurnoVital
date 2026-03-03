-- Migration 05: Extended patient fields (eps/entidad, fecha_nacimiento, direccion, contacto de emergencia)
-- Safe / idempotent: uses ADD COLUMN IF NOT EXISTS

ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS entidad text; -- EPS / aseguradora / plan externo
ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS fecha_nacimiento date;
ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS direccion text;
ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS contacto_emergencia_nombre text;
ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS contacto_emergencia_telefono text;
ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS contacto_emergencia_parentesco text;

-- Minimal index to accelerate lookups by entidad if later needed for reporting
CREATE INDEX IF NOT EXISTS idx_pacientes_entidad ON pacientes(entidad);
