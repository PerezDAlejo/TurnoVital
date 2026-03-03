# app/routes/webhook.py
from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse
import xml.etree.ElementTree as ET
import os
import json
import logging
from datetime import datetime

# Importamos el chatbot TurnoVital
from app.chatbot_turnovital import chatbot

router = APIRouter()

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# En un MVP real Serverless, guardaríamos estado en Supabase.
# Por simplicidad extrema inicial para la demo, usamos un dict en memoria
# (luego migraremos a Supabase conversacion_id).
session_store = {}

def twiml_message(text: str):
    """Genera TwiML de respuesta para Twilio WhatsApp."""
    try:
        safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        response = ET.Element("Response")
        message = ET.SubElement(response, "Message")
        message.text = safe
        xml = ET.tostring(response, encoding="unicode")
        return Response(content=xml, media_type="application/xml")
    except Exception as e:
        logger.error(f"Error generando TwiML: {e}")
        return Response(content="<Response><Message>Error interno.</Message></Response>", media_type="application/xml")

@router.post("/bot")
async def whatsapp_webhook(request: Request):
    """
    Webhook principal para Twilio WhatsApp - TurnoVital MVP.
    """
    try:
        form_data = await request.form()
        incoming_msg = form_data.get('Body', '').strip()
        sender_id = form_data.get('From', '')
        
        logger.info(f"Mensaje recibido de {sender_id}: {incoming_msg}")
        
        if not incoming_msg:
            return twiml_message("No recibí ningún mensaje de texto válido.")
            
        # Recuperar o inicializar sesión en memoria
        if sender_id not in session_store:
            session_store[sender_id] = {
                "telefono": sender_id,
                "historial": [],
                "ultima_interaccion": datetime.now()
            }
            
        contexto = session_store[sender_id]
        
        # Procesar con el chatbot TurnoVital
        resultado = await chatbot.procesar_mensaje(incoming_msg, contexto)
        
        respuesta_texto = resultado.get("respuesta", "Lo siento, tuve un problema procesando tu mensaje.")
        
        # Actualizar historial
        contexto["historial"].append({"rol": "user", "content": incoming_msg})
        contexto["historial"].append({"rol": "assistant", "content": respuesta_texto})
        contexto["ultima_interaccion"] = datetime.now()
        
        # Si se agendó, podríamos limpiar el historial para futuras consultas
        if resultado.get("agendado"):
            contexto["historial"] = []
            
        return twiml_message(respuesta_texto)
        
    except Exception as e:
        logger.error(f"Error grave en el webhook: {e}", exc_info=True)
        return twiml_message("Disculpa, tuvimos un fallo interno en TurnoVital. Por favor, intenta de nuevo.")
