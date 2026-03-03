-- 🔐 SECURE FILE STORAGE SCHEMA
-- Database schema for secure file storage with encryption, versioning, and access control

-- Extensión para encriptación (si no está disponible, usar funciones de aplicación)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Tabla principal de archivos seguros
CREATE TABLE IF NOT EXISTS secure_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_hash VARCHAR(128) UNIQUE NOT NULL, -- SHA-256 del archivo original
    encrypted_hash VARCHAR(128) UNIQUE NOT NULL, -- SHA-256 del archivo encriptado
    file_name VARCHAR(255) NOT NULL,
    original_name VARCHAR(255),
    mime_type VARCHAR(100),
    file_size BIGINT NOT NULL,
    encrypted_size BIGINT,
    storage_path TEXT NOT NULL, -- Ruta en el sistema de almacenamiento
    encryption_key_id UUID, -- Referencia a la clave de encriptación usada
    compression_applied BOOLEAN DEFAULT FALSE,
    compression_ratio DECIMAL(5,2),

    -- Metadata del archivo
    document_type VARCHAR(50), -- orden_medica, laboratorio, radiografia, etc.
    medical_info JSONB, -- Información médica extraída por OCR
    ocr_confidence DECIMAL(3,2), -- Confianza del OCR (0.00-1.00)
    ocr_text TEXT, -- Texto extraído por OCR

    -- Información del paciente (para acceso controlado)
    patient_document VARCHAR(50),
    patient_name VARCHAR(255),

    -- Control de versiones
    version INTEGER DEFAULT 1,
    parent_file_id UUID REFERENCES secure_files(id), -- Archivo padre si es versión
    is_latest_version BOOLEAN DEFAULT TRUE,

    -- Estado y procesamiento
    processing_status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    processing_attempts INTEGER DEFAULT 0,
    last_processed_at TIMESTAMPTZ,
    processing_errors TEXT,

    -- Metadatos de seguridad
    encryption_algorithm VARCHAR(50) DEFAULT 'AES-256-GCM',
    integrity_hash VARCHAR(128), -- Hash para verificar integridad
    data_classification VARCHAR(20) DEFAULT 'confidential', -- public, internal, confidential, restricted

    -- Control de acceso
    owner_user_id UUID, -- Usuario que subió el archivo
    owner_role VARCHAR(50), -- Rol del propietario (admin, doctor, secretary, patient)
    access_permissions JSONB, -- Permisos detallados por rol/usuario

    -- Auditoría
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ, -- Soft delete
    retention_until TIMESTAMPTZ -- Fecha hasta la cual debe retenerse
);

-- Índices para optimización
CREATE INDEX IF NOT EXISTS idx_secure_files_hash ON secure_files(file_hash);
CREATE INDEX IF NOT EXISTS idx_secure_files_encrypted_hash ON secure_files(encrypted_hash);
CREATE INDEX IF NOT EXISTS idx_secure_files_patient ON secure_files(patient_document);
CREATE INDEX IF NOT EXISTS idx_secure_files_type ON secure_files(document_type);
CREATE INDEX IF NOT EXISTS idx_secure_files_status ON secure_files(processing_status);
CREATE INDEX IF NOT EXISTS idx_secure_files_created ON secure_files(created_at);
CREATE INDEX IF NOT EXISTS idx_secure_files_owner ON secure_files(owner_user_id, owner_role);
CREATE INDEX IF NOT EXISTS idx_secure_files_medical_info ON secure_files USING gin(medical_info);
CREATE INDEX IF NOT EXISTS idx_secure_files_access ON secure_files USING gin(access_permissions);

