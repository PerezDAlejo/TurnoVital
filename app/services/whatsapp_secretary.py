# Sistema de notificaciones WhatsApp para secretarias
import requests
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import os

class WhatsAppSecretaryNotifier:
    """Notificador WhatsApp - Patrón Singleton"""
    
    _instance: Optional['WhatsAppSecretaryNotifier'] = None
    
    def __new__(cls):
        """Implementación del patrón Singleton"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Solo inicializar una vez
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN") 
        self.twilio_phone = os.getenv("TWILIO_WHATSAPP_FROM")
        
    def send_whatsapp_message(self, to_number: str, message: str) -> bool:
        """Envía mensaje directo de WhatsApp"""
        try:
            # VERIFICAR MODO DEMO PRIMERO
            demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
            
            if demo_mode:
                logging.info(f"[MODO DEMO] Simulando envío WhatsApp a {to_number}")
                logging.info(f"[MODO DEMO] Mensaje: {message[:100]}...")
                print(f"📱 [DEMO] WhatsApp simulado enviado a {to_number}")
                return True
            
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json"
            
            # Limpiar prefijo whatsapp: si ya existe en twilio_phone
            from_number = self.twilio_phone
            if not from_number.startswith('whatsapp:'):
                from_number = f'whatsapp:{from_number}'
            
            # Asegurar que to_number tenga el prefijo correcto
            if not to_number.startswith('whatsapp:') and not to_number.startswith('+'):
                to_number = f'+{to_number}'
            if not to_number.startswith('whatsapp:'):
                to_number = f'whatsapp:{to_number}'
            
            data = {
                'From': from_number,
                'To': to_number,
                'Body': message
            }
            
            print(f"📤 ENVIANDO WhatsApp a {to_number}...")
            print(f"   From: {from_number}")
            print(f"   To: {to_number}")
            print(f"   Mensaje: {message[:100]}...")
            
            response = requests.post(
                url,
                data=data,
                auth=(self.twilio_account_sid, self.twilio_auth_token)
            )
            
            print(f"📡 Respuesta Twilio: Status {response.status_code}")
            
            if response.status_code == 201:
                resp_json = response.json()
                print(f"✅ WhatsApp ENVIADO - SID: {resp_json.get('sid')}")
                print(f"   Status: {resp_json.get('status')}")
                logging.info(f"✅ WhatsApp enviado a secretaria {to_number} - SID: {resp_json.get('sid')}")
                return True
            else:
                print(f"❌ ERROR Twilio: {response.status_code}")
                print(f"   Response: {response.text}")
                logging.error(f"Error enviando WhatsApp: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logging.error(f"Error crítico enviando WhatsApp: {e}")
            return False

    def notify_new_case(self, secretary_phone: str, patient_data: Dict[str, Any], 
                       case_id: str, reason: str) -> bool:
        """
        Notifica a la secretaria sobre un nuevo caso con información médica detallada
        Enhanced with priority indicators and better formatting
        """
        try:
            print(f"\n🔔 notify_new_case INICIADO")
            print(f"   Secretary: {secretary_phone}")
            print(f"   Case ID: {case_id}")
            print(f"   Reason: {reason}")
            print(f"   Patient data: {patient_data}")
            
            timestamp = datetime.now().strftime("%H:%M")
            
            # Crear descripción legible del motivo
            motivo_descripciones = {
                "medico": "El paciente desea agendar una cita médica",
                "agendar_cita_medica": "El paciente desea agendar una cita médica",
                "consulta_medica": "El paciente solicita consulta médica",
                "fisioterapia": "El paciente solicita cita de fisioterapia",
                "rehabilitacion": "El paciente solicita rehabilitación",
                "solicitud_compleja": "El paciente requiere asistencia personalizada",
                "multiple_servicios": "El paciente solicita múltiples servicios"
            }
            
            reason_display = motivo_descripciones.get(reason, f"Motivo: {reason}")
            
            # Información básica del paciente
            patient_info = []
            if patient_data.get('nombre'):
                patient_info.append(f"Nombre: {patient_data['nombre']}")
            if patient_data.get('documento') or patient_data.get('cedula'):
                doc = patient_data.get('documento') or patient_data.get('cedula')
                patient_info.append(f"Documento: {doc}")
            if patient_data.get('telefono'):
                patient_info.append(f"Telefono: {patient_data['telefono']}")
            if patient_data.get('email'):
                patient_info.append(f"Email: {patient_data['email']}")
            if patient_data.get('tipo_cita'):
                patient_info.append(f"Tipo cita: {patient_data['tipo_cita']}")
            if patient_data.get('descripcion'):
                patient_info.append(f"Descripcion: {patient_data['descripcion']}")
            if patient_data.get('fecha_deseada'):
                fecha = patient_data['fecha_deseada']
                if isinstance(fecha, str):
                    patient_info.append(f"Fecha deseada: {fecha}")
                else:
                    patient_info.append(f"Fecha deseada: {fecha.strftime('%Y-%m-%d %H:%M')}")
            if patient_data.get('preferencia_contacto'):
                patient_info.append(f"Contacto: {patient_data['preferencia_contacto']}")
            
            # Construir mensaje estructurado
            message_parts = []
            
            # Sección básica
            basic_info = f"""🚨 NUEVO CASO ASIGNADO ({timestamp})

