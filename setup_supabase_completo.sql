-- =====================================================================
-- SETUP COMPLETO SUPABASE - IPS REACT
-- =====================================================================
-- Ejecutar en: https://app.supabase.com/project/civjocyxmflmljyyszwy/sql
-- 
-- Este script crea TODAS las tablas y configuraciones necesarias
-- Para el sistema de agendamiento IPS React
-- =====================================================================

-- 1. Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- Para búsquedas full-text

-- =====================================================================
-- 2. TABLAS PRINCIPALES
-- =====================================================================

-- Pacientes
CREATE TABLE IF NOT EXISTS pacientes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombres text NOT NULL,
  apellidos text,
  documento text UNIQUE NOT NULL,
  tipo_documento text DEFAULT 'CC', -- CC, CE, PA
  fecha_nacimiento date,
  telefono text NOT NULL,
  email text,
  direccion text,
  eps text,
  poliza text,
  preferencia_contacto text DEFAULT 'whatsapp',
  
  -- Contacto de emergencia
  emergencia_nombre text,
  emergencia_telefono text,
  emergencia_parentesco text,
  
  -- Metadata
  tipo_paciente text, -- 'primera_vez' | 'control'
  created_at timestamptz DEFAULT NOW(),
  updated_at timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pacientes_documento ON pacientes(documento);
CREATE INDEX IF NOT EXISTS idx_pacientes_telefono ON pacientes(telefono);
CREATE INDEX IF NOT EXISTS idx_pacientes_nombre ON pacientes USING gin(to_tsvector('spanish', nombres || ' ' || COALESCE(apellidos, '')));

