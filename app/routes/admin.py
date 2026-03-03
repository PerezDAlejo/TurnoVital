"""
Rutas administrativas para simulación de errores en presentaciones
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging
from typing import Optional

from app.utils.maintenance_manager import maintenance_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Estado global para simulación de errores
error_simulation_state = {
    "active": False,
    "mode": None,
    "end_time": None,
    "reason": None
}

class MaintenanceRequest(BaseModel):
    reason: str = "Mantenimiento programado para demo"

class ErrorModeRequest(BaseModel):
    mode: str  # "partial_failure" or "total_failure"
    duration: int = 300  # segundos
    reason: Optional[str] = None

# ============================================================================
# ENDPOINTS DE MANTENIMIENTO
# ============================================================================

@router.post("/maintenance/enable")
async def enable_maintenance(request: MaintenanceRequest):
    """Activar modo mantenimiento"""
    try:
        maintenance_manager.enable_maintenance_mode(request.reason)
        logger.info(f"Modo mantenimiento activado: {request.reason}")
        return {
            "success": True,
            "message": "Modo mantenimiento activado",
            "reason": request.reason,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error activando mantenimiento: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/maintenance/disable")
async def disable_maintenance():
    """Desactivar modo mantenimiento"""
    try:
        maintenance_manager.disable_maintenance_mode()
        logger.info("Modo mantenimiento desactivado")
        return {
            "success": True,
            "message": "Modo mantenimiento desactivado",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error desactivando mantenimiento: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/maintenance/status")
async def maintenance_status():
    """Obtener estado del modo mantenimiento"""
    return {
        "maintenance_mode": maintenance_manager.is_maintenance_mode,
        "reason": maintenance_manager.maintenance_message if maintenance_manager.is_maintenance_mode else None,
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# ENDPOINTS DE SIMULACIÓN DE ERRORES
# ============================================================================

@router.post("/debug/set-error-mode")
async def set_error_mode(request: ErrorModeRequest):
    """Activar simulación de errores"""
    try:
        global error_simulation_state
        
        end_time = datetime.now() + timedelta(seconds=request.duration)
        
        error_simulation_state.update({
            "active": True,
            "mode": request.mode,
            "end_time": end_time,
            "reason": request.reason or f"Simulación {request.mode} para demo"
        })
        
        logger.warning(f"Simulación de error activada: {request.mode} por {request.duration}s")
        
        return {
            "success": True,
            "message": f"Modo error {request.mode} activado",
            "duration": request.duration,
            "end_time": end_time.isoformat(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error activando simulación: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/debug/clear-error-mode")
async def clear_error_mode():
    """Desactivar simulación de errores"""
    try:
        global error_simulation_state
        
        old_mode = error_simulation_state.get("mode")
        
        error_simulation_state.update({
            "active": False,
            "mode": None,
            "end_time": None,
            "reason": None
        })
        
        logger.info(f"Simulación de error desactivada (era: {old_mode})")
        
        return {
            "success": True,
            "message": "Simulación de errores desactivada",
            "previous_mode": old_mode,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error desactivando simulación: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/error-status")
async def error_status():
    """Obtener estado de simulación de errores"""
    global error_simulation_state
    
    # Verificar si el modo ha expirado
    if error_simulation_state["active"] and error_simulation_state["end_time"]:
        if datetime.now() > error_simulation_state["end_time"]:
            error_simulation_state.update({
                "active": False,
                "mode": None,
                "end_time": None,
                "reason": None
            })
    
    remaining_time = None
    if error_simulation_state["active"] and error_simulation_state["end_time"]:
        remaining = error_simulation_state["end_time"] - datetime.now()
        remaining_time = max(0, int(remaining.total_seconds()))
    
    return {
        "error_mode": error_simulation_state["active"],
        "mode": error_simulation_state["mode"],
        "reason": error_simulation_state["reason"],
        "remaining_time": remaining_time,
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# FUNCIONES DE UTILIDAD PARA EL SISTEMA
# ============================================================================

def check_error_simulation() -> Optional[str]:
    """Verificar si hay simulación de error activa y retornar respuesta apropiada"""
    global error_simulation_state
    
    # Verificar expiración
    if error_simulation_state["active"] and error_simulation_state["end_time"]:
        if datetime.now() > error_simulation_state["end_time"]:
            error_simulation_state.update({
                "active": False,
                "mode": None,
                "end_time": None,
                "reason": None
            })
            return None
    
    if not error_simulation_state["active"]:
        return None
    
    mode = error_simulation_state["mode"]
    
    if mode == "partial_failure":
        return get_partial_failure_response()
    elif mode == "total_failure":
        return get_total_failure_response()
    
    return None

def get_partial_failure_response() -> str:
    """Respuesta para error parcial - escalación con números directos"""
    return """🚨 **Sistema con dificultades técnicas**

He detectado problemas internos que requieren intervención humana para garantizar la mejor atención.

📞 **Contacto directo con nuestro equipo:**
• 📱 +573207143068 (Secretaria Principal)
• 📱 +573002007277 (Secretaria Backup)

⏰ **Horario de atención:**
Lunes a Viernes: 5:00 AM - 8:00 PM
Sábados: 6:00 AM - 2:00 PM

Nuestro equipo te contactará a la brevedad o puedes llamar directamente para agendar tu cita.

¡Lamentamos las molestias!"""

def get_total_failure_response() -> str:
    """Respuesta para error total - contingencia completa"""
    return """🏥 **IPS React - Información de Contacto**

Detectamos dificultades técnicas temporales en nuestro sistema de agendamiento.

📍 **Clínica:**
IPS React - Calle 10 32-115

📞 **Contacto directo:**
• 📱 +573207143068 (Secretaria Principal)
• 📱 +573002007277 (Secretaria Backup)
• 📧 contacto@ipsreact.com

⏰ **Horarios de atención:**
• Lunes a Viernes: 5:00 AM - 8:00 PM
• Sábados: 6:00 AM - 2:00 PM

🩺 **Servicios disponibles:**
• Fisioterapia (requiere orden médica)
• Medicina General
• Acondicionamiento Físico

Por favor contacta directamente para agendar tu cita. ¡Gracias por tu paciencia!"""

# Exportar funciones para usar en webhook
__all__ = ['check_error_simulation', 'error_simulation_state']