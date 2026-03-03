# 🚨 CHECKLIST COMPLETO - LANZAMIENTO PRODUCCIÓN
## IPS REACT - Sistema de Agendamiento WhatsApp
**Fecha Lanzamiento:** 19 de Noviembre 2025, 5:00 AM
**Tiempo Restante:** ~16 horas

---

## 📋 PARTE 1: INFORMACIÓN REQUERIDA DE LA IPS

### 🔴 CRÍTICO - OBTENER HOY

#### 1. NÚMEROS DE TELÉFONO
```
┌─────────────────────────────────────────────────────────────┐
│ ✅ Número Principal WhatsApp IPS                            │
│    ├─ Número actual: ___________________________           │
│    ├─ Operador: _____________________________________       │
│    └─ Tiene WhatsApp Business? ☐ Sí  ☐ No                  │
│                                                             │
│ ✅ Secretaria 1 (Principal)                                 │
│    ├─ Nombre: _______________________________________       │
│    ├─ WhatsApp: +57 _____________________________          │
│    └─ Horario disponibilidad: ______________________       │
│                                                             │
│ ✅ Secretaria 2 (Backup)                                    │
│    ├─ Nombre: _______________________________________       │
│    ├─ WhatsApp: +57 _____________________________          │
│    └─ Horario disponibilidad: ______________________       │
│                                                             │
│ ⚠️ Números Adicionales (Opcional)                           │
│    ├─ Teléfono oficina: _____________________________      │
│    ├─ Emergencias: ___________________________________      │
│    └─ Soporte técnico: _______________________________     │
└─────────────────────────────────────────────────────────────┘
```

#### 2. CREDENCIALES SALUDTOOLS REAL
```
┌─────────────────────────────────────────────────────────────┐
│ ✅ Saludtools Producción                                    │
│    ├─ Usuario/Email: _________________________________      │
│    ├─ Contraseña: ____________________________________      │
│    ├─ API Key: _______________________________________      │
│    ├─ API Secret: ____________________________________      │
│    ├─ Clinic ID: _____________________________________      │
│    └─ URL Base: https://api.saludtools.com (confirmar)     │
│                                                             │
│ ⚠️ IMPORTANTE: Estas son las credenciales REALES            │
│    No son las de sandbox que tienes actualmente            │
└─────────────────────────────────────────────────────────────┘
```

#### 3. INFORMACIÓN DE FISIOTERAPEUTAS
```
┌─────────────────────────────────────────────────────────────┐
│ ✅ Documento de Identidad de cada Fisioterapeuta           │
│                                                             │
│ 1. Adriana Acevedo Agudelo                                 │
│    └─ CC: _____________________________________________     │
│                                                             │
│ 2. Ana Isabel Palacio Botero                               │
│    └─ CC: _____________________________________________     │
│                                                             │
│ 3. Diana Daniella Arana Carvalho                           │
│    └─ CC: _____________________________________________     │
│                                                             │
│ 4. Diego Andres Mosquera Torres                            │
│    └─ CC: _____________________________________________     │
│                                                             │
│ 5. Veronica Echeverri Restrepo                             │
│    └─ CC: _____________________________________________     │
│                                                             │
│ 6. Miguel Ignacio Moreno Cardona                           │
│    └─ CC: _____________________________________________     │
│                                                             │
│ 7. Daniela Patiño Londoño                                  │
│    └─ CC: _____________________________________________     │
│                                                             │
│ ⚠️ NOTA: Estos documentos se usan en Saludtools para       │
│    identificar al profesional al crear citas               │
└─────────────────────────────────────────────────────────────┘
```

#### 4. INFORMACIÓN MÉDICOS
```
┌─────────────────────────────────────────────────────────────┐
│ ✅ Documentos de Identidad Médicos                          │
│                                                             │
│ 1. Dr. Jorge Ivan Palacio Uribe (Medicina del Deporte)    │
│    └─ CC: _____________________________________________     │
│                                                             │
│ 2. Dr. Diego Fernando Benitez España (Endocrinología)     │
│    └─ CC: _____________________________________________     │
│                                                             │
│ 3. Dr. Jaime Valencia (Ortopedia)                          │
│    └─ CC: _____________________________________________     │
└─────────────────────────────────────────────────────────────┘
```

