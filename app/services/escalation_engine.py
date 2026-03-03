# Escalation Engine - Versión Limpia y Optimizada
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.database import (
    handoff_create_escalation, handoff_set_assignment, 
    handoff_inc_assigned, log_accion_db
)
from app.services.whatsapp_secretary import secretary_notifier


class EscalationEngine:
    """Motor de escalamiento simplificado - Patrón Singleton"""
    
    _instance: Optional['EscalationEngine'] = None
    
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
        
        self.secretary_phone = os.getenv("SECRETARY_WHATSAPP_TO", "").split(",")[0].strip()
        logging.info(f"✅ EscalationEngine inicializado - Secretaria: {self.secretary_phone}")

    def process_escalation(self, case_id: str, escalation_data: Dict[str, Any]) -> bool:
        """
        Procesa un escalamiento: registra en BD (si disponible) y envía WhatsApp a secretaria
        
        Args:
            case_id: ID único del caso
            escalation_data: Diccionario con telefono_usuario, motivo, patient_data, etc.
            
        Returns:
            True si el proceso fue exitoso
        """
        print(f"\n🔔 [ESCALATION] Procesando case_id={case_id}")
        logging.info(f"🔔 process_escalation - case_id={case_id}")
        
        # Extraer datos
        telefono_usuario = escalation_data.get("telefono_usuario", "Desconocido")
        motivo = escalation_data.get("motivo", "solicitud_compleja")
        historial = escalation_data.get("historial", [])
        
        print(f"   📞 Paciente: {telefono_usuario}")
        print(f"   📝 Motivo: {motivo}")
        
        # Guardar en BD solo si está disponible
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            try:
                handoff_create_escalation(
                    case_id=case_id,
                    telefono_usuario=telefono_usuario,
                    motivo=motivo,
                    historial=historial,
                    estado="open"
                )
                logging.info(f"💾 Escalación guardada en BD")
            except Exception as db_error:
                logging.warning(f"⚠️ BD no disponible: {str(db_error)[:80]}")
        else:
            logging.info(f"📝 BD deshabilitada - operación en memoria")

        # Verificar configuración de secretaria
        if not self.secretary_phone:
            logging.error("❌ No hay número de secretaria configurado en SECRETARY_WHATSAPP_TO")
            return False
        
        # Asignar a secretaria y enviar WhatsApp
        print(f"   ✅ Asignando a secretaria: {self.secretary_phone}")
        return self._assign_to_secretary(case_id, self.secretary_phone, escalation_data)

    def _assign_to_secretary(self, case_id: str, secretary_phone: str, escalation_data: Dict) -> bool:
        """Asigna caso a secretaria y envía notificación WhatsApp"""
        
        # Guardar asignación en BD (si disponible)
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            try:
                handoff_set_assignment(case_id, secretary_phone, "assigned")
                handoff_inc_assigned(secretary_phone, 1)
            except Exception as db_error:
                logging.warning(f"⚠️ BD no disponible para asignación: {str(db_error)[:80]}")

        # Preparar datos para notificación
        patient_data = escalation_data.get("patient_data", {})
        telefono_paciente = escalation_data.get("telefono_usuario", "")
        
        print(f"   📤 Enviando WhatsApp a secretaria...")
        
        # VALIDACIÓN: No enviar si secretaria = paciente (modo testing)
        sec_number = secretary_phone.replace("whatsapp:", "").replace("+", "").strip()
        pac_number = telefono_paciente.replace("whatsapp:", "").replace("+", "").strip()
        
        if sec_number == pac_number:
            print(f"   ⚠️ MODO TESTING: Secretaria y paciente mismo número ({sec_number})")
            print(f"   ✅ Caso registrado pero WhatsApp omitido (evitar loop)")
            
            # 🔍 MODO DEBUG: Construir y mostrar mensaje que SE ENVIARÍA
            print(f"\n{'='*80}")
            print(f"📨 MENSAJE QUE SE ENVIARÍA A SECRETARIA (+{sec_number}):")
            print(f"{'='*80}\n")
            
            # Construir mensaje (mismo formato que notify_new_case)
            timestamp = datetime.now().strftime("%H:%M")
            reason = escalation_data.get("motivo", "solicitud_compleja")
            
            motivo_descripciones = {
                "medico": "El paciente desea agendar una cita médica",
                "agendar_cita_medica": "El paciente desea agendar una cita médica",
                "desea agendar cita médica": "El paciente desea agendar una cita médica",
                "consulta_medica": "El paciente solicita consulta médica",
                "fisioterapia": "El paciente solicita cita de fisioterapia",
                "rehabilitacion": "El paciente solicita rehabilitación",
                "solicitud_compleja": "El paciente requiere asistencia personalizada",
                "multiple_servicios": "El paciente solicita múltiples servicios"
            }
            
            reason_display = motivo_descripciones.get(reason, f"Motivo: {reason}")
            
            mensaje_preview = f"""🚨 NUEVO CASO ASIGNADO ({timestamp})

Caso: {case_id}
{reason_display}
Telefono paciente: {patient_data.get('telefono', 'No disponible')}

📊 DATOS DEL PACIENTE:"""
            
            # Agregar info del paciente
            if patient_data.get('nombre'):
                mensaje_preview += f"\nNombre: {patient_data['nombre']}"
            if patient_data.get('documento') or patient_data.get('cedula'):
                doc = patient_data.get('documento') or patient_data.get('cedula')
                mensaje_preview += f"\nDocumento: {doc}"
            if patient_data.get('telefono'):
                mensaje_preview += f"\nTelefono: {patient_data['telefono']}"
            if patient_data.get('tipo_cita'):
                mensaje_preview += f"\nTipo cita: {patient_data['tipo_cita']}"
            if patient_data.get('descripcion'):
                mensaje_preview += f"\nDescripcion: {patient_data['descripcion']}"
                
            mensaje_preview += f"""

📞 RESPONDER AL PACIENTE:
Contactar al numero {patient_data.get('telefono', 'del caso')}

📋 CASO: {case_id}"""
            
            print(mensaje_preview)
            print(f"\n{'='*80}\n")
            
            logging.warning(f"Testing mode: WhatsApp omitido - mismo número")
            return True

        # Enviar notificación WhatsApp
        try:
            result = secretary_notifier.notify_new_case(
                secretary_phone=secretary_phone,
                patient_data=patient_data,
                case_id=case_id,
                reason=escalation_data.get("motivo", "solicitud_compleja")
            )
            
            if result:
                print(f"   ✅ WhatsApp enviado exitosamente")
                logging.info(f"✅ WhatsApp confirmado - {secretary_phone}")
            else:
                print(f"   ❌ Error enviando WhatsApp")
                logging.error(f"❌ Fallo WhatsApp - {secretary_phone}")
            
            # Log en BD (si disponible)
            if db_url:
                try:
                    log_accion_db("ESCALATION_ASSIGNED", {
                        "case_id": case_id,
                        "secretary_phone": secretary_phone,
                        "escalation_type": escalation_data.get("escalation_type", "auto"),
                        "priority": escalation_data.get("priority", "normal")
                    })
                except Exception as log_error:
                    logging.warning(f"⚠️ Log BD falló: {str(log_error)[:50]}")
            
            return result
            
        except Exception as e:
            logging.error(f"❌ Error crítico enviando WhatsApp: {e}")
            return False


# Instancia global
escalation_engine = EscalationEngine()
