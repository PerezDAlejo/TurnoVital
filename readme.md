# Sistema de Agendamiento Médico con WhatsApp, FastAPI, OpenAI y Saludtools

**Sistema de producción aprobado por IPS React** - Asistente virtual para clínicas médicas que permite a los pacientes agendar, consultar, editar y cancelar citas médicas a través de WhatsApp, usando IA conversacional (OpenAI) e integración directa con Saludtools.

---

## 🚀 Características Principales

- **Atención WhatsApp 24/7** con lenguaje natural y IA conversacional
- **Integración nativa con Saludtools** para gestión completa de pacientes y citas
- **IA avanzada (OpenAI GPT-4o)** para interpretar intenciones y extraer datos médicos
- **Validación automática** de fechas, documentos y reglas de negocio clínicas
- **Arquitectura escalable** con FastAPI, Supabase, AWS y n8n
- **Rate limiting y retry logic** para cumplir especificaciones de Saludtools
- **Sistema de autenticación robusto** con renovación automática de tokens
- **Experiencia conversacional** profesional y memorable para pacientes

---

## 📊 Estado del Proyecto

**✅ APROBADO PARA PRODUCCIÓN**
- Budget asignado por IPS React
- Arquitectura técnica validada
- Costos operacionales confirmados ($140-190 USD/mes)
- Integración Saludtools en desarrollo

**🔄 Fase Actual: Implementación Saludtools**
- Módulo de integración completado
- Esperando acceso a ambiente de pruebas
- Documentación API recibida de soporte Saludtools

---

## ⚙️ Instalación y Configuración

1. **Clona el repositorio**
   ```bash
   git clone https://github.com/tuusuario/agendamiento-citas.git
   cd agendamiento-citas
   ```

2. **Instala dependencias**
   ```bash
   pip install -r Requirements.txt
   ```

3. **Configura variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tus credenciales
   ```

   **Variables requeridas:**
   ```env
   # Saludtools API (obtener del equipo Saludtools)
   SALUDTOOLS_API_KEY=tu_api_key_de_saludtools
   SALUDTOOLS_API_SECRET=tu_api_secret_de_saludtools
   ENVIRONMENT=testing  # testing o prod
   
   # OpenAI
   OPENAI_API_KEY=sk-proj-...
   
   # Twilio WhatsApp
   TWILIO_ACCOUNT_SID=ACxxxxxx
   TWILIO_AUTH_TOKEN=tu_auth_token
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   
   # Supabase (logs y auditoría)
   SUPABASE_URL=https://tu-proyecto.supabase.co
   SUPABASE_KEY=tu_anon_key
   ```

4. **Ejecuta el servidor**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

---

## 🏗️ Arquitectura del Sistema

### Componentes Principales

1. **FastAPI Backend**
   - API REST para gestión de citas
   - Webhook para WhatsApp (Twilio)
   - Integración con IA conversacional

2. **Saludtools Integration**
   - Autenticación con API Key/Secret
   - Gestión de pacientes y citas
   - Rate limiting (100 req/min)
   - Token refresh automático (24h)

3. **WhatsApp + OpenAI**
   - Procesamiento de lenguaje natural
   - Extracción de datos estructurados
   - Conversación contextual inteligente

4. **Infraestructura Cloud**
   - AWS EC2/Lightsail (hosting)
   - Supabase (database & logs)
   - n8n (automation workflows)

### Flujo de Operación

```
Paciente → WhatsApp → Twilio → FastAPI → OpenAI → Saludtools → Respuesta
              ↓                     ↓           ↓
         Logs Supabase    Validaciones    Gestión Médica
```

---

## 🔗 Integración con Saludtools

### Especificaciones Técnicas

- **Rate Limit**: 100 requests por minuto
- **Token Duration**: 24 horas con refresh automático
- **Max Retries**: 6 intentos antes de bloqueo
- **Ambiente Test**: En proceso de configuración
- **Ambiente Prod**: `https://saludtools.carecloud.com.co/integration`

### Funcionalidades Implementadas

