-- ========================================
-- MIGRACIÓN: Agregar campos de contacto emergencia y método de pago
-- Fecha: 12 de Diciembre de 2025
-- Descripción: Agrega campos obligatorios para contacto de emergencia,
--              método de pago, y sesiones de orden médica
-- ========================================

-- 1. TABLA PACIENTES: Agregar campos de contacto de emergencia
-- ========================================

ALTER TABLE pacientes 
ADD COLUMN IF NOT EXISTS contacto_emergencia_nombre VARCHAR(255),
ADD COLUMN IF NOT EXISTS contacto_emergencia_telefono VARCHAR(20),
ADD COLUMN IF NOT EXISTS contacto_emergencia_parentesco VARCHAR(50);

-- Agregar comentarios a los campos
COMMENT ON COLUMN pacientes.contacto_emergencia_nombre IS 'Nombre completo del contacto de emergencia (obligatorio)';
COMMENT ON COLUMN pacientes.contacto_emergencia_telefono IS 'Teléfono del contacto de emergencia (obligatorio)';
COMMENT ON COLUMN pacientes.contacto_emergencia_parentesco IS 'Relación con el paciente: madre, esposo, hijo, etc.';

-- 2. TABLA CITAS: Agregar campos de método de pago y plan
-- ========================================

ALTER TABLE citas
ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(50),
ADD COLUMN IF NOT EXISTS plan_acondicionamiento VARCHAR(50),
ADD COLUMN IF NOT EXISTS numero_sesiones_orden INT DEFAULT 1;

-- Agregar comentarios
COMMENT ON COLUMN citas.metodo_pago IS 'Método de pago: eps_presencial, particular_efectivo, particular_tarjeta, particular_transferencia';
COMMENT ON COLUMN citas.plan_acondicionamiento IS 'Plan de acondicionamiento: basico, intermedio, avanzado, intensivo';
COMMENT ON COLUMN citas.numero_sesiones_orden IS 'Número de sesiones indicadas en la orden médica (si aplica)';

-- 3. CREAR ÍNDICES para mejorar performance
-- ========================================

CREATE INDEX IF NOT EXISTS idx_pacientes_contacto_emergencia_telefono 
ON pacientes(contacto_emergencia_telefono);

CREATE INDEX IF NOT EXISTS idx_citas_metodo_pago 
ON citas(metodo_pago);

CREATE INDEX IF NOT EXISTS idx_citas_plan_acondicionamiento 
ON citas(plan_acondicionamiento);

-- 4. CREAR CONSTRAINTS para validación
-- ========================================

-- Validar método de pago (solo valores permitidos)
ALTER TABLE citas
ADD CONSTRAINT chk_metodo_pago 
CHECK (
    metodo_pago IS NULL OR 
    metodo_pago IN (
        'eps_presencial',
        'particular_efectivo',
        'particular_tarjeta',
        'particular_transferencia'
    )
);

-- Validar plan de acondicionamiento (solo valores permitidos)
ALTER TABLE citas
ADD CONSTRAINT chk_plan_acondicionamiento 
CHECK (
    plan_acondicionamiento IS NULL OR 
    plan_acondicionamiento IN (
        'clase_individual',
        'basico',
        'intermedio',
        'avanzado',
        'intensivo'
    )
);

-- Validar número de sesiones (debe ser positivo)
ALTER TABLE citas
ADD CONSTRAINT chk_numero_sesiones_orden 
CHECK (numero_sesiones_orden > 0);

-- 5. ACTUALIZAR REGISTROS EXISTENTES
-- ========================================

-- Establecer valores por defecto para registros existentes
UPDATE citas 
SET numero_sesiones_orden = 1 
WHERE numero_sesiones_orden IS NULL;

-- 6. CREAR FUNCIÓN para validar contacto emergencia completo
-- ========================================

