"""
SISTEMA COMPLETO DE LOGGING Y MONITOREO - IPS REACT
Logging estructurado, notificaciones automáticas, monitoreo en tiempo real
"""

import os
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import asyncio
import traceback
from dataclasses import dataclass, asdict
from enum import Enum

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class SystemComponent(Enum):
    CHATBOT = "chatbot"
    DATABASE = "database" 
    SALUDTOOLS = "saludtools"
    OCR = "ocr"
    ESCALATION = "escalation"
    WEBHOOK = "webhook"
    SECURITY = "security"
    GENERAL = "general"

@dataclass
class LogEvent:
    """Evento de log estructurado"""
    timestamp: str
    level: LogLevel
    component: SystemComponent
    message: str
    phone_number: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class IPSReactLogger:
    """Sistema de logging avanzado para IPS React"""
    
    def __init__(self):
        self.setup_logging()
        self.error_count = 0
        self.warning_count = 0
        self.critical_errors = []
        
    def setup_logging(self):
        """Configurar sistema de logging estructurado"""
        
        # Crear directorios
        os.makedirs('logs', exist_ok=True)
        os.makedirs('logs/errors', exist_ok=True)
        os.makedirs('logs/system', exist_ok=True)
        os.makedirs('logs/users', exist_ok=True)
        
        # Configurar formatters
        json_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Logger principal
        self.main_logger = logging.getLogger('ips_react')
        self.main_logger.setLevel(logging.DEBUG)
        
        # Handler para archivo principal con UTF-8
        main_handler = logging.FileHandler('logs/ips_react_main.log', encoding='utf-8')
        main_handler.setFormatter(json_formatter)
        self.main_logger.addHandler(main_handler)
        
        # Handler para errores críticos con UTF-8
        error_handler = logging.FileHandler('logs/errors/critical_errors.log', encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(json_formatter)
        self.main_logger.addHandler(error_handler)
        
        # Handler para sistema con UTF-8
        system_handler = logging.FileHandler('logs/system/system_events.log', encoding='utf-8')
        system_handler.setFormatter(json_formatter)
        
        # Logger de sistema
        self.system_logger = logging.getLogger('ips_react.system')
        self.system_logger.addHandler(system_handler)
        
        # Logger de usuarios con UTF-8
        user_handler = logging.FileHandler('logs/users/user_interactions.log', encoding='utf-8')
        user_handler.setFormatter(json_formatter)
        
        self.user_logger = logging.getLogger('ips_react.users')
        self.user_logger.addHandler(user_handler)
        
    def log_event(self, event: LogEvent):
        """Log un evento estructurado"""
        
        try:
            # Preparar mensaje
            log_data = {
                "timestamp": event.timestamp,
                "level": event.level.value,
                "component": event.component.value,
                "message": event.message,
                "phone_number": event.phone_number,
                "user_id": event.user_id,
                "session_id": event.session_id,
                "error_code": event.error_code,
                "metadata": event.metadata or {}
            }
            
            # Agregar stack trace si existe
            if event.stack_trace:
                log_data["stack_trace"] = event.stack_trace
            
            # Convertir a JSON
            json_message = json.dumps(log_data, ensure_ascii=False, default=str)
            
            # Log según nivel
            if event.level == LogLevel.CRITICAL:
                self.main_logger.critical(json_message)
                self.critical_errors.append(event)
                # Notificar inmediatamente
                asyncio.create_task(self._notify_critical_error(event))
                
            elif event.level == LogLevel.ERROR:
                self.main_logger.error(json_message)
                self.error_count += 1
                
            elif event.level == LogLevel.WARNING:
                self.main_logger.warning(json_message)
                self.warning_count += 1
                
            elif event.level == LogLevel.INFO:
                self.main_logger.info(json_message)
                
            else:
                self.main_logger.debug(json_message)
            
            # Log específico por componente
            if event.component in [SystemComponent.DATABASE, SystemComponent.SECURITY]:
                self.system_logger.info(json_message)
            elif event.component == SystemComponent.CHATBOT:
                self.user_logger.info(json_message)
                
        except Exception as e:
            # Fallback logging
            print(f"ERROR EN LOGGING: {e}")
            print(f"Evento original: {event}")
    
    async def _notify_critical_error(self, event: LogEvent):
        """Notificar error crítico a secretarias"""
        try:
            # Importar módulo de notificaciones
            from app.services.whatsapp_secretary import secretary_notifier
            
            error_message = f"""🚨 **ERROR CRÍTICO EN SISTEMA IPS REACT**

🕐 **Tiempo:** {event.timestamp}
🔧 **Componente:** {event.component.value.upper()}
📱 **Usuario:** {event.phone_number or 'Sistema'}
🚫 **Error:** {event.message}

🔴 **ACCIÓN REQUERIDA:** Verificar sistema inmediatamente"""

            # Notificar a secretarias
            await secretary_notifier.send_system_alert(error_message)
            
        except Exception as e:
            print(f"Error notificando error crítico: {e}")
    
    def log_chatbot_interaction(self, phone: str, user_message: str, 
                              bot_response: str, processing_time: float, 
                              metadata: Optional[Dict] = None):
        """Log interacción específica del chatbot"""
        
        event = LogEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=LogLevel.INFO,
            component=SystemComponent.CHATBOT,
            message=f"Interacción chatbot - Usuario: '{user_message[:100]}...' | Bot: '{bot_response[:100]}...'",
            phone_number=phone,
            metadata={
                "user_message": user_message,
                "bot_response": bot_response,
                "processing_time_ms": round(processing_time * 1000, 2),
                **(metadata or {})
            }
        )
        
        self.log_event(event)
    
    def log_saludtools_operation(self, operation: str, success: bool, 
                                response_data: Optional[Dict] = None,
                                error_details: Optional[str] = None,
                                phone: Optional[str] = None):
        """Log operación con Saludtools API"""
        
        level = LogLevel.INFO if success else LogLevel.ERROR
        
        event = LogEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            component=SystemComponent.SALUDTOOLS,
            message=f"Saludtools {operation} - {'Éxito' if success else 'Error'}",
            phone_number=phone,
            metadata={
                "operation": operation,
                "success": success,
                "response_data": response_data,
                "error_details": error_details
            }
        )
        
        self.log_event(event)
    
    def log_ocr_processing(self, phone: str, num_images: int, 
                          success: bool, extracted_text: Optional[str] = None,
                          processing_time: Optional[float] = None,
                          error_details: Optional[str] = None):
        """Log procesamiento OCR"""
        
        level = LogLevel.INFO if success else LogLevel.WARNING
        
        event = LogEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            component=SystemComponent.OCR,
            message=f"OCR procesamiento - {num_images} imágenes - {'Éxito' if success else 'Error'}",
            phone_number=phone,
            metadata={
                "num_images": num_images,
                "success": success,
                "extracted_text_length": len(extracted_text) if extracted_text else 0,
                "extracted_preview": extracted_text[:200] if extracted_text else None,
                "processing_time_ms": round(processing_time * 1000, 2) if processing_time else None,
                "error_details": error_details
            }
        )
        
        self.log_event(event)
    
    def log_escalation(self, phone: str, case_id: str, reason: str, 
                      assigned_secretary: Optional[str] = None,
                      escalation_data: Optional[Dict] = None):
        """Log escalamiento a secretarias"""
        
        event = LogEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=LogLevel.WARNING,
            component=SystemComponent.ESCALATION,
            message=f"Escalamiento iniciado - Caso {case_id} - Razón: {reason}",
            phone_number=phone,
            metadata={
                "case_id": case_id,
                "reason": reason,
                "assigned_secretary": assigned_secretary,
                "escalation_data": escalation_data
            }
        )
        
        self.log_event(event)
    
    def log_system_error(self, component: SystemComponent, error: Exception,
                        context: Optional[Dict] = None,
                        phone: Optional[str] = None):
        """Log error del sistema con stack trace"""
        
        event = LogEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=LogLevel.ERROR,
            component=component,
            message=f"Error en {component.value}: {str(error)}",
            phone_number=phone,
            stack_trace=traceback.format_exc(),
            metadata=context or {}
        )
        
        self.log_event(event)
    
    def log_critical_failure(self, component: SystemComponent, error_message: str,
                           context: Optional[Dict] = None,
                           phone: Optional[str] = None):
        """Log falla crítica del sistema"""
        
        event = LogEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=LogLevel.CRITICAL,
            component=component,
            message=f"FALLA CRÍTICA en {component.value}: {error_message}",
            phone_number=phone,
            error_code="CRITICAL_SYSTEM_FAILURE",
            stack_trace=traceback.format_exc() if traceback else None,
            metadata=context or {}
        )
        
        self.log_event(event)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Obtener estado actual del sistema"""
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "critical_errors_count": len(self.critical_errors),
            "recent_critical_errors": [
                {
                    "timestamp": err.timestamp,
                    "component": err.component.value,
                    "message": err.message
                }
                for err in self.critical_errors[-5:]  # Últimos 5
            ],
            "log_files": {
                "main_log": "logs/ips_react_main.log",
                "errors_log": "logs/errors/critical_errors.log",
                "system_log": "logs/system/system_events.log",
                "users_log": "logs/users/user_interactions.log"
            }
        }

# Instancia global del logger
ips_logger = IPSReactLogger()

# Funciones convenientes para usar en toda la aplicación
def log_chatbot_interaction(phone: str, user_message: str, bot_response: str, 
                          processing_time: float, metadata: Optional[Dict] = None):
    """Función conveniente para log de chatbot"""
    ips_logger.log_chatbot_interaction(phone, user_message, bot_response, processing_time, metadata)

def log_saludtools_operation(operation: str, success: bool, response_data: Optional[Dict] = None,
                           error_details: Optional[str] = None, phone: Optional[str] = None):
    """Función conveniente para log de Saludtools"""
    ips_logger.log_saludtools_operation(operation, success, response_data, error_details, phone)

def log_ocr_processing(phone: str, num_images: int, success: bool, 
                      extracted_text: Optional[str] = None,
                      processing_time: Optional[float] = None,
                      error_details: Optional[str] = None):
    """Función conveniente para log de OCR"""
    ips_logger.log_ocr_processing(phone, num_images, success, extracted_text, processing_time, error_details)

def log_escalation(phone: str, case_id: str, reason: str, 
                  assigned_secretary: Optional[str] = None,
                  escalation_data: Optional[Dict] = None):
    """Función conveniente para log de escalamiento"""
    ips_logger.log_escalation(phone, case_id, reason, assigned_secretary, escalation_data)

def log_system_error(component: SystemComponent, error: Exception,
                    context: Optional[Dict] = None, phone: Optional[str] = None):
    """Función conveniente para log de errores"""
    ips_logger.log_system_error(component, error, context, phone)

def log_critical_failure(component: SystemComponent, error_message: str,
                        context: Optional[Dict] = None, phone: Optional[str] = None):
    """Función conveniente para log de fallas críticas"""
    ips_logger.log_critical_failure(component, error_message, context, phone)

def get_system_status() -> Dict[str, Any]:
    """Función conveniente para obtener estado del sistema"""
    return ips_logger.get_system_status()