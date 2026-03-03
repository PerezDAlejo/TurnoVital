# Sistema de monitoreo y alertas automáticas
import asyncio
import time
import logging
import traceback
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
from app.services.whatsapp_secretary import secretary_notifier

class SystemMonitor:
    """Monitor del sistema con alertas automáticas"""
    
    def __init__(self):
        self.admin_phone = os.getenv("ADMIN_WHATSAPP", "").replace("+", "")
        self.secretary_phones = [
            phone.strip().replace("+", "") 
            for phone in os.getenv("SECRETARY_WHATSAPP_TO", "").split(",") 
            if phone.strip()
        ]
        
        # Métricas del sistema
        self.last_heartbeat = time.time()
        self.error_count = 0
        self.escalation_failures = 0
        self.saludtools_failures = 0
        self.database_failures = 0
        
        # Control de alertas (evitar spam)
        self.last_alert_sent = {}
        self.alert_cooldown = 300  # 5 minutos entre alertas del mismo tipo
        
        # Estado del sistema
        self.system_status = "healthy"
        self.is_monitoring = False
        
    def update_heartbeat(self):
        """Actualiza el heartbeat del sistema"""
        self.last_heartbeat = time.time()
        
    def report_error(self, error_type: str, details: str, context: Dict = None):
        """Reporta un error al sistema de monitoreo"""
        self.error_count += 1
        
        # Incrementar contadores específicos
        if error_type == "escalation_failure":
            self.escalation_failures += 1
        elif error_type == "saludtools_failure":
            self.saludtools_failures += 1
        elif error_type == "database_failure":
            self.database_failures += 1
            
        # Verificar si necesita enviar alerta
        self._check_and_send_alert(error_type, details, context)
        
    def _check_and_send_alert(self, error_type: str, details: str, context: Dict = None):
        """Verifica si debe enviar alerta y la envía"""
        current_time = time.time()
        last_alert = self.last_alert_sent.get(error_type, 0)
        
        # Verificar cooldown
        if current_time - last_alert < self.alert_cooldown:
            return
            
        # Determinar severidad
        severity = self._determine_severity(error_type)
        
        # Enviar alerta
        if severity in ["critical", "high"]:
            self._send_admin_alert(error_type, details, severity, context)
            
        if severity == "critical":
            self._send_secretary_alert(error_type, details, context)
            
        self.last_alert_sent[error_type] = current_time
        
    def _determine_severity(self, error_type: str) -> str:
        """Determina la severidad del error"""
        critical_errors = [
            "system_down",
            "database_connection_lost", 
            "twilio_service_down",
            "multiple_escalation_failures"
        ]
        
        high_errors = [
            "escalation_failure",
            "saludtools_failure", 
            "secretary_unreachable"
        ]
        
        if error_type in critical_errors:
            return "critical"
        elif error_type in high_errors:
            return "high"
        else:
            return "medium"
            
    def _send_admin_alert(self, error_type: str, details: str, severity: str, context: Dict = None):
        """Envía alerta al administrador"""
        if not self.admin_phone:
            return
            
        severity_icons = {
            "critical": "🚨",
            "high": "⚠️", 
            "medium": "ℹ️"
        }
        
        icon = severity_icons.get(severity, "📋")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Información adicional según el contexto
        context_info = ""
        if context:
            if context.get("telefono"):
                context_info += f"\n📱 **Teléfono:** {context['telefono']}"
            if context.get("case_id"):
                context_info += f"\n📋 **Caso:** {context['case_id']}"
            if context.get("patient_name"):
                context_info += f"\n👤 **Paciente:** {context['patient_name']}"
                
        message = f"""{icon} **ALERTA DEL SISTEMA** ({timestamp})

**Tipo:** {error_type.replace('_', ' ').title()}
**Severidad:** {severity.upper()}
**Detalles:** {details}{context_info}

**Estado del Sistema:**
🔢 **Errores totales:** {self.error_count}
📞 **Fallos escalación:** {self.escalation_failures}
🏥 **Fallos Saludtools:** {self.saludtools_failures}
💾 **Fallos BD:** {self.database_failures}

⏰ **Última actividad:** {datetime.fromtimestamp(self.last_heartbeat).strftime('%H:%M:%S')}"""

        try:
            secretary_notifier.send_whatsapp_message(f"+{self.admin_phone}", message)
            logging.info(f"Alerta enviada al admin: {error_type}")
        except Exception as e:
            logging.error(f"Error enviando alerta al admin: {e}")
            
    def _send_secretary_alert(self, error_type: str, details: str, context: Dict = None):
        """Envía alerta crítica a secretarias"""
        if not self.secretary_phones:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message = f"""🚨 **ALERTA CRÍTICA DEL SISTEMA** ({timestamp})

**Problema:** {details}

⚠️ **ACCIÓN REQUERIDA:**
El sistema automático ha fallado. Por favor, gestionen manualmente los casos pendientes.

📞 **Contactar admin:** +{self.admin_phone}

Este es un mensaje automático del sistema de monitoreo."""

        for phone in self.secretary_phones:
            try:
                secretary_notifier.send_whatsapp_message(f"+{phone}", message)
                logging.info(f"Alerta crítica enviada a secretaria: {phone}")
            except Exception as e:
                logging.error(f"Error enviando alerta crítica a {phone}: {e}")
                
    def send_daily_report(self):
        """Envía reporte diario al administrador"""
        if not self.admin_phone:
            return
            
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        uptime_hours = (time.time() - self.last_heartbeat) / 3600
        
        message = f"""📊 **REPORTE DIARIO DEL SISTEMA** ({timestamp})

**Estado General:** {'🟢 SALUDABLE' if self.system_status == 'healthy' else '🔴 CON PROBLEMAS'}

**Estadísticas del Día:**
🔢 **Total errores:** {self.error_count}
📞 **Fallos escalación:** {self.escalation_failures}
🏥 **Fallos Saludtools:** {self.saludtools_failures}
💾 **Fallos BD:** {self.database_failures}

**Uptime:** {uptime_hours:.1f} horas

✅ **Sistema funcionando correctamente**"""

        try:
            secretary_notifier.send_whatsapp_message(f"+{self.admin_phone}", message)
            logging.info("Reporte diario enviado al admin")
        except Exception as e:
            logging.error(f"Error enviando reporte diario: {e}")
            
    async def start_monitoring(self, conversaciones: dict, escalaciones: dict, secretarias: dict):
        """Inicia el monitoreo del sistema en background"""
        if self.is_monitoring:
            return
            
        self.is_monitoring = True
        logging.info("Sistema de monitoreo iniciado")
        
        while self.is_monitoring:
            try:
                await self._monitor_cycle(conversaciones, escalaciones, secretarias)
            except Exception as e:
                logging.error(f"Error en ciclo de monitoreo: {e}")
                self.report_error("monitor_cycle_error", str(e))
                
            await asyncio.sleep(60)  # Revisar cada minuto
            
    async def _monitor_cycle(self, conversaciones: dict, escalaciones: dict, secretarias: dict):
        """Ciclo de monitoreo del sistema"""
        current_time = time.time()
        
        # Verificar heartbeat del sistema
        if current_time - self.last_heartbeat > 300:  # 5 minutos sin actividad
            self.report_error("system_inactive", "Sistema sin actividad por más de 5 minutos")
            
        # Verificar escalaciones colgadas
        stuck_escalations = []
        for telefono, escalacion in escalaciones.items():
            escalation_time = escalacion.get("timestamp")
            if escalation_time:
                try:
                    escalation_datetime = datetime.fromisoformat(escalation_time)
                    if (datetime.utcnow() - escalation_datetime).total_seconds() > 3600:  # 1 hora
                        stuck_escalations.append(telefono)
                except:
                    pass
                    
        if stuck_escalations:
            self.report_error(
                "stuck_escalations",
                f"Escalaciones colgadas detectadas: {len(stuck_escalations)}",
                {"escalations": stuck_escalations}
            )
            
        # Verificar secretarias saturadas
        saturated_secretaries = []
        for phone, info in secretarias.items():
            assigned = info.get("assigned", 0)
            if assigned > 5:  # Más de 5 casos asignados
                saturated_secretaries.append(phone)
                
        if saturated_secretaries:
            self.report_error(
                "secretaries_saturated", 
                f"Secretarias saturadas: {len(saturated_secretaries)}",
                {"secretaries": saturated_secretaries}
            )
            
        # Actualizar heartbeat
        self.update_heartbeat()
        
    def stop_monitoring(self):
        """Detiene el monitoreo"""
        self.is_monitoring = False
        logging.info("Sistema de monitoreo detenido")

# Instancia global del monitor
system_monitor = SystemMonitor()

# Funciones de conveniencia para usar en el código
def report_escalation_failure(telefono: str, error: str, context: Dict = None):
    """Reporta fallo en escalación"""
    ctx = {"telefono": telefono, **(context or {})}
    system_monitor.report_error("escalation_failure", error, ctx)

def report_saludtools_failure(operation: str, error: str, context: Dict = None):
    """Reporta fallo en Saludtools"""
    system_monitor.report_error("saludtools_failure", f"{operation}: {error}", context)
    
def report_database_failure(operation: str, error: str, context: Dict = None):
    """Reporta fallo en base de datos"""
    system_monitor.report_error("database_failure", f"{operation}: {error}", context)
    
def report_critical_system_failure(details: str, context: Dict = None):
    """Reporta fallo crítico del sistema"""
    system_monitor.report_error("system_down", details, context)
    
def update_system_heartbeat():
    """Actualiza el heartbeat del sistema"""
    system_monitor.update_heartbeat()