Caso: {case_id}
{reason_display}
Telefono paciente: {patient_data.get('telefono', 'No disponible')}"""
            message_parts.append(basic_info)
            
            # Sección de información del paciente
            if patient_info:
                patient_section = f"""
📊 DATOS DEL PACIENTE:
{chr(10).join(patient_info)}"""
                message_parts.append(patient_section)
            
            # Acción requerida si aplica
            if patient_data.get('accion_requerida'):
                action_section = f"""
⚠️ ACCION REQUERIDA:
{patient_data['accion_requerida']}"""
                message_parts.append(action_section)
            
            # Instruções finales
            instructions = f"""
� RESPONDER AL PACIENTE:
Contactar al numero {patient_data.get('telefono', 'del caso')}

📋 CASO: {case_id}"""
            message_parts.append(instructions)
            
            # Combinar mensaje final
            final_message = "\n".join(message_parts)
            
            # Enviar mensaje
            return self.send_whatsapp_message(secretary_phone, final_message)
            
        except Exception as e:
            logging.error(f"Error construyendo mensaje para secretaria: {e}")
            return False

    def notify_queue_position(self, case_id: str, position: int, total: int, secretary_phone: str) -> bool:
        """Notifica posición en cola"""
        try:
            message = f"""📋 ACTUALIZACION DE COLA

Caso: {case_id}
Posicion: {position}/{total}

Tu caso sigue en espera. Te contactaremos pronto."""
            
            return self.send_whatsapp_message(secretary_phone, message)
            
        except Exception as e:
            logging.error(f"Error en notify_queue_position: {e}")
            return False

    def notify_case_completed(self, case_id: str, secretary_phone: str, resolution_summary: str = "") -> bool:
        """Notifica caso completado"""
        try:
            message = f"""✅ CASO COMPLETADO

Caso: {case_id}
Estado: Resuelto

{resolution_summary if resolution_summary else 'Caso marcado como completado.'}

Gracias por tu atencion."""
            
            return self.send_whatsapp_message(secretary_phone, message)
            
        except Exception as e:
            logging.error(f"Error en notify_case_completed: {e}")
            return False

    def notify_case_transferred(self, case_id: str, secretary_phone: str, reason: str = "") -> bool:
        """Notifica transferencia de caso"""
        try:
            message = f"""🔄 CASO TRANSFERIDO

Caso: {case_id}
Estado: Transferido de vuelta al bot

{reason if reason else 'El caso ha sido transferido al sistema automatizado.'}

El paciente continuara con el bot."""
            
            return self.send_whatsapp_message(secretary_phone, message)
            
        except Exception as e:
            logging.error(f"Error en notify_case_transferred: {e}")
            return False

    def notify_urgent_case(self, case_id: str, patient_data: Dict[str, Any], 
                          urgency_reason: str, secretary_phone: str,
                          medical_info: Optional[Dict] = None) -> bool:
        """Notifica caso urgente con prioridad alta"""
        try:
            timestamp = datetime.now().strftime("%H:%M")
            
            # Construir información médica urgente
            urgent_info = []
            if medical_info:
                if medical_info.get('sintomas_urgentes'):
                    urgent_info.append(f"Sintomas urgentes: {', '.join(medical_info['sintomas_urgentes'])}")
                if medical_info.get('alergias_criticas'):
                    urgent_info.append(f"Alergias criticas: {', '.join(medical_info['alergias_criticas'])}")
                if medical_info.get('medicamentos_actuales'):
                    urgent_info.append(f"Medicamentos actuales: {', '.join(medical_info['medicamentos_actuales'])}")
            
            message_parts = [
                f"""🆘 CASO URGENTE - ATENCION INMEDIATA ({timestamp})

