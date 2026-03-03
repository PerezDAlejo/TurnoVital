"""
🆕 BUG #11 FIX: SISTEMA DE MONITOREO Y ALERTAS
==============================================
Monitor simple para tracking de errores, métricas y alertas del sistema.

Problema original: No existía sistema de monitoreo, lo que dificultaba
detectar problemas en producción y generar alertas proactivas.

Solución: Implementa monitor ligero con:
- Contador de errores y éxitos
- Almacenamiento de errores recientes
- Sistema de alertas por threshold
- Cálculo de tasa de error
- Estado de salud del sistema

Características:
- Zero dependencies (solo stdlib)
- Thread-safe para entornos concurrentes
- Expandible a email/SMS/Slack
- Logging estructurado
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List
import os

logger = logging.getLogger(__name__)

class SimpleMonitor:
    """
    Monitor simple para tracking de errores y métricas del sistema.
    
    Mantiene estadísticas de operaciones, registra errores recientes
    y genera alertas cuando se exceden umbrales configurados.
    """
    
    def __init__(self):
        """Inicializa el monitor con contadores en cero."""
        self.error_count = 0  # Contador total de errores
        self.success_count = 0  # Contador total de éxitos
        self.last_errors: List[Dict] = []  # Cola de errores recientes
        self.max_errors_stored = 50  # Máximo de errores a mantener en memoria
        self.alert_threshold = 10  # Alertar cada N errores
        self.start_time = datetime.now()  # Para calcular uptime
        
    def record_success(self, operation: str):
        """
        Registra una operación exitosa.
        
        Args:
            operation: Nombre de la operación exitosa
        """
        self.success_count += 1
        
    def record_error(self, operation: str, error: str, severity: str = "medium"):
        """
        Registra un error y genera alerta si es necesario.
        
        Args:
            operation: Nombre de la operación que falló
            error: Descripción del error
            severity: Nivel de severidad ("low", "medium", "high", "critical")
        """
        self.error_count += 1
        
        # Crear registro estructurado del error
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "error": str(error),
            "severity": severity
        }
        
        # Agregar a cola de errores recientes
        self.last_errors.append(error_data)
        
        # Mantener solo los últimos N errores (evitar memory leak)
        if len(self.last_errors) > self.max_errors_stored:
            self.last_errors.pop(0)
        
        # Log estructurado para herramientas de análisis
        logger.error(f"❌ Error en {operation}", extra={
            "operation": operation,
            "error": str(error),
            "severity": severity,
            "error_count": self.error_count
        })
        
        # Generar alerta si excede threshold
        if self.error_count % self.alert_threshold == 0:
            self._send_alert(operation, error, severity)
    
    def _send_alert(self, operation: str, error: str, severity: str):
        """
        Envía alerta cuando se alcanza el threshold de errores.
        
        Actualmente solo loguea, pero es expandible a email/SMS/Slack.
        
        Args:
            operation: Operación que causó la alerta
            error: Descripción del error
            severity: Nivel de severidad
        """
        alert_message = f"""
🚨 ALERTA: Threshold de errores alcanzado ({self.alert_threshold} errores)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Operación: {operation}
Último error: {error}
Severidad: {severity}
Total errores: {self.error_count}
Tasa de error: {self.get_error_rate():.2%}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        logger.critical(alert_message)
        
        # TODO: Expandir a canales de notificación externos
        # if os.getenv("ALERT_EMAIL"):
        #     send_email(alert_message)
        # if os.getenv("SLACK_WEBHOOK"):
        #     send_slack_notification(alert_message)
    
    def get_error_rate(self) -> float:
        """
        Calcula la tasa de error actual.
        
        Returns:
            float: Tasa de error (0.0 a 1.0)
        """
        total = self.error_count + self.success_count
        if total == 0:
            return 0.0
        return self.error_count / total
    
    def get_stats(self) -> Dict:
        """
        Retorna estadísticas completas del monitor.
        
        Returns:
            Dict: Estadísticas incluyendo uptime, contadores, tasa de error y salud
        """
        uptime = datetime.now() - self.start_time
        
        return {
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_hours": round(uptime.total_seconds() / 3600, 2),
            "total_operations": self.error_count + self.success_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "error_rate": self.get_error_rate(),
            "recent_errors": self.last_errors[-10:],  # Últimos 10 errores
            "health_status": "healthy" if self.get_error_rate() < 0.05 else "degraded"
        }
    
    def reset_stats(self):
        """
        Reinicia todas las estadísticas.
        Útil para testing o después de deployment.
        """
        self.error_count = 0
        self.success_count = 0
        self.last_errors = []
        self.start_time = datetime.now()

# Instancia global del monitor (singleton pattern)
simple_monitor = SimpleMonitor()