#### 5. INFORMACIÓN CORPORATIVA IPS
```
┌─────────────────────────────────────────────────────────────┐
│ ✅ Datos Legales y Administrativos                          │
│                                                             │
│ Razón Social: _________________________________________     │
│ NIT: ___________________________________________________    │
│ Dirección Completa: Calle 10 32-115, Medellín (confirmar) │
│ Email Corporativo: _____________________________________    │
│ Sitio Web: _____________________________________________    │
│                                                             │
│ ✅ Cuenta Bancaria (para transferencias)                   │
│ Banco: __________________________________________________   │
│ Tipo de Cuenta: ☐ Ahorros  ☐ Corriente                     │
│ Número de Cuenta: _______________________________________   │
│ Titular: ________________________________________________   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 PARTE 2: CUENTAS Y SERVICIOS A CREAR HOY

### 🟢 PASO 1: GMAIL CORPORATIVO
```
┌─────────────────────────────────────────────────────────────┐
│ CREAR CUENTA GMAIL                                          │
│                                                             │
│ Sugerencias de email:                                       │
│ • ipsreact.agendamiento@gmail.com                           │
│ • ipsreact.sistema@gmail.com                                │
│ • chatbot.ipsreact@gmail.com                                │
│                                                             │
│ USAR PARA:                                                  │
│ ✓ OpenAI cuenta                                             │
│ ✓ AWS cuenta                                                │
│ ✓ Meta Business Manager                                     │
│ ✓ Twilio/otras APIs                                         │
│ ✓ Notificaciones del sistema                               │
│                                                             │
│ ⚠️ IMPORTANTE:                                               │
│ • Guardar contraseña en lugar seguro                        │
│ • Activar verificación en 2 pasos                           │
│ • Anotar email de recuperación                              │
└─────────────────────────────────────────────────────────────┘
```

### 🟢 PASO 2: OPENAI (GPT-4O-MINI)
```
┌─────────────────────────────────────────────────────────────┐
│ CREAR CUENTA OPENAI                                         │
│ URL: https://platform.openai.com/signup                     │
│                                                             │
│ 1. Registrarse con gmail corporativo                        │
│ 2. Verificar email                                          │
│ 3. Ir a: API Keys → Create new secret key                  │
│ 4. Copiar API Key (solo se muestra una vez)                │
│ 5. Agregar método de pago (tarjeta crédito/débito)         │
│                                                             │
│ COSTO ESTIMADO:                                             │
│ • GPT-4o-mini: $0.150 / 1M tokens input                     │
│ • GPT-4o-mini: $0.600 / 1M tokens output                    │
│ • Estimado mensual: $10-30 USD (depende del volumen)        │
│                                                             │
│ GUARDAR:                                                    │
│ API Key: sk-proj-_____________________________________      │
└─────────────────────────────────────────────────────────────┘
```

### 🟢 PASO 3: META BUSINESS (WHATSAPP BUSINESS API)
```
┌─────────────────────────────────────────────────────────────┐
│ CONFIGURAR WHATSAPP BUSINESS API                            │
│                                                             │
│ OPCIÓN A - Meta Business (Recomendado para producción):    │
│ ────────────────────────────────────────────────────────────│
│ 1. Ir a: https://business.facebook.com/                     │
│ 2. Crear Business Manager                                   │
│ 3. Verificar empresa (documentos IPS)                       │
│ 4. Agregar WhatsApp Business API                            │
│ 5. Verificar número de teléfono IPS                         │
│ 6. Obtener credenciales:                                    │
│    • Phone Number ID: _________________________________     │
│    • WhatsApp Business Account ID: ____________________     │
│    • Access Token: ____________________________________     │
│                                                             │
│ ⚠️ PROCESO PUEDE TOMAR: 1-3 días para aprobación            │
│                                                             │
│ OPCIÓN B - Twilio (Más rápido para lanzamiento):           │
│ ────────────────────────────────────────────────────────────│
│ 1. Ir a: https://www.twilio.com/                            │
│ 2. Crear cuenta con gmail corporativo                       │
│ 3. Comprar número WhatsApp habilitado                       │
│ 4. Verificar el número actual de la IPS como remitente     │
│ 5. Obtener credenciales:                                    │
│    • Account SID: _____________________________________     │
│    • Auth Token: ______________________________________     │
│    • WhatsApp Number: whatsapp:+________________           │
│                                                             │
│ COSTO TWILIO:                                               │
│ • Número WhatsApp: ~$1-2 USD/mes                            │
│ • Mensajes: $0.005 USD por mensaje (entrada + salida)      │
│                                                             │
│ 💡 RECOMENDACIÓN: Empezar con Twilio HOY, migrar a Meta     │
│    cuando esté aprobado (1-3 días)                          │
└─────────────────────────────────────────────────────────────┘
```

### 🟢 PASO 4: AWS (SERVIDOR PRODUCCIÓN)
```
┌─────────────────────────────────────────────────────────────┐
│ CONFIGURAR AWS EC2                                          │
│                                                             │
│ 1. Crear cuenta AWS                                         │
│    URL: https://aws.amazon.com/                             │
│    Email: usar gmail corporativo                            │
│                                                             │
│ 2. Configurar método de pago (tarjeta)                      │
│                                                             │
│ 3. Lanzar instancia EC2:                                    │
│    Región: us-east-1 (Virginia) - más barata               │
│    Tipo: t3.small o t3.medium                               │
│    OS: Ubuntu 22.04 LTS                                     │
│    Almacenamiento: 20 GB GP3                                │
│                                                             │
│ 4. Configurar Security Group:                               │
│    • Puerto 22 (SSH) - Solo tu IP                          │
│    • Puerto 80 (HTTP)                                       │
│    • Puerto 443 (HTTPS)                                     │
│    • Puerto 8000 (FastAPI) - temporal                       │
│                                                             │
│ 5. Crear/Descargar Key Pair (.pem)                          │
│                                                             │
│ 6. Obtener IP pública:                                      │
│    IP Elástica: __.__.__.__ (anotar aquí)                   │
│                                                             │
│ COSTO ESTIMADO:                                             │
│ • t3.small: ~$15 USD/mes                                    │
│ • t3.medium: ~$30 USD/mes                                   │
│ • Transferencia datos: ~$5 USD/mes                          │
│ • Total: $20-40 USD/mes                                     │
│                                                             │
│ ⚠️ ALTERNATIVA MÁS RÁPIDA: Railway, Render, Heroku          │
│    (Más fácil de configurar pero un poco más caro)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 PARTE 3: CONFIGURACIÓN TÉCNICA (HOY TARDE/NOCHE)