-- Citas enriquecidas (integración SaludTools)
CREATE TABLE IF NOT EXISTS citas_enriquecida (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  saludtools_id text UNIQUE, -- ID en SaludTools
  
  -- Referencias
  paciente_id uuid REFERENCES pacientes(id) ON DELETE CASCADE,
  especialista_id text NOT NULL, -- Cédula del fisioterapeuta
  especialista_nombre text NOT NULL,
  
  -- Información de la cita
  tipo_cita text NOT NULL, -- 'fisioterapia' | 'acondicionamiento' | 'medica'
  subtipo text, -- 'primera_vez' | 'control' | 'cardiaca' | 'ortopedica'
  estado text NOT NULL DEFAULT 'confirmada', -- 'confirmada' | 'cancelada' | 'completada'
  fuente text NOT NULL DEFAULT 'whatsapp',
  
  -- Fechas y horarios
  start_at timestamptz NOT NULL,
  end_at timestamptz NOT NULL,
  duracion_min int NOT NULL DEFAULT 60,
  
  -- Detalles
  modalidad text DEFAULT 'CONVENTIONAL', -- SaludTools: CONVENTIONAL | TELEMEDICINE | DOMICILIARY
  notas text,
  orden_medica_adjunta boolean DEFAULT false,
  orden_medica_url text,
  
  -- Pago
  forma_pago text, -- 'poliza' | 'particular' | 'eps'
  monto numeric(10,2),
  
  -- Cancelación
  cancelled_at timestamptz,
  cancellation_reason text,
  
  -- Metadata
  created_at timestamptz DEFAULT NOW(),
  updated_at timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_citas_paciente ON citas_enriquecida(paciente_id);
CREATE INDEX IF NOT EXISTS idx_citas_especialista ON citas_enriquecida(especialista_id, start_at);
CREATE INDEX IF NOT EXISTS idx_citas_estado ON citas_enriquecida(estado);
CREATE INDEX IF NOT EXISTS idx_citas_fecha ON citas_enriquecida(start_at);
CREATE INDEX IF NOT EXISTS idx_citas_saludtools ON citas_enriquecida(saludtools_id);

-- Histórico de cambios de citas
CREATE TABLE IF NOT EXISTS citas_historial (
  id bigserial PRIMARY KEY,
  cita_id uuid NOT NULL,
  evento text NOT NULL, -- 'created' | 'updated' | 'cancelled' | 'completed'
  snapshot jsonb,
  usuario text, -- 'sistema' | 'secretaria' | 'paciente'
  timestamp timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_citas_historial_cita ON citas_historial(cita_id);
CREATE INDEX IF NOT EXISTS idx_citas_historial_evento ON citas_historial(evento, timestamp);

-- =====================================================================
-- 3. CONVERSACIONES Y MENSAJES
-- =====================================================================

-- Conversaciones WhatsApp
CREATE TABLE IF NOT EXISTS conversaciones (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paciente_id uuid REFERENCES pacientes(id) ON DELETE SET NULL,
  telefono text NOT NULL, -- Número WhatsApp del paciente
  canal text NOT NULL DEFAULT 'whatsapp',
  estado text NOT NULL DEFAULT 'activa', -- 'activa' | 'cerrada' | 'escalada'
  contexto jsonb, -- Estado actual de la conversación
  started_at timestamptz DEFAULT NOW(),
  last_message_at timestamptz DEFAULT NOW(),
  closed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_conversaciones_telefono ON conversaciones(telefono);
CREATE INDEX IF NOT EXISTS idx_conversaciones_paciente ON conversaciones(paciente_id);
CREATE INDEX IF NOT EXISTS idx_conversaciones_estado ON conversaciones(estado, last_message_at);

-- Mensajes de conversaciones
CREATE TABLE IF NOT EXISTS mensajes_conversacion (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversacion_id uuid REFERENCES conversaciones(id) ON DELETE CASCADE,
  rol text NOT NULL, -- 'user' | 'assistant' | 'system'
  content text NOT NULL,
  metadata jsonb, -- Información adicional (intents, entities, etc.)
  timestamp timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mensajes_conversacion ON mensajes_conversacion(conversacion_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_mensajes_timestamp ON mensajes_conversacion(timestamp DESC);

-- =====================================================================
-- 4. ADJUNTOS Y OCR
-- =====================================================================

-- Adjuntos (órdenes médicas, imágenes)
CREATE TABLE IF NOT EXISTS adjuntos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversacion_id uuid REFERENCES conversaciones(id) ON DELETE CASCADE,
  paciente_id uuid REFERENCES pacientes(id) ON DELETE CASCADE,
  
  -- Tipo y ubicación
  tipo text NOT NULL, -- 'orden_medica' | 'documento' | 'imagen'
  storage_bucket text DEFAULT 'ordenes-medicas',
  storage_key text NOT NULL, -- Ruta en Supabase Storage
  url_publica text, -- URL pública del archivo
  
  -- Procesamiento OCR
  procesado boolean DEFAULT false,
  ocr_extracted_text text,
  ocr_datos_estructurados jsonb,
  ocr_confianza numeric(3,2), -- 0.00 a 1.00
  ocr_requiere_revision boolean DEFAULT false,
  
  -- Metadata
  nombre_archivo_original text,
  mime_type text,
  tamanio_bytes bigint,
  fecha_envio timestamptz DEFAULT NOW(),
  procesado_at timestamptz,
  
  created_at timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_adjuntos_conversacion ON adjuntos(conversacion_id);
CREATE INDEX IF NOT EXISTS idx_adjuntos_paciente ON adjuntos(paciente_id);
CREATE INDEX IF NOT EXISTS idx_adjuntos_tipo ON adjuntos(tipo, procesado);
CREATE INDEX IF NOT EXISTS idx_adjuntos_storage ON adjuntos(storage_key);

-- Cache de OCR (para evitar reprocesar)
CREATE TABLE IF NOT EXISTS ocr_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  image_hash text UNIQUE NOT NULL,
  ocr_text text,
  medical_info jsonb,
  confidence numeric(3,2),
  created_at timestamptz DEFAULT NOW(),
  accessed_at timestamptz DEFAULT NOW(),
  access_count int DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_ocr_cache_hash ON ocr_cache(image_hash);
CREATE INDEX IF NOT EXISTS idx_ocr_cache_accessed ON ocr_cache(accessed_at);

-- =====================================================================
-- 5. ESCALAMIENTO Y SECRETARIAS
-- =====================================================================

-- Secretarias
CREATE TABLE IF NOT EXISTS secretarias (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre text NOT NULL,
  telefono text UNIQUE NOT NULL,
  email text,
  activa boolean DEFAULT true,
  casos_asignados int DEFAULT 0,
  capacidad_maxima int DEFAULT 3,
  updated_at timestamptz DEFAULT NOW()
);

-- Insertar secretarias IPS React
INSERT INTO secretarias (nombre, telefono, activa, capacidad_maxima)
VALUES 
  ('Secretaria Principal', '+573207143068', true, 3),
  ('Secretaria Backup', '+573002007277', true, 3)
ON CONFLICT (telefono) DO NOTHING;

-- Escalaciones (handoff)
CREATE TABLE IF NOT EXISTS escalaciones_handoff (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id text UNIQUE NOT NULL,
  
  -- Referencias
  conversacion_id uuid REFERENCES conversaciones(id) ON DELETE SET NULL,
  paciente_id uuid REFERENCES pacientes(id) ON DELETE SET NULL,
  secretaria_id uuid REFERENCES secretarias(id) ON DELETE SET NULL,
  
  -- Datos del caso
  telefono_usuario text NOT NULL,
  motivo text NOT NULL, -- 'medico' | 'transferencia' | 'humano' | 'frustracion'
  prioridad text DEFAULT 'normal', -- 'alta' | 'normal' | 'baja'
  estado text NOT NULL DEFAULT 'open', -- 'open' | 'assigned' | 'resolved' | 'closed'
  
  -- Contexto
  historial jsonb,
  patient_data jsonb,
  
  -- Timestamps
  created_at timestamptz DEFAULT NOW(),
  assigned_at timestamptz,
  resolved_at timestamptz,
  closed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_escalaciones_case ON escalaciones_handoff(case_id);
CREATE INDEX IF NOT EXISTS idx_escalaciones_estado ON escalaciones_handoff(estado, created_at);
CREATE INDEX IF NOT EXISTS idx_escalaciones_secretaria ON escalaciones_handoff(secretaria_id);

-- =====================================================================
-- 6. LOGS Y AUDITORÍA
-- =====================================================================

-- Logs de acciones del sistema
CREATE TABLE IF NOT EXISTS logs_acciones (
  id bigserial PRIMARY KEY,
  accion text NOT NULL,
  entidad text, -- 'cita' | 'paciente' | 'conversacion' | 'escalacion'
  entidad_id uuid,
  metadata jsonb,
  nivel text DEFAULT 'info', -- 'debug' | 'info' | 'warning' | 'error'
  timestamp timestamptz DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logs_accion ON logs_acciones(accion, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_entidad ON logs_acciones(entidad, entidad_id);
CREATE INDEX IF NOT EXISTS idx_logs_nivel ON logs_acciones(nivel, timestamp DESC);

-- =====================================================================
-- 7. FUNCIONES Y TRIGGERS
-- =====================================================================

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para updated_at
DROP TRIGGER IF EXISTS update_pacientes_updated_at ON pacientes;
CREATE TRIGGER update_pacientes_updated_at
    BEFORE UPDATE ON pacientes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_citas_updated_at ON citas_enriquecida;
CREATE TRIGGER update_citas_updated_at
    BEFORE UPDATE ON citas_enriquecida
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_secretarias_updated_at ON secretarias;
CREATE TRIGGER update_secretarias_updated_at
    BEFORE UPDATE ON secretarias
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Función para registrar cambios en historial de citas
CREATE OR REPLACE FUNCTION log_cita_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO citas_historial (cita_id, evento, snapshot)
        VALUES (NEW.id, 'created', to_jsonb(NEW));
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO citas_historial (cita_id, evento, snapshot)
        VALUES (NEW.id, 'updated', to_jsonb(NEW));
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO citas_historial (cita_id, evento, snapshot)
        VALUES (OLD.id, 'deleted', to_jsonb(OLD));
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS citas_audit_trigger ON citas_enriquecida;
CREATE TRIGGER citas_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON citas_enriquecida
    FOR EACH ROW
    EXECUTE FUNCTION log_cita_change();

-- Función para limpiar cache OCR antiguo (llamar mensualmente)
CREATE OR REPLACE FUNCTION cleanup_old_ocr_cache()
RETURNS int AS $$
DECLARE
    deleted_count int;
BEGIN
    DELETE FROM ocr_cache
    WHERE accessed_at < NOW() - INTERVAL '30 days'
      AND access_count < 5;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- 8. ROW LEVEL SECURITY (RLS) - COMPLETO
-- =====================================================================

-- Habilitar RLS en TODAS las tablas
ALTER TABLE pacientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE citas_enriquecida ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversaciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE mensajes_conversacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE adjuntos ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalaciones_handoff ENABLE ROW LEVEL SECURITY;
ALTER TABLE secretarias ENABLE ROW LEVEL SECURITY;
ALTER TABLE logs_acciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE ocr_cache ENABLE ROW LEVEL SECURITY;

-- Política: El backend puede hacer todo (autenticado con service_role key)
CREATE POLICY "Backend full access pacientes" ON pacientes FOR ALL USING (true);
CREATE POLICY "Backend full access citas" ON citas_enriquecida FOR ALL USING (true);
CREATE POLICY "Backend full access conversaciones" ON conversaciones FOR ALL USING (true);
CREATE POLICY "Backend full access mensajes" ON mensajes_conversacion FOR ALL USING (true);
CREATE POLICY "Backend full access adjuntos" ON adjuntos FOR ALL USING (true);
CREATE POLICY "Backend full access escalaciones" ON escalaciones_handoff FOR ALL USING (true);
CREATE POLICY "Backend full access secretarias" ON secretarias FOR ALL USING (true);
CREATE POLICY "Backend full access logs" ON logs_acciones FOR ALL USING (true);
CREATE POLICY "Backend full access ocr_cache" ON ocr_cache FOR ALL USING (true);

-- =====================================================================
-- 9. CONFIGURACIÓN DEL NEGOCIO (NUEVO)
-- =====================================================================

CREATE TABLE IF NOT EXISTS configuracion_negocio (
  key text PRIMARY KEY,
  value jsonb NOT NULL,
  description text,
  updated_at timestamptz DEFAULT NOW()
);

ALTER TABLE configuracion_negocio ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Backend full access config" ON configuracion_negocio FOR ALL USING (true);

-- Insertar configuración inicial (extraída del código actual)
INSERT INTO configuracion_negocio (key, value, description)
VALUES 
  ('fisioterapeutas', '[
    {"cedula": "1098654321", "nombre": "Dra. Ana María Polo", "especialidad": "Fisioterapia"},
    {"cedula": "1007654321", "nombre": "Dr. Carlos Ramirez", "especialidad": "Fisioterapia Deportiva"}
  ]'::jsonb, 'Lista de especialistas disponibles'),
  
  ('precios', '{
    "valoracion": 50000,
    "sesion_particular": 35000,
    "paquete_10": 300000,
    "domicilio_recargo": 15000
  }'::jsonb, 'Lista de precios base'),
  
  ('eps_validas', '["Coomeva", "Sura", "Sanitas", "Salud Total"]'::jsonb, 'EPS con convenio'),
  
  ('horarios_atencion', '{
    "lunes_viernes": {"inicio": "07:00", "fin": "18:00"},
    "sabado": {"inicio": "08:00", "fin": "12:00"}
  }'::jsonb, 'Horarios de atención de la clínica')
ON CONFLICT (key) DO NOTHING;

-- =====================================================================
-- 10. VISTAS ÚTILES
-- =====================================================================

-- Vista: Citas próximas
CREATE OR REPLACE VIEW citas_proximas AS
SELECT 
    c.id,
    c.saludtools_id,
    p.nombres || ' ' || COALESCE(p.apellidos, '') as paciente_nombre,
    p.documento,
    p.telefono,
    c.especialista_nombre,
    c.tipo_cita,
    c.subtipo,
    c.start_at,
    c.end_at,
    c.estado,
    c.orden_medica_adjunta
FROM citas_enriquecida c
JOIN pacientes p ON p.id = c.paciente_id
WHERE c.start_at >= NOW()
  AND c.estado = 'confirmada'
ORDER BY c.start_at;

-- Vista: Órdenes pendientes de procesar
CREATE OR REPLACE VIEW ordenes_pendientes AS
SELECT 
    a.id,
    a.created_at as fecha_envio,
    p.nombres || ' ' || COALESCE(p.apellidos, '') as paciente_nombre,
    p.documento,
    a.url_publica,
    a.ocr_confianza,
    a.ocr_requiere_revision
FROM adjuntos a
JOIN pacientes p ON p.id = a.paciente_id
WHERE a.tipo = 'orden_medica'
  AND a.procesado = false
ORDER BY a.created_at DESC;

-- =====================================================================
-- FIN DEL SCRIPT
-- =====================================================================

-- Verificar instalación
SELECT 'Instalación completa!' as mensaje,
       (SELECT COUNT(*) FROM pacientes) as total_pacientes,
       (SELECT COUNT(*) FROM citas_enriquecida) as total_citas,
       (SELECT COUNT(*) FROM conversaciones) as total_conversaciones,
       (SELECT COUNT(*) FROM secretarias) as total_secretarias,
       (SELECT COUNT(*) FROM configuracion_negocio) as config_items;