Caso: {case_id}
Paciente: {patient_data.get('nombre', 'No especificado')}
Telefono: {patient_data.get('telefono', 'No disponible')}
Cedula: {patient_data.get('cedula', 'No especificada')}

🚨 RAZON DE URGENCIA:
{urgency_reason}"""
            ]
            
            if urgent_info:
                medical_section = f"""
🩺 INFORMACION MEDICA CRITICA:
{chr(10).join(urgent_info)}"""
                message_parts.append(medical_section)
            
            actions = f"""
📞 CONTACTAR INMEDIATAMENTE: {patient_data.get('telefono', 'No disponible')}

Este caso requiere atencion prioritaria.
Favor contactar al paciente lo antes posible."""
            message_parts.append(actions)
            
            final_message = "\n".join(message_parts)
            
            return self.send_whatsapp_message(secretary_phone, final_message)
            
        except Exception as e:
            logging.error(f"Error en notify_urgent_case: {e}")
            return False

    def notify_system_alert(self, alert_type: str, message: str, secretary_phone: str) -> bool:
        """Notifica alertas del sistema"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            alert_message = f"""⚠️ ALERTA DEL SISTEMA ({timestamp})

Tipo: {alert_type}
Mensaje: {message}

Este es un mensaje automatico del sistema."""
            
            return self.send_whatsapp_message(secretary_phone, alert_message)
            
        except Exception as e:
            logging.error(f"Error en notify_system_alert: {e}")
            return False

# Instancia global del notificador
secretary_notifier = WhatsAppSecretaryNotifier()

def process_secretary_response(telefono: str, mensaje: str, escalaciones: dict, secretarias: dict) -> str:
    """
    Procesa respuestas de secretarias con comandos SUPER INTUITIVOS y HUMANOS
    
    ✅ PARA CONFIRMAR/COMPLETAR:
    • "listo CAS-123" / "confirmado CAS-123" / "resuelto CAS-123"
    • "terminado CAS-123" / "hecho CAS-123" / "ok CAS-123"
    • "✅ CAS-123" / "solucionado CAS-123"
    
    🤖 PARA DEVOLVER AL BOT:
    • "bot CAS-123" / "transferir CAS-123" / "automatico CAS-123"
    """
    try:
        mensaje_original = mensaje.strip()
        mensaje_lower = mensaje_original.lower()
        
        # Buscar pattern de caso (flexible)
        import re
        case_pattern = r'(cas-[a-f0-9]{8}|cita-\w+|\b[a-f0-9]{8}\b)'
        case_match = re.search(case_pattern, mensaje_lower)
        
        if not case_match:
            # Buscar números simples como fallback
            number_match = re.search(r'\b(\d{4,8})\b', mensaje)
            if number_match:
                case_id = f"CAS-{number_match.group(1)}"
            else:
                return None
        else:
            case_id = case_match.group(1).upper()
            if not case_id.startswith('CAS-') and not case_id.startswith('CITA-'):
                case_id = f"CAS-{case_id}"

        # PALABRAS PARA COMPLETAR (muy naturales)
        completion_words = [
            "listo", "confirmado", "resuelto", "terminado", "hecho", "ok", 
            "solucionado", "✅", "completado", "finalizado", "cerrado",
            "confirmo", "termine", "ya", "done", "ready", "finished"
        ]
        
        # PALABRAS PARA TRANSFERIR AL BOT  
        transfer_words = [
            "bot", "transferir", "automatico", "automático", "sistema", 
            "devolver", "pasar", "regresar", "🤖"
        ]
        
        # Verificar si quiere COMPLETAR el caso
        if any(word in mensaje_lower for word in completion_words):
            return handle_case_completion(case_id, telefono, escalaciones, secretarias)
        
        # Verificar si quiere TRANSFERIR al bot
        elif any(word in mensaje_lower for word in transfer_words):
            return handle_case_transfer(case_id, telefono, escalaciones, secretarias)
        
        # Si menciona un caso pero no está claro qué hacer
        elif case_id and any(word in mensaje_lower for word in ["caso", "help", "ayuda", "comandos", "?"]):
            return f"""💡 **¿Qué quieres hacer con {case_id}?**

✅ **Marcar como completado:**
   • "listo {case_id}"
   • "confirmado {case_id}" 
   • "resuelto {case_id}"

🤖 **Devolver al bot:**
   • "bot {case_id}"
   • "transferir {case_id}"