### 🔧 TAREAS TÉCNICAS - ORDEN DE EJECUCIÓN

```
┌─────────────────────────────────────────────────────────────┐
│ HORA 13:00 - 15:00 | RECOLECCIÓN DE INFORMACIÓN            │
├─────────────────────────────────────────────────────────────┤
│ ☐ Obtener todos los datos de la lista PARTE 1              │
│ ☐ Verificar documentos de identidad fisioterapeutas        │
│ ☐ Confirmar credenciales Saludtools REAL                    │
│ ☐ Validar número WhatsApp actual de la IPS                 │
│ ☐ Obtener datos bancarios para transferencias              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ HORA 15:00 - 17:00 | CREACIÓN DE CUENTAS                   │
├─────────────────────────────────────────────────────────────┤
│ ☐ Crear Gmail corporativo                                  │
│ ☐ Crear cuenta OpenAI + obtener API Key                    │
│ ☐ Crear cuenta Twilio + comprar número WhatsApp            │
│ ☐ Crear cuenta AWS + lanzar EC2                            │
│ ☐ Iniciar proceso Meta Business (paralelo)                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ HORA 17:00 - 19:00 | CONFIGURACIÓN SERVIDOR AWS            │
├─────────────────────────────────────────────────────────────┤
│ ☐ Conectar a EC2 por SSH                                   │
│ ☐ Instalar Python 3.11+                                    │
│ ☐ Instalar dependencias del sistema                        │
│ ☐ Clonar repositorio del proyecto                          │
│ ☐ Instalar dependencias Python (requirements.txt)          │
│ ☐ Configurar variables de entorno (.env)                   │
│ ☐ Configurar Nginx como reverse proxy                      │
│ ☐ Configurar SSL con Let's Encrypt (opcional)              │
│ ☐ Configurar systemd para auto-inicio                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ HORA 19:00 - 21:00 | TESTING Y VALIDACIÓN                  │
├─────────────────────────────────────────────────────────────┤
│ ☐ Actualizar .env con credenciales REALES                  │
│ ☐ Probar conexión Saludtools producción                    │
│ ☐ Verificar OpenAI API funcionando                         │
│ ☐ Configurar webhook Twilio → servidor AWS                 │
│ ☐ Testing end-to-end desde WhatsApp                        │
│ ☐ Validar agendamiento en Saludtools real                  │
│ ☐ Probar escalamiento a secretarias                        │
│ ☐ Validar OCR con orden médica real                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ HORA 21:00 - 23:00 | AJUSTES FINALES Y MONITOREO           │
├─────────────────────────────────────────────────────────────┤
│ ☐ Configurar logs y alertas                                │
│ ☐ Documentar credenciales en lugar seguro                  │
│ ☐ Crear backup de configuración                            │
│ ☐ Testing final con usuarios reales (secretarias)          │
│ ☐ Validar horario Coomeva                                  │
│ ☐ Verificar todos los flujos críticos                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ HORA 03:00 - 05:00 | DESPLIEGUE FINAL Y GO-LIVE            │
├─────────────────────────────────────────────────────────────┤
│ ☐ Verificación final del sistema                           │
│ ☐ Reiniciar servicios                                      │
│ ☐ Verificar auto-inicio configurado                        │
│ ☐ Testing rápido de todos los flujos                       │
│ ☐ Sistema listo para recibir pacientes a las 5:00 AM       │
│ ☐ Monitorear primeras interacciones                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 PARTE 4: ARCHIVO .ENV PRODUCCIÓN

```env
# ═══════════════════════════════════════════════════════════
# CONFIGURACIÓN PRODUCCIÓN - IPS REACT
# Fecha: 19 Noviembre 2025
# ═══════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# OPENAI (GPT-4O-MINI)
# ─────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-proj-_________________________________
OPENAI_MODEL=gpt-4o-mini

