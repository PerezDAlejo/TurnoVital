# 🚀 GUÍA COMPLETA DE DESPLIEGUE Y TESTING - IPS REACT

**Fecha:** 13 de diciembre, 2025  
**Versión:** 2.0 - Post Optimización Ultrathink

---

## 📋 TABLA DE CONTENIDOS

1. [Testing Local](#testing-local)
2. [Testing con Twilio Sandbox](#testing-twilio-sandbox)
3. [Servicios Necesarios para Producción](#servicios-produccion)
4. [Despliegue a Producción](#despliegue-produccion)
5. [Monitoreo y Mantenimiento](#monitoreo)
6. [Troubleshooting](#troubleshooting)

---

## 🧪 TESTING LOCAL

### 1. Preparación del Entorno

```powershell
# 1.1 Activar entorno virtual
cd "C:\Users\User\Desktop\trabajo IPS\agendamiento citas\agendamiento-citas"
.\.venv\Scripts\Activate.ps1

# 1.2 Verificar variables de entorno
Get-Content .env

# Variables críticas:
#   - OPENAI_API_KEY
#   - GOOGLE_API_KEY (Gemini)
#   - SUPABASE_URL
#   - SUPABASE_KEY
#   - TWILIO_ACCOUNT_SID
#   - TWILIO_AUTH_TOKEN
#   - TWILIO_WHATSAPP_NUMBER
#   - SALUDTOOLS_API_KEY
#   - SALUDTOOLS_SECRET
#   - SALUDTOOLS_CLINIC_ID

# 1.3 Verificar instalación de Tesseract
tesseract --version
# Esperado: Tesseract 5.0+ con español

# Si no está instalado:
.\instalar_tesseract_corregido.ps1
```

### 2. Ejecutar Suite de Testing Unificado

```powershell
# 2.1 Testing completo del sistema
python tests\test_suite_produccion.py

# Output esperado:
# ✅ TODOS LOS TESTS PASARON (100%)
# Sistema listo para producción

# 2.2 Tests específicos de correcciones
python tests\test_correcciones_completas.py

# 2.3 Tests de integración Gemini
python tests\test_gemini_adapter.py

# 2.4 Tests de integración completa
python tests\test_integracion_completa.py
```

### 3. Iniciar Servidor Local

```powershell
# 3.1 Método 1: Script directo
python run_server.py

# 3.2 Método 2: Uvicorn directo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Verificar endpoints:
# - Health: http://localhost:8000/health
# - Docs: http://localhost:8000/docs
# - Metrics: http://localhost:8000/metrics
```

### 4. Testing de Endpoints API

```powershell
# 4.1 Health check
Invoke-WebRequest -Uri "http://localhost:8000/health" -Method GET

# 4.2 Listar citas (requiere Supabase)
Invoke-WebRequest -Uri "http://localhost:8000/citas/" -Method GET

# 4.3 Métricas del sistema
Invoke-WebRequest -Uri "http://localhost:8000/metrics" -Method GET
```

---

## 📱 TESTING CON TWILIO SANDBOX

### 1. Configurar Túnel Ngrok

```powershell
# 1.1 Iniciar ngrok con script mejorado
python iniciar_ngrok.py

# Output esperado:
# ╔════════════════════════════════════════════════════════════════╗
# ║          🚀 NGROK URL ACTIVA - IPS REACT                      ║
# ╚════════════════════════════════════════════════════════════════╝
# 
# 📋 URL Pública: https://xxxx-xx-xxx.ngrok-free.app
# 
# 🔧 CONFIGURACIÓN TWILIO:
# 1. Ir a: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox
# 2. En "WHEN A MESSAGE COMES IN":
#    URL: https://xxxx-xx-xxx.ngrok-free.app/webhook/twilio
#    Method: POST

# 1.2 Alternativa: Ngrok manual
ngrok http 8000
```

### 2. Configurar Webhook en Twilio

#### Opción A: Twilio Sandbox (Desarrollo)

```
1. Ir a: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox

2. Configurar webhook:
   - WHEN A MESSAGE COMES IN:
     * URL: https://tu-ngrok-url.ngrok-free.app/webhook/twilio
     * Method: POST
   
3. Guardar cambios

4. Obtener código de sandbox:
   - Enviar mensaje desde tu WhatsApp personal
   - Formato: "join <código-sandbox>"
   - Ej: "join happy-tiger-1234"
```

#### Opción B: WhatsApp Business API (Producción)

```
1. Crear cuenta Meta Business Manager
2. Registrar número de teléfono
3. Verificar dominio
4. Configurar webhook:
   - URL: https://tu-dominio.com/webhook/twilio
   - Verify Token: (configurar en .env)
5. Suscribirse a eventos: messages
```

### 3. Escenarios de Testing con Twilio

#### Escenario 1: Agendamiento Simple

```
WhatsApp (Usuario):
> Hola, quiero agendar fisioterapia

Bot:
> ¡Hola! 👋 Bienvenido a IPS React...
> Para comenzar, ¿cuál es tu número de documento?

Usuario:
> 1234567890

Bot:
> Gracias. ¿Cuál es tu nombre completo?

... (flujo continúa)
```

#### Escenario 2: Datos Completos en un Mensaje

```
WhatsApp (Usuario):
> Hola, quiero fisioterapia de control.
> Cédula: 1234567890
> Nombre: Juan Pérez
> Fecha nacimiento: 15/03/1990
> EPS: Sura
> Celular: 3001234567
> Email: juan@test.com
> Dirección: Calle 10 #20-30
> Emergencia: María López, 3009876543, madre
> Quiero este viernes 10am con Miguel

Bot:
> ¡Perfecto! He recopilado toda tu información...
> [muestra resumen]
> ¿Confirmas los datos?
```

#### Escenario 3: Orden Médica (OCR)

```
WhatsApp (Usuario):
> [envía imagen de orden médica]

Bot:
> 📄 Analizando orden médica...
> 
> ✅ Orden procesada:
> - Tipo: Fisioterapia ortopédica
> - Sesiones: 10
> - EPS: Sura
> 
> ¿Los datos son correctos?
```

#### Escenario 4: Póliza sin Convenio

```
WhatsApp (Usuario):
> Tengo póliza Colpatria

Bot:
> ⚠️ IMPORTANTE:
> La póliza Colpatria NO tiene convenio con IPS React.
> Debes pagar tarifa particular: $60,000
> 
> ¿Cómo quieres pagar?
> 1️⃣ Póliza/EPS (presencial)
> 2️⃣ Particular - Efectivo/Tarjeta
> 3️⃣ Particular - Transferencia
```

#### Escenario 5: Rehabilitación Cardíaca

```
WhatsApp (Usuario):
> Quiero fisioterapia cardíaca con Diego Mosquera

Bot:
> ⚠️ Diego Andres Mosquera Torres no atiende rehabilitación cardíaca.
> 
> Fisioterapeutas especializados:
> - Diana Daniella Arana Carvalho
> - Ana Isabel Palacio Botero
> - Adriana Acevedo Agudelo
> 
> ¿Con cuál deseas agendar?
```

#### Escenario 6: Escalamiento a Secretaria

```
WhatsApp (Usuario):
> Quiero pagar con transferencia

Bot:
> 📞 Conectando con secretaria para gestionar transferencia...
> Te contactaremos en breve.

[Sistema notifica a secretaria disponible]

Secretaria (WhatsApp):
> 🆘 NUEVO CASO ESCALADO
> 
> Razón: Pago por transferencia
> Paciente: Juan Pérez (3001234567)
> 
> Datos recopilados:
> - Documento: 1234567890
> - Tipo cita: Fisioterapia control
> ...
> 
> Responde 'ATENDIDO' cuando contactes al paciente.
```

### 4. Validación de Flujos

**Checklist de Testing:**

- [ ] ✅ Bot responde a primer mensaje
- [ ] ✅ Recopila datos paso a paso
- [ ] ✅ Acepta datos completos en un mensaje
- [ ] ✅ Procesa imágenes OCR correctamente
- [ ] ✅ Detecta pólizas sin convenio
- [ ] ✅ Valida fisioterapeutas cardíacos
- [ ] ✅ Respeta restricción Coomeva 9am-4pm
- [ ] ✅ Excepción cardíaca Coomeva funciona
- [ ] ✅ Solicita contacto de emergencia
- [ ] ✅ Solicita método de pago explícito
- [ ] ✅ Escala a secretaria cuando corresponde
- [ ] ✅ Maneja reintentos OCR (hasta 3)
- [ ] ✅ Crea cita en Supabase
- [ ] ✅ Crea cita en SaludTools con appointmentType correcto
- [ ] ✅ Cita múltiple (3+ citas en un mensaje)

---

## 🌐 SERVICIOS NECESARIOS PARA PRODUCCIÓN

### 1. Infraestructura

#### Opción A: Servidor Tradicional (Recomendado para inicio)

```yaml
Proveedor: DigitalOcean Droplet
Plan: Basic - $24/mes
Specs:
  - 4GB RAM
  - 2 vCPUs
  - 80GB SSD
  - Ubuntu 22.04 LTS

Configuración:
  1. Crear Droplet
  2. Instalar Docker
  3. Configurar Nginx reverse proxy
  4. SSL con Let's Encrypt
  5. Deploy con Docker Compose
```

**Comandos de Setup:**

```bash
# 1. Actualizar sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 3. Instalar Docker Compose
sudo apt install docker-compose -y

# 4. Instalar Nginx
sudo apt install nginx -y

# 5. Instalar Certbot (SSL)
sudo apt install certbot python3-certbot-nginx -y

# 6. Clonar repositorio
git clone <tu-repo>.git /opt/ips-react
cd /opt/ips-react

# 7. Configurar .env
nano .env
# (copiar variables de producción)

# 8. Iniciar con Docker
docker-compose up -d

# 9. Configurar SSL
sudo certbot --nginx -d tu-dominio.com
```

#### Opción B: Serverless (Escalabilidad automática)

```yaml
Proveedor: AWS Lambda + API Gateway
Costo: Pay-per-use (~$0.20 por millón de requests)

Ventajas:
  - Auto-scaling
  - Sin gestión de servidor
  - Alta disponibilidad

Desventajas:
  - Cold starts (2-5 segundos primer request)
  - Límite 15 minutos por request
  - Complejidad configuración

Configuración:
  1. Crear función Lambda (Python 3.11)
  2. Configurar API Gateway
  3. Subir código como ZIP
  4. Configurar variables de entorno
  5. Conectar con VPC para Supabase
```

### 2. Base de Datos

#### Actual: Supabase PostgreSQL

```yaml
Plan: Pro - $25/mes
Specs:
  - 8GB database
  - 50GB bandwidth
  - Backup automático
  - RLS (Row Level Security)

Connection:
  Host: db.civjocyxmflmljyyszwy.supabase.co
  Port: 5432
  Database: postgres
  User: postgres
  Password: IPSreact12300.*

Migración requerida:
  1. Aplicar migrations/002_agregar_campos_contacto_pago.sql
  2. Habilitar RLS en todas las tablas
  3. Configurar políticas de acceso
```

**Aplicar Migración:**

```sql
-- 1. Abrir Supabase SQL Editor
-- 2. Copiar contenido de migrations/002_agregar_campos_contacto_pago.sql
-- 3. Ejecutar
-- 4. Verificar:

SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name IN ('pacientes', 'citas')
AND (column_name LIKE '%contacto%' 
     OR column_name LIKE '%metodo_pago%' 
     OR column_name LIKE '%plan%');

-- Esperado: 6 columnas nuevas
```

### 3. APIs Externas

#### OpenAI (GPT-4o)

```yaml
Plan: Pay-as-you-go
Costo: ~$5-15/día (800 agendamientos/mes)
Uso: Fallback cuando Gemini falla

API Key: sk-...
Endpoint: https://api.openai.com/v1/chat/completions
Model: gpt-4o

Variables .env:
  OPENAI_API_KEY=sk-...
```

#### Google Gemini (Principal)

```yaml
Plan: Free tier (60 requests/min)
Costo: $0 (hasta límite)
Ahorro: 88% vs GPT-4o

API Key: (obtener en Google AI Studio)
Endpoint: https://generativelanguage.googleapis.com
Model: gemini-2.0-flash-exp

Variables .env:
  GOOGLE_API_KEY=AIza...
```

**Obtener API Key:**

```
1. Ir a: https://makersuite.google.com/app/apikey
2. Crear nuevo API key
3. Copiar y agregar a .env
```

#### Twilio (WhatsApp)

```yaml
Plan: Pay-as-you-go
Costo: $0.005/mensaje
Estimado: $20/mes (800 agendamientos * 5 mensajes)

Credentials:
  Account SID: AC...
  Auth Token: ...
  WhatsApp Number: +14155238886 (sandbox)
  WhatsApp Number: +57... (producción)

Variables .env:
  TWILIO_ACCOUNT_SID=AC...
  TWILIO_AUTH_TOKEN=...
  TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

**Setup WhatsApp Business (Producción):**

```
1. Registrarse en Meta Business Manager
2. Crear aplicación WhatsApp Business
3. Registrar número de teléfono
4. Verificar dominio empresarial
5. Configurar webhook en Twilio
6. Migrar de sandbox a número real
```

#### SaludTools

```yaml
Costo: Incluido en contrato IPS
API: https://api.saludtools.com

Credentials:
  API Key: STAKOAGQgyIGE2qpC5oYiI8f3KrTET
  Secret: LzrDT+h3rO6aVSluTV0q81v9loGzs++B/STugq2emOY=
  Clinic ID: 8 (CONFIRMAR)

Variables .env:
  SALUDTOOLS_API_KEY=STAKO...
  SALUDTOOLS_SECRET=LzrDT...
  SALUDTOOLS_CLINIC_ID=8

Endpoints usados:
  - POST /api/v1/appointments (crear cita)
  - GET /api/v1/appointments/{id} (leer cita)
  - PUT /api/v1/appointments/{id} (actualizar)
  - DELETE /api/v1/appointments/{id} (cancelar)
```

### 4. OCR (Tesseract)

#### Local (Desarrollo)

```powershell
# Instalación Windows
.\instalar_tesseract_corregido.ps1

# Verificar
tesseract --version

# Path en .env
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
```

#### Producción (Linux)

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-spa -y

# Verificar
tesseract --version

# No requiere variable .env (detecta automáticamente)
```

#### Alternativa Cloud (Opcional)

```yaml
Google Cloud Vision API:
  Costo: $1.50 por 1000 imágenes
  Precisión: 95%+
  
AWS Textract:
  Costo: $1.50 por 1000 páginas
  Soporte tablas/formularios
  
Azure Computer Vision:
  Costo: $1.00 por 1000 transacciones
  Incluye análisis contextual
```

### 5. Almacenamiento de Archivos

#### Actual: secure_storage/ (Local)

```
Ubicación: ./secure_storage/2025/
Problema: No persistente en serverless
Solución: Migrar a cloud storage
```

#### Recomendado: AWS S3

```yaml
Plan: Pay-as-you-go
Costo: ~$1/mes (estimado 1000 órdenes médicas)

Configuración:
  1. Crear bucket: ips-react-ordenes-medicas
  2. Configurar acceso IAM
  3. Habilitar encriptación AES-256
  4. Configurar lifecycle (eliminar después 90 días)

Variables .env:
  AWS_ACCESS_KEY_ID=AKIA...
  AWS_SECRET_ACCESS_KEY=...
  AWS_S3_BUCKET=ips-react-ordenes-medicas
  AWS_REGION=us-east-1
```

**Modificación Código:**

```python
# app/document_accumulator.py

import boto3

s3 = boto3.client('s3')

def guardar_archivo_s3(file_data, filename):
    bucket = os.getenv('AWS_S3_BUCKET')
    s3.put_object(
        Bucket=bucket,
        Key=f'ordenes/{filename}',
        Body=file_data,
        ServerSideEncryption='AES256'
    )
```

### 6. Monitoreo y Logs

#### Sentry (Errores)

```yaml
Plan: Developer - $26/mes
Eventos: 50k/mes

Configuración:
  1. Crear proyecto en sentry.io
  2. Obtener DSN
  3. Instalar SDK: pip install sentry-sdk
  4. Configurar en app/main.py

Variables .env:
  SENTRY_DSN=https://...@sentry.io/...
```

```python
# app/main.py
import sentry_sdk

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    traces_sample_rate=1.0,
    environment="production"
)
```

#### CloudWatch (AWS)

```yaml
Costo: $0.50/GB logs
Configuración automática con Lambda
Dashboards incluidos
```

#### Supabase Logs

```yaml
Incluido en plan Pro
Logs de queries SQL
Dashboard performance
```

### 7. Variables de Entorno (Resumen)

**Archivo .env completo para producción:**

```ini
# ========================================
# GENERAL
# ========================================
ENV=production
DEBUG=false
LOG_LEVEL=info

# ========================================
# OPENAI (Fallback)
# ========================================
OPENAI_API_KEY=sk-proj-...

# ========================================
# GEMINI (Principal)
# ========================================
GOOGLE_API_KEY=AIza...

# ========================================
# SUPABASE
# ========================================
SUPABASE_URL=https://civjocyxmflmljyyszwy.supabase.co
SUPABASE_KEY=eyJhbGc...
DATABASE_URL=postgresql://postgres:IPSreact12300.*@db.civjocyxmflmljyyszwy.supabase.co:5432/postgres

# ========================================
# TWILIO
# ========================================
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+57...

# ========================================
# SALUDTOOLS
# ========================================
SALUDTOOLS_API_KEY=STAKOAGQgyIGE2qpC5oYiI8f3KrTET
SALUDTOOLS_SECRET=LzrDT+h3rO6aVSluTV0q81v9loGzs++B/STugq2emOY=
SALUDTOOLS_CLINIC_ID=8

# ========================================
# OCR
# ========================================
TESSERACT_PATH=/usr/bin/tesseract  # Linux
# TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe  # Windows

# ========================================
# AWS (Opcional - si usas S3)
# ========================================
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=ips-react-ordenes-medicas
AWS_REGION=us-east-1

# ========================================
# MONITORING (Opcional)
# ========================================
SENTRY_DSN=https://...@sentry.io/...

# ========================================
# SECRETARIAS (WhatsApp)
# ========================================
SECRETARY_NUMBERS=+573207143068,+573002007277
```

---

## 🚀 DESPLIEGUE A PRODUCCIÓN

### Opción 1: Deploy con Docker (Recomendado)

#### 1. Crear Dockerfile

```dockerfile
# Crear: Dockerfile
FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements
COPY Requirements.txt .
RUN pip install --no-cache-dir -r Requirements.txt

# Copiar código
COPY . .

# Exponer puerto
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2. Crear docker-compose.yml

```yaml
# Crear: docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./secure_storage:/app/secure_storage
      - ./logs:/app/logs
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - web
    restart: always
```

#### 3. Configurar Nginx

```nginx
# Crear: nginx.conf
server {
    listen 80;
    server_name tu-dominio.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name tu-dominio.com;
    
    # SSL certificates
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # Proxy to FastAPI
    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (si necesitas)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### 4. Deploy

```bash
# 1. Clonar en servidor
git clone <tu-repo>.git /opt/ips-react
cd /opt/ips-react

# 2. Configurar .env
nano .env
# (pegar variables de producción)

# 3. Build y start
docker-compose up -d --build

# 4. Verificar logs
docker-compose logs -f web

# 5. Verificar health
curl http://localhost:8000/health
```

### Opción 2: Deploy Manual (Linux)

```bash
# 1. Instalar Python
sudo apt install python3.11 python3.11-venv -y

# 2. Crear entorno virtual
cd /opt/ips-react
python3.11 -m venv venv
source venv/bin/activate

# 3. Instalar dependencias
pip install -r Requirements.txt

# 4. Instalar Tesseract
sudo apt install tesseract-ocr tesseract-ocr-spa -y

# 5. Configurar systemd service
sudo nano /etc/systemd/system/ips-react.service
```

```ini
[Unit]
Description=IPS React WhatsApp Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ips-react
Environment="PATH=/opt/ips-react/venv/bin"
ExecStart=/opt/ips-react/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 6. Iniciar servicio
sudo systemctl daemon-reload
sudo systemctl enable ips-react
sudo systemctl start ips-react

# 7. Verificar
sudo systemctl status ips-react
```

---

## 📊 MONITOREO Y MANTENIMIENTO

### 1. Health Checks

```bash
# Health endpoint
curl https://tu-dominio.com/health

# Métricas
curl https://tu-dominio.com/metrics

# Logs recientes
docker-compose logs --tail=100 -f web

# O con systemd:
sudo journalctl -u ips-react -f
```

### 2. Queries de Monitoreo Supabase

```sql
-- Citas creadas hoy
SELECT COUNT(*) 
FROM citas 
WHERE DATE(created_at) = CURRENT_DATE;

-- Pólizas sin convenio detectadas
SELECT entidad_eps, COUNT(*) 
FROM pacientes 
WHERE entidad_eps IN (
  'Colpatria', 'MedPlus', 'Colmédica', 'Medisanitas',
  'SSI Grupo', 'Mapfre', 'Previsora', 'Liberty',
  'Pan American', 'MetLife', 'SBS Seguros', 'Cardif'
)
GROUP BY entidad_eps;

-- Métodos de pago
SELECT metodo_pago, COUNT(*) 
FROM citas 
GROUP BY metodo_pago;

-- Escalamientos hoy
SELECT COUNT(*) 
FROM escalamientos 
WHERE DATE(created_at) = CURRENT_DATE;

-- OCR reintentos
SELECT phone_number, error_type, attempt_count 
FROM ocr_retry_attempts 
WHERE DATE(created_at) = CURRENT_DATE
ORDER BY created_at DESC;
```

### 3. Alertas Críticas

**Configurar en Sentry/CloudWatch:**

- Error rate > 5%
- Response time > 5s
- Disponibilidad < 99%
- Gemini fallback rate > 20%
- Escalamientos fallidos > 3/día

### 4. Backups

```bash
# Backup Supabase (automático en plan Pro)
# Frecuencia: Diario
# Retención: 30 días

# Backup manual archivos
tar -czf backup-$(date +%Y%m%d).tar.gz secure_storage/ logs/ .env
```

---

## 🔧 TROUBLESHOOTING

### Problema 1: Bot no responde en WhatsApp

**Diagnóstico:**

```bash
# 1. Verificar servidor corriendo
curl http://localhost:8000/health

# 2. Verificar ngrok activo
curl http://localhost:4040/api/tunnels

# 3. Verificar webhook Twilio
# Ir a: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox
# Verificar URL webhook actualizada

# 4. Ver logs en tiempo real
tail -f logs/system/app.log
```

**Soluciones:**

- Reiniciar servidor: `docker-compose restart web`
- Reiniciar ngrok: `python iniciar_ngrok.py`
- Verificar .env tiene todas las variables
- Probar endpoint directo: `POST http://tu-url/webhook/twilio`

### Problema 2: OCR no detecta texto

**Diagnóstico:**

```bash
# Verificar Tesseract instalado
tesseract --version

# Probar OCR directo
tesseract test_images/orden.jpg output -l spa
```

**Soluciones:**

- Instalar Tesseract: `sudo apt install tesseract-ocr-spa`
- Verificar TESSERACT_PATH en .env
- Probar con imagen de mejor calidad
- Verificar sistema de reintentos (hasta 3 intentos)

### Problema 3: SaludTools devuelve error 412

**Diagnóstico:**

```python
# Verificar appointmentType
python -c "from app.config import mapear_tipo_fisioterapia; print(mapear_tipo_fisioterapia('primera vez'))"

# Esperado: "Cita De Primera Vez"
# NO: "PRIMERAVEZ"
```

**Soluciones:**

- Verificar correcciones aplicadas
- appointmentType debe ser exacto: "Cita De Primera Vez", "Cita De Control", "Acondicionamiento Fisico", "Continuidad De Orden"
- Verificar SALUDTOOLS_CLINIC_ID correcto

### Problema 4: Gemini quota exceeded

**Diagnóstico:**

```bash
# Ver logs de fallback
grep "FALLBACK TO OPENAI" logs/system/app.log

# Si muchos fallbacks: Gemini llegó al límite
```

**Soluciones:**

- Esperar 1 minuto (límite: 60 req/min)
- Verificar OPENAI_API_KEY configurado (fallback automático)
- Considerar plan pago Gemini si uso muy alto

### Problema 5: Supabase connection timeout

**Diagnóstico:**

```bash
# Probar conexión directa
psql postgresql://postgres:IPSreact12300.*@db.civjocyxmflmljyyszwy.supabase.co:5432/postgres
```

**Soluciones:**

- Verificar IP del servidor no bloqueada en Supabase
- Verificar DATABASE_URL en .env
- Revisar límites de conexiones (max 60 en plan Pro)

---

## ✅ CHECKLIST FINAL DESPLIEGUE

**Pre-Despliegue:**

- [ ] Tests locales pasando (100%)
- [ ] Testing Twilio sandbox exitoso
- [ ] Variables .env producción configuradas
- [ ] Migración SQL aplicada en Supabase
- [ ] RLS habilitado en todas las tablas
- [ ] Dominio configurado y SSL activo
- [ ] Backup de datos actual

**Durante Despliegue:**

- [ ] Servidor aprovisionado
- [ ] Docker/Python instalado
- [ ] Código clonado
- [ ] .env configurado
- [ ] Servicio iniciado
- [ ] Health check pasando
- [ ] Nginx configurado
- [ ] SSL certificado

**Post-Despliegue:**

- [ ] Webhook Twilio apuntando a producción
- [ ] WhatsApp Business número verificado (producción real)
- [ ] Sentry/monitoreo configurado
- [ ] Tests en producción exitosos
- [ ] Documentación actualizada
- [ ] Equipo capacitado

**Validación Final:**

- [ ] Agendamiento simple funciona
- [ ] Agendamiento múltiple funciona
- [ ] OCR procesa órdenes médicas
- [ ] Escalamiento a secretaria funciona
- [ ] Pólizas sin convenio detectadas
- [ ] Validación fisioterapeutas cardíacos
- [ ] Restricción Coomeva funciona
- [ ] Contacto emergencia solicitado
- [ ] Método pago explícito
- [ ] Citas creadas en Supabase
- [ ] Citas creadas en SaludTools
- [ ] appointmentType correcto

---

## 📞 SOPORTE

**Documentación:**

- README.md
- docs/CORRECCIONES_COMPLETADAS_FINAL.md
- docs/CHECKLIST_LANZAMIENTO_PRODUCCION.md
- docs/ONE_PAGER.md

**Contacto:**

- Twilio Support: https://support.twilio.com
- Supabase Support: https://supabase.com/support
- SaludTools: (contacto interno IPS)

---

**Fecha última actualización:** 13 de diciembre, 2025  
**Versión:** 2.0 - Post Optimización Ultrathink  
**Estado:** ✅ Listo para producción
