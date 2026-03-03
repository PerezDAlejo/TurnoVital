# 🚀 TurnoVital MVP - Sistema Autoadministrado de Agendamiento Inteligente

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Production%20Ready-brightgreen)

TurnoVital es un MVP funcional diseñado para demostrar las capacidades de un asistente virtual IA para agendamiento de citas a través de **WhatsApp**, conectado directamente a **Google Calendar**.

El sistema utiliza procesamiento de lenguaje natural (OpenAI/Gemini) para tener conversaciones fluidas con los pacientes y extraer los datos necesarios (Servicio, Fecha, Hora, Nombre) sin depender de comandos estrictos.

---

## 🏗️ Arquitectura del MVP

1. **Twilio WhatsApp API**: Actúa como el canal de comunicación con los pacientes.
2. **FastAPI Webhook**: Recibe y enruta los mensajes en tiempo real.
3. **TurnoVital Chatbot (OpenAI)**: Mantiene el contexto de la conversación, extrae las intenciones y formatea los datos de agendamiento.
4. **Google Calendar API**: Crea de manera automática los eventos en la agenda de la clínica.
5. **Supabase (Próximamente)**: Persistencia de conversaciones (actualmente en memoria para facilitar pruebas locales del MVP).

---

## ⚙️ Requisitos Previos

1. **Tokens de IA**: API Key de OpenAI (`OPENAI_API_KEY`).
2. **Google Cloud**:
   - Cuenta de Servicio de Google Cloud con la API de Calendar activada.
   - Archivo `credentials.json` en la raíz del proyecto.
   - ID del Calendario (`GOOGLE_CALENDAR_ID`) donde la cuenta de servicio tenga permisos de escritura (compartir el calendario con el correo de la cuenta de servicio).
3. **Twilio**: Una cuenta de Twilio con el Sandbox de WhatsApp activado.
4. **Ngrok**: Para exponer tu servidor local a Twilio.

---

## 🚀 Guía Rápida de Instalación y Ejecución

### 1. Clonar e Instalar Dependencias

```bash
# Clonar el repositorio
git clone <tu-repositorio>
cd turnovital-mvp

# Crear entorno virtual
python -m venv .venv
source .venv/Scripts/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r Requirements.txt
```

_(Nota: Asegúrate de instalar `google-api-python-client google-auth-httplib2 google-auth-oauthlib` si no están en tus requirements)._

### 2. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto basándote en `.env.example`:

```env
OPENAI_API_KEY="tu-api-key-aqui"
OPENAI_MODEL="gpt-4o-mini"
GOOGLE_CALENDAR_ID="primary" # O el correo de tu calendario compartido
```

Asegúrate de colocar tu archivo `credentials.json` de la cuenta de servicio de Google Cloud en la misma carpeta raíz.

### 3. Levantar el Servidor Local

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verás en la consola que el servidor inicia y carga las conexiones al bot.

### 4. Exponer a Internet (Ngrok)

En otra terminal, corre:

```bash
python iniciar_ngrok.py
# O directamente: ngrok http 8000
```

Copia la URL segura `https://xxxxx.ngrok-free.app` que te dé la consola.

### 5. Configurar Twilio

1. Ve a tu consola de Twilio > WhatsApp Sandbox.
2. En la sección "When a message comes in", pega tu URL de ngrok añadiendo la ruta del webhook:
   `https://xxxxx.ngrok-free.app/webhook/bot`
3. Guarda los cambios.

### 6. ¡Probar el MVP!

1. Envía el código de unión al número del Sandbox de Twilio en WhatsApp (ej. `join sand-castle`).
2. Escribe un mensaje natural: _"Hola, necesito agendar una limpieza facial para mañana a las 3pm a nombre de Carlos Perez"._
3. El bot confirmará y la cita aparecerá automáticamente en tu Google Calendar.

---

## 🧹 Limpieza y Optimización

Este proyecto fue refactorizado para ser ligero y eficiente (Stateless). Archivos innecesarios de validación OCR compleja o dependencias estrictas de terceros (SaludTools) fueron abstraídas para esta versión de exposición, permitiendo alojar la API de forma súper económica (ej. un VPS básico de $5/mes o en contenedores serverless).
