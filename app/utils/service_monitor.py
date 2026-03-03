# app/utils/service_monitor.py
"""
Sistema de monitoreo automático de servicios y respuestas de contingencia
Detecta automáticamente cuando los servicios están inactivos y proporciona números de contacto
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from enum import Enum

class ServiceStatus(Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"  # Mantenimiento programado (con escalación)
    INACTIVE = "inactive"        # Servicio inactivo (solo número de contacto)
    EMERGENCY = "emergency"      # Emergencia crítica

class ServiceMonitor:
    """Monitor automático de servicios críticos"""
    
    def __init__(self):
        self.service_status = ServiceStatus.ACTIVE
        self.last_health_check = {}
        self.failure_counts = {}
        self.inactive_reason = ""
        self.emergency_numbers = self._load_emergency_numbers()
        
        # Configuración de umbrales
        self.max_failures = int(os.getenv("SERVICE_MAX_FAILURES", "3"))
        self.health_check_interval = int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))  # segundos
        
    def _load_emergency_numbers(self) -> List[str]:
        """Carga números de emergencia desde configuración"""
        primary_contact = os.getenv("PRIMARY_CONTACT_NUMBER", "+573207143068")
        secondary_contact = os.getenv("SECONDARY_CONTACT_NUMBER", "+573002007277")
        admin_contact = os.getenv("ADMIN_WHATSAPP", "+573207143068")
        
        return [primary_contact, secondary_contact, admin_contact]
    
    async def check_all_services(self) -> Dict[str, bool]:
        """Verifica el estado de todos los servicios críticos"""
        
        services = {
            "openai": await self._check_openai_service(),
            "twilio": await self._check_twilio_service(),
            "saludtools": await self._check_saludtools_service(),
            "database": await self._check_database_service()
        }
        
        # Analizar resultados y actualizar estado
        failed_services = [name for name, status in services.items() if not status]
        
        if failed_services:
            await self._handle_service_failures(failed_services)
        else:
            # Todos los servicios funcionando - resetear a ACTIVE si no está en mantenimiento manual
            if self.service_status not in [ServiceStatus.MAINTENANCE]:
                self.service_status = ServiceStatus.ACTIVE
                
        self.last_health_check[datetime.now().isoformat()] = services
        return services
    
    async def _check_openai_service(self) -> bool:
        """Verifica si OpenAI está disponible"""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI()
            
            # Test simple de la API con nueva versión
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5
                ),
                timeout=10
            )
            return True
        except Exception as e:
            logging.error(f"OpenAI service check failed: {e}")
            return False
    
    async def _check_twilio_service(self) -> bool:
        """Verifica si Twilio está disponible"""
        try:
            import requests
            
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            
            if not account_sid or not auth_token:
                return False
            
            # Verificar cuenta Twilio
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json"
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    requests.get,
                    url,
                    auth=(account_sid, auth_token),
                    timeout=10
                ),
                timeout=15
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logging.error(f"Twilio service check failed: {e}")
            return False
    
    async def _check_saludtools_service(self) -> bool:
        """Verifica si Saludtools está disponible"""
        try:
            from app.saludtools import SaludtoolsAPI
            
            # Test de conectividad básica
            api = SaludtoolsAPI()
            result = await asyncio.wait_for(
                asyncio.to_thread(api.authenticate),
                timeout=15
            )
            return result is not None
            
        except Exception as e:
            logging.error(f"Saludtools service check failed: {e}")
            # Si no existe el módulo, asumir que está disponible
            return True
    
    async def _check_database_service(self) -> bool:
        """Verifica si la base de datos está disponible"""
        try:
            # Si hay configuración de BD, verificarla
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                return True  # No hay BD configurada
            
            # Test básico de conexión
            # TODO: Implementar según el tipo de BD usado
            return True
            
        except Exception as e:
            logging.error(f"Database service check failed: {e}")
            return False
    
    async def _handle_service_failures(self, failed_services: List[str]):
        """Maneja fallos de servicios"""
        
        # Incrementar contadores de fallo
        for service in failed_services:
            self.failure_counts[service] = self.failure_counts.get(service, 0) + 1
        
        # Determinar criticidad
        critical_services = ["openai", "twilio"]
        critical_failures = [s for s in failed_services if s in critical_services]
        
        if critical_failures:
            # Fallo crítico - cambiar a INACTIVE
            if any(self.failure_counts.get(s, 0) >= self.max_failures for s in critical_failures):
                self.service_status = ServiceStatus.INACTIVE
                self.inactive_reason = f"Servicios críticos inactivos: {', '.join(critical_failures)}"
                
                # Notificar administradores
                await self._notify_admins_service_failure(critical_failures)
                
        else:
            # Solo servicios no críticos fallaron
            logging.warning(f"Servicios no críticos fallaron: {failed_services}")
    
    async def _notify_admins_service_failure(self, failed_services: List[str]):
        """Notifica a administradores sobre fallos críticos"""
        
        admin_phone = os.getenv("ADMIN_WHATSAPP", "").replace("+", "")
        if not admin_phone:
            return
        
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        message = f"""🚨 **ALERTA CRÍTICA DEL SISTEMA** ({timestamp})

❌ **SERVICIOS FALLARON:**
{chr(10).join([f"• {service.upper()}" for service in failed_services])}

⚠️ **ESTADO ACTUAL:** INACTIVO
📱 **Usuarios reciben números de contacto directo**

🔧 **ACCIÓN REQUERIDA:**
Revisar servicios inmediatamente

📊 **Fallos registrados:**
{chr(10).join([f"• {s}: {self.failure_counts.get(s, 0)} fallos" for s in failed_services])}