# ─────────────────────────────────────────────────────────────
# TWILIO (WHATSAPP)
# ─────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID=AC___________________________________
TWILIO_AUTH_TOKEN=_______________________________________
TWILIO_WHATSAPP_NUMBER=whatsapp:+_______________________

# ─────────────────────────────────────────────────────────────
# SALUDTOOLS (PRODUCCIÓN - NO SANDBOX)
# ─────────────────────────────────────────────────────────────
SALUDTOOLS_API_KEY=______________________________________
SALUDTOOLS_API_SECRET=___________________________________
SALUDTOOLS_BASE_URL=https://api.saludtools.com
SALUDTOOLS_CLINIC_ID=____________________________________

# ─────────────────────────────────────────────────────────────
# BASE DE DATOS (SUPABASE OPCIONAL)
# ─────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://postgres:IPSreact12300.*@db.civjocyxmflmljyyszwy.supabase.co:5432/postgres

# ─────────────────────────────────────────────────────────────
# SECRETARIAS (ESCALAMIENTO)
# ─────────────────────────────────────────────────────────────
SECRETARIA_1_WHATSAPP=+57________________________________
SECRETARIA_1_NOMBRE=_____________________________________
SECRETARIA_2_WHATSAPP=+57________________________________
SECRETARIA_2_NOMBRE=_____________________________________