¡Escribe como te salga más natural! 😊"""

        # Si solo dice ayuda sin caso específico
        elif any(word in mensaje_lower for word in ["help", "ayuda", "comandos", "como"]):
            return """🤖 **COMANDOS SUPER FÁCILES:**

✅ **Caso terminado:** "listo CAS-123"
🤖 **Pasar al bot:** "bot CAS-123"

💡 **También funciona:**
• "confirmado CAS-123" / "resuelto CAS-123"
• "transferir CAS-123" / "automatico CAS-123"

¡Usa las palabras que te salgan naturales! 😊"""
        
        return None
        
    except Exception as e:
        logging.error(f"Error procesando respuesta de secretaria: {e}")
        return "❌ Error. Intenta: 'listo CAS-123' o 'bot CAS-123'"

def handle_case_completion(case_id: str, secretary_phone: str, escalaciones: dict, secretarias: dict) -> str:
    """
    Maneja el marcado de caso como terminado - LIBERA LA SECRETARIA automáticamente
    """
    try:
        # Buscar el caso en escalaciones por case_id
        case_found = False
        patient_phone = None
        
        for phone, escalation_data in escalaciones.items():
            if escalation_data.get("caseId") == case_id:
                case_found = True
                patient_phone = phone
                
                # Marcar escalación como resuelta
                escalation_data["activo"] = False
                escalation_data["status"] = "completed"
                escalation_data["completed_at"] = datetime.now().isoformat()
                escalation_data["resolved_by"] = secretary_phone
                
                # LIBERAR SECRETARIA automáticamente
                secretary_whatsapp = f"whatsapp:{secretary_phone}" if not secretary_phone.startswith("whatsapp:") else secretary_phone
                if secretary_whatsapp in secretarias:
                    secretarias[secretary_whatsapp]["assigned"] = max(0, int(secretarias[secretary_whatsapp].get("assigned", 0)) - 1)
                    logging.info(f"Secretaria {secretary_phone} liberada automáticamente")
                
                # Remover escalación
                escalaciones.pop(phone, None)
                
                logging.info(f"Caso {case_id} completado por secretaria {secretary_phone}")
                break
        
        if not case_found:
            return f"❌ No encontré el caso {case_id}. Verifica el número."
        
        # Mensaje de confirmación amigable
        return f"""✅ **¡Perfecto!** 

Caso {case_id} marcado como **completado**.
🆓 **Quedas libre** para nuevos casos.

¡Gracias por tu excelente trabajo! 😊"""
        
    except Exception as e:
        logging.error(f"Error completando caso {case_id}: {e}")
        return f"❌ Error procesando {case_id}. Intenta de nuevo."


def handle_case_transfer(case_id: str, secretary_phone: str, escalaciones: dict, secretarias: dict) -> str:
    """
    Maneja la transferencia de caso de vuelta al bot - LIBERA LA SECRETARIA automáticamente
    """
    try:
        # Buscar el caso en escalaciones por case_id
        case_found = False
        patient_phone = None
        
        for phone, escalation_data in escalaciones.items():
            if escalation_data.get("caseId") == case_id:
                case_found = True
                patient_phone = phone
                
                # Marcar escalación como transferida
                escalation_data["activo"] = False
                escalation_data["status"] = "transferred_back"
                escalation_data["transferred_at"] = datetime.now().isoformat()
                escalation_data["transferred_by"] = secretary_phone
                
                # LIBERAR SECRETARIA automáticamente
                secretary_whatsapp = f"whatsapp:{secretary_phone}" if not secretary_phone.startswith("whatsapp:") else secretary_phone
                if secretary_whatsapp in secretarias:
                    secretarias[secretary_whatsapp]["assigned"] = max(0, int(secretarias[secretary_whatsapp].get("assigned", 0)) - 1)
                    logging.info(f"Secretaria {secretary_phone} liberada automáticamente")
                
                # Remover escalación para que el bot pueda retomar
                escalaciones.pop(phone, None)
                
                logging.info(f"Caso {case_id} transferido al bot por secretaria {secretary_phone}")
                break
        
        if not case_found:
            return f"❌ No encontré el caso {case_id}. Verifica el número."
        
        # Mensaje de confirmación amigable
        return f"""🤖 **¡Listo!**

Caso {case_id} transferido al **bot automático**.
🆓 **Quedas libre** para nuevos casos.

El paciente puede continuar escribiendo normalmente. 👍"""
        
    except Exception as e:
        logging.error(f"Error transfiriendo caso {case_id}: {e}")
        return f"❌ Error procesando {case_id}. Intenta de nuevo."