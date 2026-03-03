# 🧪 Tests - Sistema IPS React

Suite completa de tests para validación del sistema de agendamiento.

## 📋 Tests Principales

### ✅ Validación General
- `test_validacion_rapida.py` - Suite de validación rápida del sistema
- `validar_correcciones.py` - Validación de correcciones de bugs
- `test_pre_despliegue_final.py` - Tests pre-despliegue

### 🔧 SaludTools API
- `test_saludtools_completo.py` - Tests completos CRUD SaludTools
- `test_correccion_error_412.py` - Validación corrección Error 412
- `test_agendamiento_real.py` - Tests de agendamiento end-to-end

### 💬 Chatbot
- `test_chatbot_real.py` - Tests del chatbot principal
- `test_chatbot_saludtools_real.py` - Integración chatbot + SaludTools
- `test_servidor_simulacion.py` - Simulación de servidor procesando mensajes

### 📸 OCR
- `test_ocr_completo.py` - Tests completos de OCR
- `demo_ocr_completo.py` - Demostración de OCR inteligente

### 🎯 Funcionalidades Específicas
- `test_funcionalidades_criticas.py` - 5 funcionalidades críticas
- `test_fisioterapia_completa.py` - Tests de tipos de fisioterapia
- `test_escalamiento_real.py` - Tests de escalamiento a secretaria

## 🚀 Ejecutar Tests

```bash
# Test rápido de validación
python tests/test_validacion_rapida.py

# Test completo de SaludTools
python tests/test_saludtools_completo.py

# Test de agendamiento real
python tests/test_agendamiento_real.py
```

## 📊 Cobertura

Los tests cubren:
- ✅ CRUD completo de SaludTools
- ✅ Conversaciones del chatbot
- ✅ Procesamiento OCR
- ✅ Escalamiento a humanos
- ✅ Validaciones de negocio
- ✅ Integración end-to-end