-- Tabla de versiones de archivos
CREATE TABLE IF NOT EXISTS file_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES secure_files(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    file_hash VARCHAR(128) NOT NULL,
    encrypted_hash VARCHAR(128) NOT NULL,
    storage_path TEXT NOT NULL,
    encryption_key_id UUID,
    file_size BIGINT NOT NULL,
    encrypted_size BIGINT,
    changes_description TEXT,
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(file_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_file_versions_file ON file_versions(file_id, version_number DESC);

-- Tabla de claves de encriptación (rotación de claves)
CREATE TABLE IF NOT EXISTS encryption_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_identifier VARCHAR(100) UNIQUE NOT NULL,
    encrypted_key TEXT NOT NULL, -- Clave encriptada con KMS/master key
    algorithm VARCHAR(50) DEFAULT 'AES-256-GCM',
    key_version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    rotated_at TIMESTAMPTZ
);

-- Tabla de logs de auditoría de archivos
CREATE TABLE IF NOT EXISTS file_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID REFERENCES secure_files(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL, -- upload, download, delete, access, modify
    user_id UUID,
    user_role VARCHAR(50),
    user_ip VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    metadata JSONB, -- Información adicional del evento
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_file_audit_file ON file_audit_logs(file_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_file_audit_user ON file_audit_logs(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_file_audit_action ON file_audit_logs(action, timestamp DESC);

-- Tabla de permisos de acceso
CREATE TABLE IF NOT EXISTS file_access_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES secure_files(id) ON DELETE CASCADE,
    user_id UUID,
    role VARCHAR(50),
    permission VARCHAR(20) NOT NULL, -- read, write, delete, admin
    granted_by UUID,
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,

    UNIQUE(file_id, user_id, permission),
    UNIQUE(file_id, role, permission)
);

CREATE INDEX IF NOT EXISTS idx_file_permissions_file ON file_access_permissions(file_id);
CREATE INDEX IF NOT EXISTS idx_file_permissions_user ON file_access_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_file_permissions_role ON file_access_permissions(role);

-- Tabla de tokens de acceso temporal
CREATE TABLE IF NOT EXISTS file_access_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES secure_files(id) ON DELETE CASCADE,
    token_hash VARCHAR(128) UNIQUE NOT NULL,
    permissions VARCHAR(20) NOT NULL, -- read, write
    expires_at TIMESTAMPTZ NOT NULL,
    max_uses INTEGER,
    current_uses INTEGER DEFAULT 0,
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_file_tokens_hash ON file_access_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_file_tokens_expires ON file_access_tokens(expires_at);

-- Tabla de configuración de retención
CREATE TABLE IF NOT EXISTS retention_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    document_type VARCHAR(50),
    retention_period_days INTEGER NOT NULL,
    auto_delete BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insertar políticas de retención por defecto para datos médicos
INSERT INTO retention_policies (name, document_type, retention_period_days, description) VALUES
('Ordenes Médicas', 'orden_medica', 2555, '7 años según normatividad colombiana'),
('Resultados Laboratorio', 'laboratorio', 2555, '7 años según normatividad colombiana'),
('Imágenes Radiológicas', 'radiografia', 2555, '7 años según normatividad colombiana'),
('Historias Clínicas', 'historia_clinica', 2555, '7 años según normatividad colombiana'),
('Consentimientos', 'consentimiento', 2555, '7 años según normatividad colombiana'),
('Certificados Médicos', 'certificado_medico', 1825, '5 años para certificados'),
('Documentos Temporales', 'temporal', 90, '3 meses para documentos temporales')
ON CONFLICT DO NOTHING;

-- Función para verificar permisos de acceso
CREATE OR REPLACE FUNCTION check_file_access(
    p_file_id UUID,
    p_user_id UUID DEFAULT NULL,
    p_user_role VARCHAR(50) DEFAULT NULL,
    p_requested_permission VARCHAR(20) DEFAULT 'read'
) RETURNS BOOLEAN AS $$
DECLARE
    has_access BOOLEAN := FALSE;
BEGIN
    -- Verificar si el archivo existe y no está eliminado
    IF NOT EXISTS (
        SELECT 1 FROM secure_files
        WHERE id = p_file_id AND deleted_at IS NULL
    ) THEN
        RETURN FALSE;
    END IF;

    -- El propietario siempre tiene acceso completo
    IF p_user_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM secure_files
        WHERE id = p_file_id AND owner_user_id = p_user_id
    ) THEN
        RETURN TRUE;
    END IF;

    -- Verificar permisos específicos por usuario
    IF p_user_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM file_access_permissions
        WHERE file_id = p_file_id
          AND user_id = p_user_id
          AND permission = p_requested_permission
          AND is_active = TRUE
          AND (expires_at IS NULL OR expires_at > NOW())
    ) THEN
        RETURN TRUE;
    END IF;

    -- Verificar permisos por rol
    IF p_user_role IS NOT NULL AND EXISTS (
        SELECT 1 FROM file_access_permissions
        WHERE file_id = p_file_id
          AND role = p_user_role
          AND permission = p_requested_permission
          AND is_active = TRUE
          AND (expires_at IS NULL OR expires_at > NOW())
    ) THEN
        RETURN TRUE;
    END IF;

    -- Verificar tokens de acceso temporal
    IF EXISTS (
        SELECT 1 FROM file_access_tokens
        WHERE file_id = p_file_id
          AND expires_at > NOW()
          AND current_uses < max_uses
          AND permissions = p_requested_permission
    ) THEN
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Función para registrar acceso a archivo
CREATE OR REPLACE FUNCTION log_file_access(
    p_file_id UUID,
    p_action VARCHAR(50),
    p_user_id UUID DEFAULT NULL,
    p_user_role VARCHAR(50) DEFAULT NULL,
    p_success BOOLEAN DEFAULT TRUE,
    p_metadata JSONB DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO file_audit_logs (
        file_id, action, user_id, user_role, success, metadata
    ) VALUES (
        p_file_id, p_action, p_user_id, p_user_role, p_success, p_metadata
    );
END;
$$ LANGUAGE plpgsql;

-- Función para limpiar archivos expirados (ejecutar periódicamente)
CREATE OR REPLACE FUNCTION cleanup_expired_files()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
    file_record RECORD;
BEGIN
    -- Marcar como eliminados archivos que excedieron su período de retención
    FOR file_record IN
        SELECT sf.id, sf.storage_path
        FROM secure_files sf
        JOIN retention_policies rp ON sf.document_type = rp.document_type
        WHERE sf.retention_until < NOW()
          AND sf.deleted_at IS NULL
          AND rp.auto_delete = TRUE
    LOOP
        -- Marcar como eliminado
        UPDATE secure_files
        SET deleted_at = NOW()
        WHERE id = file_record.id;

        -- Log de eliminación
        PERFORM log_file_access(
            file_record.id,
            'auto_delete',
            NULL,
            'system',
            TRUE,
            jsonb_build_object('reason', 'retention_expired', 'storage_path', file_record.storage_path)
        );

        deleted_count := deleted_count + 1;
    END LOOP;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Función para rotar claves de encriptación
CREATE OR REPLACE FUNCTION rotate_encryption_key(
    p_old_key_id UUID,
    p_new_key_identifier VARCHAR(100),
    p_new_encrypted_key TEXT
) RETURNS UUID AS $$
DECLARE
    new_key_id UUID;
BEGIN
    -- Crear nueva clave
    INSERT INTO encryption_keys (key_identifier, encrypted_key)
    VALUES (p_new_key_identifier, p_new_encrypted_key)
    RETURNING id INTO new_key_id;

    -- Marcar clave anterior como inactiva
    UPDATE encryption_keys
    SET is_active = FALSE, rotated_at = NOW()
    WHERE id = p_old_key_id;

    -- Log de rotación
    INSERT INTO file_audit_logs (action, user_role, success, metadata)
    VALUES ('key_rotation', 'system', TRUE,
            jsonb_build_object('old_key_id', p_old_key_id, 'new_key_id', new_key_id));

    RETURN new_key_id;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar updated_at
CREATE OR REPLACE FUNCTION update_secure_files_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_secure_files_updated_at ON secure_files;
CREATE TRIGGER tr_secure_files_updated_at
    BEFORE UPDATE ON secure_files
    FOR EACH ROW
    EXECUTE FUNCTION update_secure_files_updated_at();

-- Políticas de seguridad RLS (Row Level Security) - opcional pero recomendado
-- ALTER TABLE secure_files ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE file_access_permissions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE file_audit_logs ENABLE ROW LEVEL SECURITY;

-- Políticas RLS de ejemplo (ajustar según necesidades específicas)
-- CREATE POLICY secure_files_owner_policy ON secure_files
--     FOR ALL USING (owner_user_id = current_user_id() OR check_file_access(id, current_user_id(), current_user_role()));

COMMENT ON TABLE secure_files IS 'Tabla principal para almacenamiento seguro de archivos médicos con encriptación y control de acceso';
COMMENT ON TABLE file_versions IS 'Versionado de archivos para mantener historial de cambios';
COMMENT ON TABLE encryption_keys IS 'Gestión de claves de encriptación con rotación automática';
COMMENT ON TABLE file_audit_logs IS 'Auditoría completa de todas las operaciones con archivos';
COMMENT ON TABLE file_access_permissions IS 'Permisos de acceso granular por usuario y rol';
COMMENT ON TABLE file_access_tokens IS 'Tokens temporales para acceso seguro a archivos';
COMMENT ON TABLE retention_policies IS 'Políticas de retención según normatividad colombiana';