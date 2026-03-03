"""
CHATBOT PRINCIPAL TURNOVITAL MVP
================================
Sistema genérico e inteligente de agendamiento vía WhatsApp.
Diseñado para ser rápido, stateless y conectar con Google Calendar.
"""

import os
import json
import logging
from datetime import datetime
from openai import AsyncOpenAI
from app.google_calendar_manager import GoogleCalendarManager

logger = logging.getLogger(__name__)

class TurnoVitalChatbot:
    """
    Chatbot MVP para TurnoVital.
    Flujo simplificado:
    1. Saludar.
    2. Identificar servicio, fecha y hora.
    3. Pedir nombre completo.
    4. Agendar en Google Calendar.
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.calendar_manager = GoogleCalendarManager()
        
    def get_system_prompt(self) -> str:
        return """Eres el asistente virtual de TurnoVital, un sistema de agendamiento inteligente.
Tu objetivo es ayudar al usuario a agendar una cita de forma rápida y amable.

DATOS NECESARIOS PARA AGENDAR:
1. Servicio a agendar (ej. Consulta general, Revisión, etc.)
2. Fecha deseada.
3. Hora deseada.
4. Nombre completo del usuario.

REGLAS:
- Saluda cordialmente.
- Si el usuario no indica alguno de los datos, pregúntaselos conversacionalmente (de a uno o dos por mensaje).
- Trata de deducir la fecha (ej. "mañana" = mañana). Hoy es {datetime.now().strftime('%Y-%m-%d')}.
- Una vez tengas TODOS los datos, responde OBLIGATORIAMENTE generando un JSON válido con la estructura solicitada, precedido por un mensaje amable de confirmación.

FORMATO DE CONFIRMACIÓN (Solo usar cuando tengas los 4 datos):
"¡Perfecto! Agendaremos tu cita para [Servicio] el [Fecha] a las [Hora] a nombre de [Nombre]."
```json
{
  "listo_para_agendar": true,
  "datos": {
    "servicio": "[Servicio]",
    "fecha": "[YYYY-MM-DD]",
    "hora": "[HH:MM]",
    "nombre": "[Nombre]"
  }
}
```

Si aún faltan datos, responde normalmente como asistente.
"""

    async def procesar_mensaje(self, mensaje: str, contexto: dict = None) -> dict:
        """
        Procesa el mensaje del usuario y decide si agendar o seguir preguntando.
        """
        try:
            historial = contexto.get("historial", []) if contexto else []
            
            # Construir mensajes para OpenAI
            messages = [{"role": "system", "content": self.get_system_prompt()}]
            
            # Añadir historial
            for msg in historial[-6:]: # últimos 6 mensajes
                if isinstance(msg, dict):
                    role = "user" if msg.get("rol") == "user" else "assistant"
                    messages.append({"role": role, "content": msg.get("content", "")})
            
            # Añadir mensaje actual
            messages.append({"role": "user", "content": str(mensaje)})
            
            logger.info("Enviando a OpenAI para análisis TurnoVital...")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3
            )
            
            respuesta_texto = response.choices[0].message.content
            
            # Detectar si el bot generó el JSON de agendamiento
            if "listo_para_agendar" in respuesta_texto and "```json" in respuesta_texto:
                # Extraer JSON
                try:
                    partes = respuesta_texto.split("```json")
                    texto_amable = partes[0].strip()
                    json_str = partes[1].split("```")[0].strip()
                    datos_agendamiento = json.loads(json_str)
                    
                    if datos_agendamiento.get("listo_para_agendar"):
                        datos = datos_agendamiento.get("datos", {})
                        
                        # Intento de crear cita en Google Calendar
                        cal_res = await self.calendar_manager.crear_evento(
                            nombre=datos.get("nombre", "Paciente"),
                            servicio=datos.get("servicio", "Cita"),
                            fecha=datos.get("fecha"),
                            hora=datos.get("hora"),
                            telefono=contexto.get("telefono", "")
                        )
                        
                        if cal_res["success"]:
                            respuesta_final = f"✅ {texto_amable}\n\n¡Tu cita ha sido agendada en nuestro calendario exitosamente! Te esperamos."
                        else:
                            respuesta_final = f"⚠️ {texto_amable}\n\nSin embargo, tuvimos un problema guardándolo en el calendario principal ({cal_res.get('error')}). Un asesor se contactará contigo."
                            
                        return {
                            "respuesta": respuesta_final,
                            "agendado": True,
                            "datos": datos
                        }
                        
                except Exception as eval_err:
                    logger.error(f"Error parseando JSON de agendamiento: {eval_err}")
                    return {
                        "respuesta": "¡Perfecto! Ya tengo todos tus datos. En breve te confirmaremos el agendamiento formal de tu cita.",
                        "agendado": False
                    }
                    
            return {
                "respuesta": respuesta_texto.replace("```json", "").strip(),
                "agendado": False
            }
            
        except Exception as e:
            logger.error(f"Error en TurnoVitalChatbot: {str(e)}")
            return {
                "respuesta": "Disculpa, tuve un problema técnico procesando tu solicitud. ¿Me la repites?",
                "error": str(e)
            }

# Instancia global
chatbot = TurnoVitalChatbot()
