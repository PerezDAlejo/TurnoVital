-- 🔄 SCHEMA PARA CACHE INTELIGENTE DE OCR
-- Mejora velocidad y aprendizaje del sistema

-- Tabla de cache de OCR
CREATE TABLE IF NOT EXISTS ocr_cache (
    id SERIAL PRIMARY KEY,
    image_hash VARCHAR(64) UNIQUE NOT NULL,
    ocr_text TEXT,
    medical_info JSONB,
    confidence_score FLOAT DEFAULT 0.0,
    telefono VARCHAR(50),
    file_size INTEGER,
    image_type VARCHAR(20),
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_ocr_cache_hash ON ocr_cache(image_hash);
CREATE INDEX IF NOT EXISTS idx_ocr_cache_telefono ON ocr_cache(telefono);
CREATE INDEX IF NOT EXISTS idx_ocr_cache_created ON ocr_cache(created_at);
CREATE INDEX IF NOT EXISTS idx_ocr_cache_medical_info ON ocr_cache USING gin(medical_info);

-- Tabla de métricas de OCR
CREATE TABLE IF NOT EXISTS ocr_metrics (
    id SERIAL PRIMARY KEY,
    date DATE DEFAULT CURRENT_DATE,
    total_images_processed INTEGER DEFAULT 0,
    successful_extractions INTEGER DEFAULT 0,
    cache_hits INTEGER DEFAULT 0,
    cache_misses INTEGER DEFAULT 0,
    avg_processing_time_ms FLOAT DEFAULT 0.0,
    avg_confidence_score FLOAT DEFAULT 0.0,
    most_common_document_type VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de patrones de documentos médicos
CREATE TABLE IF NOT EXISTS medical_document_patterns (
    id SERIAL PRIMARY KEY,
    pattern_name VARCHAR(100) NOT NULL,
    pattern_keywords TEXT[],
    expected_fields JSONB,
    confidence_threshold FLOAT DEFAULT 0.7,
    usage_count INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insertar patrones comunes iniciales
INSERT INTO medical_document_patterns (pattern_name, pattern_keywords, expected_fields) VALUES
('Orden Fisioterapia', 
 ARRAY['fisioterapia', 'rehabilitación', 'terapia física', 'sesiones'],
 '{"required_fields": ["patient_name", "doctor_name", "sessions"], "optional_fields": ["diagnosis", "frequency", "duration"]}'::jsonb),
('Orden Médica General',
 ARRAY['orden médica', 'prescripción', 'tratamiento'],
 '{"required_fields": ["patient_name", "doctor_name", "treatment"], "optional_fields": ["diagnosis", "medications"]}'::jsonb),
('Resultado Laboratorio',
 ARRAY['laboratorio', 'resultados', 'análisis', 'examen'],
 '{"required_fields": ["patient_name", "test_type", "results"], "optional_fields": ["reference_values", "date"]}'::jsonb)
ON CONFLICT DO NOTHING;

-- Función para limpiar cache viejo (ejecutar periódicamente)
CREATE OR REPLACE FUNCTION cleanup_old_ocr_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Eliminar registros de cache mayores a 90 días
    DELETE FROM ocr_cache 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar métricas automáticamente
CREATE OR REPLACE FUNCTION update_ocr_metrics()
RETURNS TRIGGER AS $$
BEGIN
    -- Actualizar métricas diarias
    INSERT INTO ocr_metrics (date, total_images_processed, successful_extractions)
    VALUES (CURRENT_DATE, 1, CASE WHEN NEW.ocr_text IS NOT NULL AND NEW.ocr_text != '' THEN 1 ELSE 0 END)
    ON CONFLICT (date) DO UPDATE SET
        total_images_processed = ocr_metrics.total_images_processed + 1,
        successful_extractions = ocr_metrics.successful_extractions + 
            CASE WHEN NEW.ocr_text IS NOT NULL AND NEW.ocr_text != '' THEN 1 ELSE 0 END;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Crear trigger
DROP TRIGGER IF EXISTS tr_update_ocr_metrics ON ocr_cache;
CREATE TRIGGER tr_update_ocr_metrics
    AFTER INSERT ON ocr_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_ocr_metrics();