- ✅ Autenticación con API Key/Secret
- ✅ Creación y búsqueda de pacientes
- ✅ Gestión completa de citas (CRUD)
- ✅ Rate limiting y retry logic
- ✅ Logging y auditoría
- 🔄 Configuración de webhooks (pendiente)
     SUPABASE_URL=tu_supabase_url
     SUPABASE_KEY=tu_supabase_key
     ```

4. **Configura Twilio Sandbox**
   - Ve a [Twilio WhatsApp Sandbox](https://www.twilio.com/console/sms/whatsapp/sandbox).
   - Pega la URL pública de LocalTunnel en el campo "WHEN A MESSAGE COMES IN":
     ```
     https://tunelprueba123.loca.lt/webhook/twilio
     ```
   - Método: **POST**

5. **Ejecuta la API**
   ```sh
   uvicorn app.main:app --reload
   ```

6. **Expón tu API con LocalTunnel**
   ```sh
   lt --port 8000 --subdomain tunelprueba123
   ```

---

## 🧪 Testing y Validación

### Pruebas con WhatsApp (Ambiente de Testing)

1. **Configuración inicial**
   ```bash
   # Asegúrate de que ENVIRONMENT=testing en tu .env
   uvicorn app.main:app --reload --port 8000
   
   # En otra terminal, expón con LocalTunnel
   lt --port 8000 --subdomain tunelprueba123
   ```

2. **Flujos de prueba recomendados**
   - "Hola, quiero agendar una cita"
   - "Consultar mis citas para documento 12345678"
   - "Editar mi cita del lunes a las 10"
   - "Cancelar la cita del 30 de junio"

### Pruebas de API Directa

```bash
# Agendar cita
curl -X POST "http://localhost:8000/agendar" \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Juan Pérez",
    "documento": "12345678",
    "telefono": "573001234567",
    "fecha_deseada": "2024-02-15T10:00:00",
    "descripcion": "Consulta general"
  }'

# Consultar citas
curl -X GET "http://localhost:8000/citas?documento=12345678"
```

### Pruebas de Integración Saludtools

```python
# Ejecutar pruebas unitarias
python test_saludtools.py

