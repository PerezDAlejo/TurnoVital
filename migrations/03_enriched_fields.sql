-- Migration 03: Enriched fields for citas_enriquecida and pacientes
-- Safe to run multiple times

-- Pacientes extras
ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS plan_salud text;
ALTER TABLE IF EXISTS pacientes ADD COLUMN IF NOT EXISTS tiene_orden_medica boolean;

-- Citas enriquecidas extras
ALTER TABLE IF EXISTS citas_enriquecida ADD COLUMN IF NOT EXISTS especialista_nombre text;
ALTER TABLE IF EXISTS citas_enriquecida ADD COLUMN IF NOT EXISTS franja text; -- manana | mediodia | tarde
ALTER TABLE IF EXISTS citas_enriquecida ADD COLUMN IF NOT EXISTS plan_salud text;
ALTER TABLE IF EXISTS citas_enriquecida ADD COLUMN IF NOT EXISTS tiene_orden_medica boolean;
ALTER TABLE IF EXISTS citas_enriquecida ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_citas_enriq_especialista_nombre ON citas_enriquecida(especialista_nombre, start_at);
