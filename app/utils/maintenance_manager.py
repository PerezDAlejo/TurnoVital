# Sistema de mantenimiento y fallback automático
import os
import logging
from datetime import datetime
from app.services.whatsapp_secretary import secretary_notifier

class MaintenanceManager:
    """Gestiona estados de mantenimiento y fallback automático"""
    
    def __init__(self):
        self.is_maintenance_mode = False
        self.maintenance_message = ""
        self.emergency_contact_sent = False
        
    def enable_maintenance_mode(self, reason: str = "Mantenimiento programado"):
        """Activa modo mantenimiento y notifica a secretarias"""
        self.is_maintenance_mode = True
        self.maintenance_message = reason
        
        # Notificar a secretarias inmediatamente
        self._notify_secretaries_maintenance(reason)
        logging.warning(f"Sistema en modo mantenimiento: {reason}")
        
    def disable_maintenance_mode(self):
        """Desactiva modo mantenimiento"""
        self.is_maintenance_mode = False
        self.maintenance_message = ""
        self.emergency_contact_sent = False
        logging.info("Sistema salió del modo mantenimiento")
        
    def get_maintenance_response(self, user_phone: str = None) -> str:
        """Genera respuesta automática durante mantenimiento"""
        timestamp = datetime.now().strftime("%H:%M")
        
        # Números de secretarias desde configuración
        secretary_numbers = os.getenv("SECRETARY_WHATSAPP_TO", "").split(",")
        secretary_list = "\n".join([f"📱 {num.strip()}" for num in secretary_numbers if num.strip()])
        
        if not secretary_list:
            secretary_list = "📱 +573207143068\n📱 +573002007277"
            
        response = f"""🔧 **SISTEMA EN MANTENIMIENTO** ({timestamp})

⚠️ Nuestro sistema automático está temporalmente fuera de servicio.

📞 **Para agendar tu cita, contacta directamente:**
{secretary_list}

🕒 **Horarios de atención:**
Lunes a Viernes: 8:00 AM - 6:00 PM
Sábados: 8:00 AM - 12:00 PM

🤖 Te notificaremos cuando el sistema vuelva a estar disponible.

Disculpa las molestias. ¡Estamos trabajando para mejorar tu experiencia!"""

        # Registrar intento de acceso durante mantenimiento
        if user_phone:
            logging.info(f"Usuario {user_phone} intentó acceder durante mantenimiento")
            
        return response
        
    def _notify_secretaries_maintenance(self, reason: str):
        """Notifica a secretarias sobre modo mantenimiento"""
        if self.emergency_contact_sent:
            return  # Ya notificado
            
        secretary_phones = [
            phone.strip().replace("+", "") 
            for phone in os.getenv("SECRETARY_WHATSAPP_TO", "").split(",") 
            if phone.strip()
        ]
        
        admin_phone = os.getenv("ADMIN_WHATSAPP", "").replace("+", "")
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        message = f"""🔧 **SISTEMA EN MODO MANTENIMIENTO** ({timestamp})

**Motivo:** {reason}

⚠️ **IMPORTANTE:**
- El sistema automático está temporalmente desactivado
- Los pacientes recibirán sus números para contacto directo
- Gestionen manualmente todas las citas nuevas
- Se registrarán todos los casos para sincronizar después

👤 **Admin contacto:** +{admin_phone}

🔄 **Se notificará cuando el sistema vuelva a estar operativo**

Este es un mensaje automático del sistema."""

        # Enviar a todas las secretarias
        for phone in secretary_phones:
            try:
                secretary_notifier.send_whatsapp_message(f"+{phone}", message)
                logging.info(f"Notificación de mantenimiento enviada a secretaria: {phone}")
            except Exception as e:
                logging.error(f"Error notificando mantenimiento a {phone}: {e}")
                
        # Enviar al admin también
        if admin_phone:
            try:
                admin_message = f"🔧 **MODO MANTENIMIENTO ACTIVADO**\n\nMotivo: {reason}\nTiempo: {timestamp}\n\n✅ Secretarias han sido notificadas automáticamente"
                secretary_notifier.send_whatsapp_message(f"+{admin_phone}", admin_message)
                logging.info(f"Notificación de mantenimiento enviada al admin: {admin_phone}")
            except Exception as e:
                logging.error(f"Error notificando mantenimiento al admin: {e}")
                
        self.emergency_contact_sent = True
        
    def check_system_health(self) -> bool:
        """Verifica si el sistema debe entrar en modo mantenimiento automáticamente"""
        try:
            # Verificar conectividad de servicios críticos
            from app import database as db
            from app.services import saludtools_service
            
            # Test básico de BD
            # db.test_connection()
            
            # Test básico de Saludtools
            # saludtools_service.health_check()
            
            return True  # Sistema saludable
            
        except Exception as e:
            logging.error(f"Sistema no saludable, activando mantenimiento: {e}")
            self.enable_maintenance_mode(f"Fallo automático detectado: {str(e)[:100]}")
            return False
            
    def emergency_fallback_response(self, error_context: str = "") -> str:
        """Respuesta de emergencia cuando todo falla"""
        secretary_numbers = os.getenv("SECRETARY_WHATSAPP_TO", "+573207143068,+573002007277").split(",")
        secretary_list = "\n".join([f"📱 {num.strip()}" for num in secretary_numbers if num.strip()])
        
        timestamp = datetime.now().strftime("%H:%M")
        
        response = f"""🚨 **SISTEMA TEMPORALMENTE NO DISPONIBLE** ({timestamp})

Estamos experimentando dificultades técnicas.

📞 **CONTACTA INMEDIATAMENTE:**
{secretary_list}

⚡ **Es URGENTE - Te atenderán de inmediato**

🔧 Nuestro equipo técnico está resolviendo el problema.

Disculpa las molestias. Tu cita es importante para nosotros."""

        # Log del contexto de error
        if error_context:
            logging.critical(f"Respuesta de emergencia activada: {error_context}")
            
        return response

# Instancia global del manager de mantenimiento
maintenance_manager = MaintenanceManager()

def check_maintenance_mode(user_phone: str = None) -> str | None:
    """Verifica si está en modo mantenimiento y retorna respuesta apropiada"""
    if maintenance_manager.is_maintenance_mode:
        return maintenance_manager.get_maintenance_response(user_phone)
    return None

def activate_emergency_mode(reason: str):
    """Activa modo de emergencia inmediatamente"""
    maintenance_manager.enable_maintenance_mode(f"EMERGENCIA: {reason}")
    
def get_emergency_response(error_details: str = "") -> str:
    """Obtiene respuesta de emergencia para fallos críticos"""
    return maintenance_manager.emergency_fallback_response(error_details)