# Ejecutar pruebas end-to-end
python test_cita_e2e.py
```

---

## 📁 Estructura del Proyecto

```
agendamiento-citas/
├── app/
│   ├── __init__.py              # Configuración global y cliente Saludtools
│   ├── main.py                  # FastAPI app y configuración CORS
│   ├── models.py                # Modelos Pydantic para validación
│   ├── ai.py                    # Prompt y lógica de IA (Valeria)
│   ├── database.py              # Integración Supabase para logs
│   ├── saludtools.py            # 🆕 Integración completa Saludtools API
│   └── routes/
│       ├── webhook.py           # Webhook WhatsApp + conversación IA
│       └── citas.py             # CRUD de citas con Saludtools
├── secrets/                     # Credenciales (no versionar)
├── test_cita_e2e.py            # Pruebas end-to-end automatizadas
├── test_saludtools.py          # Pruebas unitarias Saludtools
├── Requirements.txt            # Dependencias Python
├── .env.example               # Plantilla de variables de entorno
└── README.md                  # Este archivo
```

---

## 🔄 Modo de Desarrollo (Mock)

El sistema puede funcionar en **modo mock** cuando no tienes credenciales de Saludtools:

- Configura `SALUDTOOLS_ENVIRONMENT=qa` en `.env`
- Si no hay `SALUDTOOLS_API_KEY`, el sistema usa datos simulados
- Ideal para desarrollo y pruebas sin impactar el sistema médico real

---

## 🏥 Integración con Saludtools

El sistema se integra directamente con Saludtools para:

1. **Autenticación automática** con API Key y Secret
2. **Búsqueda y creación de pacientes** por documento
3. **Gestión completa de citas médicas** (crear, consultar, editar, cancelar)
4. **Sincronización en tiempo real** con el sistema médico
5. **Validación de parámetros** (tipos de documento, estados de cita)

### Endpoints Saludtools utilizados:
- `POST /authenticate/apikey/v1/` — Autenticación
- `POST /sync/event/v1/` — Operaciones CRUD de pacientes y citas
- `GET /parametric/*` — Parámetros del sistema

---

## 💡 ¿Por qué este sistema destaca?

- **Integración médica real** con Saludtools (no solo calendarios básicos).
 - **Despliegue híbrido**: corre localmente con uvicorn o en AWS Lambda (serverless) sin cambios de código.
 - **Métricas expuestas** en JSON y formato Prometheus para observabilidad.
 - **Rate limiting defensivo** y retries con backoff para robustez.

---

## ☁️ Despliegue Serverless (AWS SAM + Lambda + API Gateway)

El repo ya incluye:
- `serverless/handler.py` (envoltura Mangum)
- `serverless/template.yaml` (infraestructura SAM)
- `.samignore` (exclusiones de build)

### Pasos
```bash
sam build
sam deploy --guided
```
Ingresa valores para parámetros (StageName, Environment, claves). Tras el deploy se imprime la `ApiUrl` (Output).

### Endpoints en Lambda
Si StageName=dev:
```
GET https://<api-id>.execute-api.<region>.amazonaws.com/dev/health
POST .../dev/agendar
```

### Recomendaciones Lambda
1. Mantener `psycopg2-binary` (ya presente) para evitar compilaciones nativas.
2. Conexiones DB: migrar a HTTP (Supabase) o usar pooling ligero (futuro).
3. Métricas en memoria son efímeras (se reinician en cold start): para métricas persistentes usar CloudWatch Custom Metrics.

---

## 📈 Métricas y Observabilidad

Endpoints:
- `GET /metrics` -> JSON con counters y gauges (uso local).
- `GET /metrics/prometheus` -> Texto estilo Prometheus (experimental, reinicia con cada cold start en Lambda).

Counters relevantes (ejemplos):
- `citas_creadas`
- `citas_tipo_PRIMERAVEZ`, `citas_tipo_CONTROL`, `citas_tipo_ACONDICIONAMIENTO`
- `citas_error_crear`, `citas_error_backend`
- `saludtools_auth_attempt`, `saludtools_auth_success`, `saludtools_auth_error`
- `citas_412` (diagnóstico de payload inválido, debería quedarse en 0 ahora)
- `rate_limited`

Formato Prometheus generado dinámicamente (no requiere lib externa). Para scraping en producción se sugiere mover a CloudWatch o un Exporter centralizado.

---

## 🛡️ Rate Limiting

Implementado rate limit in-memory: máximo 3 solicitudes de agendamiento por documento en una ventana de 60 segundos. Respuesta 429 JSON si se excede. En Lambda (serverless) este conteo sería por instancia (no global); para producción multi-invocación usar DynamoDB (token bucket) o Redis.

---

## 🧪 Tipos de Cita Fisioterapia Controlados

El chatbot solo permite: `PRIMERAVEZ`, `CONTROL`, `ACONDICIONAMIENTO`.
Mapeo en `app/config.py` (función `mapear_tipo_fisioterapia`). Servicios restringidos (p.ej. suelo pélvico, hidroterapia) se filtran y redirigen a un tipo válido.

Test rápido:
```bash
python test_mapear_tipo_fisioterapia.py
```

---

## 🚀 Próximos Pasos Sugeridos
1. Persistir métricas críticas en CloudWatch.
2. DynamoDB para rate limit y contadores duraderos.
3. Notificaciones recordatorio (EventBridge + Lambda).
4. Pipeline CI/CD (GitHub Actions + SAM deploy).
5. Exportar logs estructurados (JSON) para analítica.

- **Experiencia conversacional natural** con IA especializada en salud.
- **Arquitectura de producción** escalable y robusta.
- **Modo desarrollo seguro** sin impactar datos médicos reales.
- **Compliance médico** con validaciones y auditoría completa.
- **ROI comprobado** con cálculos de ahorro y eficiencia operativa.

---

## 🚀 Para Producción

### Checklist de Deploy:
1. ✅ **Credenciales Saludtools** obtenidas del equipo técnico
2. ✅ **Variables de entorno** configuradas en producción  
3. ✅ **AWS EC2** configurado con dominio y SSL
4. ✅ **Twilio WhatsApp** en modo producción (no sandbox)
5. ✅ **n8n** para automatización y notificaciones
6. ✅ **Supabase** para logs y métricas en tiempo real

### Costos mensuales estimados:
- **Total sistema**: $434,774.59 COP/mes
- **Twilio WhatsApp**: $205.13 COP por mensaje
- **OpenAI GPT**: $8,208.87 COP por millón de tokens
- **Infraestructura**: AWS + n8n + Supabase incluidos

---

## 📝 Créditos

Desarrollado por Alejandro Perez Davila con ayuda de GitHub Copilot.

---
## 🛡️ Notas Importantes

- **Ambiente QA**: Usa `https://saludtools.qa.carecloud.com.co/integration/` para pruebas
- **Ambiente PROD**: Usa `https://saludtools.carecloud.com.co/integration/` en producción
- **Tokens**: Los tokens de Saludtools expiran cada 12 horas (auto-renovación incluida)
- **Rate Limits**: Máximo 60 requests por minuto en QA, consultar límites de producción
- **Seguridad**: No compartas API Keys ni credenciales. Usa variables de entorno siempre.
- **HIPAA/LOPD**: Sistema diseñado para cumplir regulaciones de privacidad médica.

### Variables de entorno específicas de Saludtools

En tu archivo `.env` agrega (además de las claves):

```
SALUDTOOLS_DOCTOR_DOCUMENT_TYPE=1
SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER=55223626
SALUDTOOLS_CLINIC_ID=8  # Reemplaza este número con el ID real de la clínica
```

Para descubrir el ID real de la clínica ejecuta (con credenciales válidas cargadas):

```
python listar_parametricos.py
```

Si la sección "Clínicas" aparece vacía o el endpoint no existe, solicita al soporte de Saludtools el ID interno que debes usar en el campo `clinic` / `clinicId` al crear citas.