CREATE OR REPLACE FUNCTION validar_contacto_emergencia()
RETURNS TRIGGER AS $$
BEGIN
    -- Si algún campo de contacto emergencia está lleno, todos deben estar llenos
    IF (
        NEW.contacto_emergencia_nombre IS NOT NULL OR 
        NEW.contacto_emergencia_telefono IS NOT NULL OR 
        NEW.contacto_emergencia_parentesco IS NOT NULL
    ) THEN
        IF (
            NEW.contacto_emergencia_nombre IS NULL OR 
            NEW.contacto_emergencia_telefono IS NULL OR 
            NEW.contacto_emergencia_parentesco IS NULL OR
            NEW.contacto_emergencia_nombre = '' OR
            NEW.contacto_emergencia_telefono = '' OR
            NEW.contacto_emergencia_parentesco = ''
        ) THEN
            RAISE EXCEPTION 'Si proporciona contacto de emergencia, todos los campos (nombre, teléfono, parentesco) son obligatorios';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Crear trigger para validar contacto emergencia
DROP TRIGGER IF EXISTS trigger_validar_contacto_emergencia ON pacientes;
CREATE TRIGGER trigger_validar_contacto_emergencia
    BEFORE INSERT OR UPDATE ON pacientes
    FOR EACH ROW
    EXECUTE FUNCTION validar_contacto_emergencia();

-- 7. CREAR VISTA para análisis de métodos de pago
-- ========================================

CREATE OR REPLACE VIEW vista_citas_metodo_pago AS
SELECT 
    metodo_pago,
    COUNT(*) as total_citas,
    COUNT(DISTINCT paciente_id) as total_pacientes,
    AVG(CASE WHEN estado = 'confirmada' THEN 1 ELSE 0 END) * 100 as tasa_confirmacion
FROM citas
WHERE metodo_pago IS NOT NULL
GROUP BY metodo_pago
ORDER BY total_citas DESC;

-- 8. CREAR VISTA para análisis de planes de acondicionamiento
-- ========================================

CREATE OR REPLACE VIEW vista_planes_acondicionamiento AS
SELECT 
    plan_acondicionamiento,
    COUNT(*) as total_suscripciones,
    COUNT(DISTINCT paciente_id) as total_pacientes,
    MIN(fecha_cita) as primera_suscripcion,
    MAX(fecha_cita) as ultima_suscripcion
FROM citas
WHERE plan_acondicionamiento IS NOT NULL
GROUP BY plan_acondicionamiento
ORDER BY total_suscripciones DESC;

-- 9. PERMISOS (ajustar según tu configuración RLS)
-- ========================================

-- Otorgar permisos de lectura/escritura al rol de la aplicación
-- NOTA: Ajusta 'anon' y 'authenticated' según tus roles
GRANT SELECT, INSERT, UPDATE ON pacientes TO anon;
GRANT SELECT, INSERT, UPDATE ON pacientes TO authenticated;

GRANT SELECT, INSERT, UPDATE ON citas TO anon;
GRANT SELECT, INSERT, UPDATE ON citas TO authenticated;

GRANT SELECT ON vista_citas_metodo_pago TO authenticated;
GRANT SELECT ON vista_planes_acondicionamiento TO authenticated;

-- 10. LOGGING DE MIGRACIÓN
-- ========================================

-- Insertar registro en tabla de migraciones (si existe)
-- Si no existe la tabla, crear una simple
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    descripcion TEXT,
    ejecutada_en TIMESTAMP DEFAULT NOW()
);

INSERT INTO schema_migrations (version, descripcion) 
VALUES (
    '002_agregar_campos_contacto_pago',
    'Agregados campos de contacto de emergencia (nombre, teléfono, parentesco), método de pago, plan acondicionamiento, y número de sesiones de orden médica'
)
ON CONFLICT (version) DO NOTHING;

-- ========================================
-- FIN DE MIGRACIÓN
-- ========================================

-- VERIFICACIÓN RÁPIDA:
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name IN ('pacientes', 'citas')
-- ORDER BY table_name, ordinal_position;