# ─────────────────────────────────────────────────────────────
# CONFIGURACIÓN GENERAL
# ─────────────────────────────────────────────────────────────
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
TIMEZONE=America/Bogota

# ─────────────────────────────────────────────────────────────
# DATOS BANCARIOS (TRANSFERENCIAS)
# ─────────────────────────────────────────────────────────────
BANCO_NOMBRE=________________________________________________
BANCO_TIPO_CUENTA=___________________________________________
BANCO_NUMERO=________________________________________________
BANCO_TITULAR=_______________________________________________
```

---

## 📋 PARTE 5: VALIDACIÓN FINAL - CHECKLIST

```
┌─────────────────────────────────────────────────────────────┐
│ ANTES DE LANZAMIENTO - VERIFICAR                           │
├─────────────────────────────────────────────────────────────┤
│ ☐ Servidor AWS respondiendo en puerto 80/443               │
│ ☐ Webhook Twilio configurado correctamente                 │
│ ☐ OpenAI API Key funcionando                               │
│ ☐ Saludtools PRODUCCIÓN conectado (no sandbox)             │
│ ☐ Base de datos opcional configurada                       │
│ ☐ Números de secretarias correctos                         │
│ ☐ OCR funcionando con órdenes médicas                       │
│ ☐ Sistema de logs activo                                   │
│ ☐ Auto-inicio configurado (systemd)                        │
│ ☐ Firewall configurado correctamente                       │
│                                                             │
│ TESTING FUNCIONAL:                                          │
│ ☐ Saludo inicial funciona                                  │
│ ☐ Agendamiento fisioterapia funciona                       │
│ ☐ Agendamiento múltiple funciona                           │
│ ☐ Escalamiento a secretarias funciona                      │
│ ☐ Validación Coomeva 9am-4pm funciona                      │
│ ☐ Pólizas sin convenio detectadas                          │
│ ☐ Fisioterapias no soportadas rechazadas                   │
│ ☐ Planes acondicionamiento correctos                       │
│ ☐ Citas se crean en Saludtools REAL                        │
│ ☐ Notificaciones WhatsApp llegan                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚨 CONTINGENCIAS Y PLAN B

```
┌─────────────────────────────────────────────────────────────┐
│ SI ALGO FALLA EN PRODUCCIÓN                                │
├─────────────────────────────────────────────────────────────┤
│ 1. Meta Business no aprobado a tiempo                      │
│    → Usar Twilio (ya probado y funcional)                   │
│                                                             │
│ 2. AWS complejo de configurar                               │
│    → Usar Railway.app (1-click deploy)                      │
│    → URL: https://railway.app/                              │
│                                                             │
│ 3. Saludtools producción con problemas                     │
│    → Mantener sandbox temporal                              │
│    → Agendar manual mientras se resuelve                    │
│                                                             │
│ 4. OpenAI API límites                                       │
│    → Tener tarjeta de crédito lista                         │
│    → Aumentar límites en platform.openai.com                │
│                                                             │
│ 5. Número WhatsApp no se puede migrar                      │
│    → Usar nuevo número Twilio                               │
│    → Notificar a pacientes del cambio                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📞 CONTACTOS DE SOPORTE TÉCNICO

```
OpenAI: https://help.openai.com/
Twilio: https://support.twilio.com/ (+1-888-908-8454)
AWS: https://aws.amazon.com/support/
Meta Business: https://business.facebook.com/help/
Saludtools: [contacto de soporte de Saludtools]
```

---

## ✅ ENTREGABLES FINALES

Al terminar, debes tener:
- ✅ Sistema funcionando 24/7 en AWS
- ✅ WhatsApp recibiendo y respondiendo mensajes
- ✅ Citas creándose automáticamente en Saludtools
- ✅ Escalamiento a secretarias funcionando
- ✅ Logs y monitoreo activos
- ✅ Documentación de credenciales segura
- ✅ Plan de contingencia listo

---

**ÚLTIMA ACTUALIZACIÓN:** 18 Noviembre 2025, 13:00
**PRÓXIMA REVISIÓN:** 19 Noviembre 2025, 04:00 (1 hora antes del go-live)
