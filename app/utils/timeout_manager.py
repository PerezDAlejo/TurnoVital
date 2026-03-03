# Sistema de timeouts y reinicio automático de conversaciones
import asyncio
import time
from datetime import datetime, timedelta
import logging

# Configuración de timeouts
CONVERSATION_TIMEOUT = 30 * 60  # 30 minutos en segundos
ESCALATION_TIMEOUT = 60 * 60   # 1 hora para escalaciones
CHECK_INTERVAL = 5 * 60        # Revisar cada 5 minutos

# Almacén de última actividad por teléfono
conversation_timestamps = {}
escalation_timestamps = {}

def update_conversation_activity(telefono: str):
    """Actualiza timestamp de última actividad de conversación"""
    conversation_timestamps[telefono] = time.time()

def update_escalation_activity(telefono: str):
    """Actualiza timestamp de última actividad de escalación"""
    escalation_timestamps[telefono] = time.time()

def check_conversation_timeout(telefono: str) -> bool:
    """Verifica si una conversación ha expirado"""
    last_activity = conversation_timestamps.get(telefono, 0)
    return (time.time() - last_activity) > CONVERSATION_TIMEOUT

def check_escalation_timeout(telefono: str) -> bool:
    """Verifica si una escalación ha expirado"""
    last_activity = escalation_timestamps.get(telefono, 0)
    return (time.time() - last_activity) > ESCALATION_TIMEOUT

def reset_conversation_with_context(telefono: str, conversaciones: dict, escalaciones: dict):
    """Reinicia conversación preservando contexto de Saludtools"""
    # Limpiar conversación pero mantener información básica si existe
    if telefono in conversaciones:
        # Preservar información básica del paciente si se extrajo
        historial = conversaciones[telefono]
        datos_paciente = {}
        
        # Buscar datos del paciente en el historial
        for rol, mensaje in historial:
            if rol == "assistant_context" and isinstance(mensaje, dict):
                datos_paciente = mensaje.get("datos_extraidos", {})
                break
        
        # Reiniciar conversación con mensaje informativo
        conversaciones[telefono] = []
        if datos_paciente:
            conversaciones[telefono].append(("assistant_context", {
                "tipo": "reinicio_timeout",
                "datos_preservados": datos_paciente,
                "timestamp": datetime.utcnow().isoformat()
            }))
        
        logging.info(f"Conversación reiniciada por timeout: {telefono}")
        return True
    return False

def reset_escalation_with_context(telefono: str, escalaciones: dict, secretarias: dict):
    """Reinicia escalación liberando secretaria pero preservando contexto"""
    if telefono in escalaciones:
        escalacion = escalaciones[telefono]
        
        # Liberar secretaria asignada
        assignment = escalacion.get("assignment", {})
        assigned_to = assignment.get("assigned_to") if isinstance(assignment, dict) else None
        
        if assigned_to and assigned_to in secretarias:
            secretarias[assigned_to]["assigned"] = max(0, int(secretarias[assigned_to].get("assigned", 0)) - 1)
        
        # Preservar información importante
        historial = escalacion.get("historial", [])
        motivo = escalacion.get("motivo", "")
        case_id = escalacion.get("caseId", "")
        
        # Limpiar escalación
        escalaciones.pop(telefono, None)
        
        logging.info(f"Escalación reiniciada por timeout: {telefono}, caso: {case_id}")
        return {
            "historial": historial,
            "motivo": motivo,
            "case_id": case_id,
            "timestamp_timeout": datetime.utcnow().isoformat()
        }
    return None

async def cleanup_expired_sessions(conversaciones: dict, escalaciones: dict, secretarias: dict):
    """Task en background para limpiar sesiones expiradas"""
    while True:
        try:
            current_time = time.time()
            
            # Limpiar conversaciones expiradas
            expired_conversations = [
                telefono for telefono in conversation_timestamps
                if (current_time - conversation_timestamps[telefono]) > CONVERSATION_TIMEOUT
            ]
            
            for telefono in expired_conversations:
                if telefono in conversaciones:
                    reset_conversation_with_context(telefono, conversaciones, escalaciones)
                conversation_timestamps.pop(telefono, None)
            
            # Limpiar escalaciones expiradas
            expired_escalations = [
                telefono for telefono in escalation_timestamps
                if (current_time - escalation_timestamps[telefono]) > ESCALATION_TIMEOUT
            ]
            
            for telefono in expired_escalations:
                if telefono in escalaciones:
                    context = reset_escalation_with_context(telefono, escalaciones, secretarias)
                    if context:
                        logging.info(f"Escalación expirada liberada: {telefono}")
                escalation_timestamps.pop(telefono, None)
            
            # Limpiar timestamps huérfanos
            active_phones = set(conversaciones.keys()) | set(escalaciones.keys())
            for telefono in list(conversation_timestamps.keys()):
                if telefono not in active_phones:
                    conversation_timestamps.pop(telefono, None)
            
            for telefono in list(escalation_timestamps.keys()):
                if telefono not in active_phones:
                    escalation_timestamps.pop(telefono, None)
            
            if expired_conversations or expired_escalations:
                logging.info(f"Sesiones limpiadas - Conversaciones: {len(expired_conversations)}, Escalaciones: {len(expired_escalations)}")
            
        except Exception as e:
            logging.error(f"Error en cleanup de sesiones: {e}")
        
        # Esperar antes de la siguiente revisión
        await asyncio.sleep(CHECK_INTERVAL)

def should_show_timeout_message(telefono: str) -> bool:
    """Determina si debe mostrar mensaje de timeout al usuario"""
    last_activity = conversation_timestamps.get(telefono, 0)
    time_since_activity = time.time() - last_activity
    
    # Mostrar mensaje si han pasado 25 minutos (5 min antes del timeout)
    return time_since_activity > (CONVERSATION_TIMEOUT - 5 * 60) and time_since_activity < CONVERSATION_TIMEOUT

def get_timeout_warning_message() -> str:
    """Mensaje de advertencia antes del timeout"""
    return ("⏰ Tu sesión está por expirar en 5 minutos por inactividad. "
            "Si necesitas más tiempo, envía cualquier mensaje para mantener la sesión activa. "
            "Si expira, podrás comenzar una nueva conversación y tu información en Saludtools se preservará.")

def get_timeout_reset_message() -> str:
    """Mensaje después de reinicio por timeout"""
    return ("⏰ Tu sesión anterior expiró por inactividad, pero he iniciado una nueva conversación. "
            "Tu información en Saludtools está preservada. "
            "¿En qué puedo ayudarte? ¿Quieres agendar, consultar, editar o cancelar una cita?")