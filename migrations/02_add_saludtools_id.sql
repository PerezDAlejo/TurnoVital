-- Migration: add explicit saludtools_id column to citas_enriquecida
-- Safe to run multiple times (IF NOT EXISTS guards)
ALTER TABLE IF EXISTS citas_enriquecida
  ADD COLUMN IF NOT EXISTS saludtools_id bigint;

CREATE INDEX IF NOT EXISTS idx_citas_enriq_saludtools_id ON citas_enriquecida(saludtools_id);

-- Backfill from legacy pattern in notas (saludtools_id=123456...)
UPDATE citas_enriquecida
SET saludtools_id = (regexp_match(notas, 'saludtools_id=(\d+)'))[1]::bigint
WHERE saludtools_id IS NULL
  AND notas LIKE 'saludtools_id=%';

-- NOTE: Going forward, application code should stop relying on pattern matching in notas
-- and instead use the dedicated column for lookups.