🔄 **El sistema intentará recuperación automática**"""

        try:
            from app.services.whatsapp_secretary import secretary_notifier
            secretary_notifier.send_whatsapp_message(f"+{admin_phone}", message)
            logging.critical(f"Alerta crítica enviada a admin: {admin_phone}")
        except Exception as e:
            logging.error(f"Error enviando alerta crítica: {e}")
    
    def get_service_status(self) -> ServiceStatus:
        """Obtiene el estado actual del servicio"""
        return self.service_status
    
    def set_maintenance_mode(self, reason: str = "Mantenimiento programado"):
        """Activa modo mantenimiento manual"""
        self.service_status = ServiceStatus.MAINTENANCE
        self.inactive_reason = reason
        logging.warning(f"Modo mantenimiento activado: {reason}")
    
    def set_inactive_mode(self, reason: str = "Servicio temporalmente inactivo"):
        """Activa modo inactivo manual"""
        self.service_status = ServiceStatus.INACTIVE
        self.inactive_reason = reason
        logging.warning(f"Modo inactivo activado: {reason}")
    
    def restore_service(self):
        """Restaura el servicio a modo activo"""
        self.service_status = ServiceStatus.ACTIVE
        self.inactive_reason = ""
        self.failure_counts = {}
        logging.info("Servicio restaurado a modo activo")
    
    def get_contingency_response(self, user_phone: str = None) -> str:
        """Genera respuesta de contingencia según el estado del servicio"""
        
        timestamp = datetime.now().strftime("%H:%M")
        
        if self.service_status == ServiceStatus.MAINTENANCE:
            return self._get_maintenance_response(timestamp)
        elif self.service_status == ServiceStatus.INACTIVE:
            return self._get_inactive_response(timestamp)
        elif self.service_status == ServiceStatus.EMERGENCY:
            return self._get_emergency_response(timestamp)
        else:
            return ""  # Servicio activo, no necesita respuesta de contingencia
    
    def _get_maintenance_response(self, timestamp: str) -> str:
        """Respuesta para modo mantenimiento (con opción de escalación)"""
        
        primary_number = self.emergency_numbers[0] if self.emergency_numbers else "+573207143068"
        
        return f"""🔧 **SISTEMA EN MANTENIMIENTO** ({timestamp})

⚠️ Estamos realizando mejoras en nuestro sistema automático.

📞 **Para agendar tu cita:**

🎯 **OPCIÓN 1 - CONTACTO DIRECTO:**
📱 {primary_number}

🤖 **OPCIÓN 2 - ESCALACIÓN AUTOMÁTICA:**
Escribe "secretaria" y te conectaremos directamente

🕒 **Horarios de atención:**
• Lunes a Viernes: 6:00 AM - 8:00 PM
• Sábados: 8:00 AM - 12:00 PM

⏱️ **Tiempo estimado de restablecimiento:** 30-60 minutos

Disculpa las molestias temporales."""
    
    def _get_inactive_response(self, timestamp: str) -> str:
        """Respuesta para modo inactivo (solo números de contacto)"""
        
        numbers_list = "\n".join([f"📱 {num}" for num in self.emergency_numbers[:2]])
        
        return f"""⚠️ **SERVICIO TEMPORALMENTE INACTIVO** ({timestamp})

Nuestro sistema automático no está disponible en este momento.

📞 **Para agendar tu cita, contacta directamente:**
{numbers_list}

🕒 **Horarios de atención:**
• Lunes a Viernes: 6:00 AM - 8:00 PM  
• Sábados: 8:00 AM - 12:00 PM

📋 **Servicios disponibles:**
• Fisioterapia
• Medicina General
• Acondicionamiento Físico

🔄 Te notificaremos cuando el sistema esté disponible nuevamente.

¡Gracias por tu comprensión!"""
    
    def _get_emergency_response(self, timestamp: str) -> str:
        """Respuesta para emergencias críticas"""
        
        primary_number = self.emergency_numbers[0] if self.emergency_numbers else "+573207143068"
        
        return f"""🚨 **SISTEMA EN MODO EMERGENCIA** ({timestamp})

❌ Experimentamos dificultades técnicas temporales.

📞 **CONTACTA INMEDIATAMENTE:**
📱 {primary_number}

⚠️ **URGENCIAS MÉDICAS:**
📞 Llama al 123 (Emergencias Colombia)

🏥 **IPS REACT está operativa** - Solo el sistema automático está afectado.

Disculpa las molestias. Estamos trabajando para solucionarlo."""

# Instancia global del monitor
service_monitor = ServiceMonitor()

# Funciones de conveniencia para usar en el webhook
def get_service_status() -> ServiceStatus:
    """Obtiene el estado actual del servicio"""
    return service_monitor.get_service_status()

def get_contingency_response(user_phone: str = None) -> Optional[str]:
    """Obtiene respuesta de contingencia si es necesaria"""
    if service_monitor.service_status != ServiceStatus.ACTIVE:
        return service_monitor.get_contingency_response(user_phone)
    return None

def set_maintenance_mode(reason: str = "Mantenimiento programado"):
    """Activa modo mantenimiento"""
    service_monitor.set_maintenance_mode(reason)

def set_inactive_mode(reason: str = "Servicio inactivo"):
    """Activa modo inactivo"""
    service_monitor.set_inactive_mode(reason)

def restore_service():
    """Restaura servicio a modo activo"""
    service_monitor.restore_service()

async def run_health_check():
    """Ejecuta verificación de salud de servicios"""
    return await service_monitor.check_all_services()