# app/routes/admin_system.py
"""
Endpoints de administración para control del sistema de contingencias
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging
from datetime import datetime

from app.utils.service_monitor import (
    service_monitor, 
    ServiceStatus,
    run_health_check,
    set_maintenance_mode,
    set_inactive_mode,
    restore_service
)

router = APIRouter()

# Simple autenticación por token (en producción usar algo más robusto)
ADMIN_TOKEN = "admin_ips_react_2024"

def verify_admin_token(token: str = Query(...)):
    """Verifica token de administración"""
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Token de administración inválido")
    return True

@router.get("/admin/system/status")
async def get_system_status(authorized: bool = Depends(verify_admin_token)):
    """Obtiene el estado completo del sistema"""
    
    try:
        # Ejecutar verificación de servicios
        services_status = await run_health_check()
        
        current_status = service_monitor.get_service_status()
        
        return {
            "system_status": current_status.value,
            "timestamp": datetime.now().isoformat(),
            "services": services_status,
            "failure_counts": service_monitor.failure_counts,
            "inactive_reason": service_monitor.inactive_reason,
            "last_health_checks": list(service_monitor.last_health_check.keys())[-5:] if service_monitor.last_health_check else [],
            "emergency_numbers": service_monitor.emergency_numbers
        }
        
    except Exception as e:
        logging.error(f"Error obteniendo estado del sistema: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/system/maintenance")
async def activate_maintenance(
    reason: str = Query("Mantenimiento programado"),
    authorized: bool = Depends(verify_admin_token)
):
    """Activa modo mantenimiento manualmente"""
    
    try:
        set_maintenance_mode(reason)
        
        logging.warning(f"Modo mantenimiento activado manualmente: {reason}")
        
        return {
            "status": "success",
            "message": "Modo mantenimiento activado",
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "mode": "maintenance"
        }
        
    except Exception as e:
        logging.error(f"Error activando mantenimiento: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/system/inactive")
async def activate_inactive(
    reason: str = Query("Servicio temporalmente inactivo"),
    authorized: bool = Depends(verify_admin_token)
):
    """Activa modo inactivo manualmente"""
    
    try:
        set_inactive_mode(reason)
        
        logging.warning(f"Modo inactivo activado manualmente: {reason}")
        
        return {
            "status": "success",
            "message": "Modo inactivo activado",
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "mode": "inactive"
        }
        
    except Exception as e:
        logging.error(f"Error activando modo inactivo: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/system/restore")
async def restore_system(authorized: bool = Depends(verify_admin_token)):
    """Restaura el sistema a modo activo"""
    
    try:
        restore_service()
        
        logging.info("Sistema restaurado a modo activo manualmente")
        
        return {
            "status": "success", 
            "message": "Sistema restaurado a modo activo",
            "timestamp": datetime.now().isoformat(),
            "mode": "active"
        }
        
    except Exception as e:
        logging.error(f"Error restaurando sistema: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/system/health-check")
async def manual_health_check(authorized: bool = Depends(verify_admin_token)):
    """Ejecuta verificación manual de salud de servicios"""
    
    try:
        services_status = await run_health_check()
        current_status = service_monitor.get_service_status()
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "system_status": current_status.value,
            "services": services_status,
            "summary": {
                "all_services_ok": all(services_status.values()),
                "failed_services": [name for name, status in services_status.items() if not status],
                "total_services": len(services_status)
            }
        }
        
    except Exception as e:
        logging.error(f"Error en verificación de salud: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/system/contingency-message")
async def get_contingency_message(
    user_phone: Optional[str] = Query(None),
    authorized: bool = Depends(verify_admin_token)
):
    """Obtiene el mensaje de contingencia actual"""
    
    try:
        current_status = service_monitor.get_service_status()
        
        if current_status == ServiceStatus.ACTIVE:
            return {
                "status": "active",
                "message": "Sistema operativo - sin mensaje de contingencia",
                "timestamp": datetime.now().isoformat()
            }
        
        contingency_message = service_monitor.get_contingency_response(user_phone)
        
        return {
            "status": current_status.value,
            "message": contingency_message,
            "reason": service_monitor.inactive_reason,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Error obteniendo mensaje de contingencia: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/system/logs")
async def get_system_logs(
    lines: int = Query(50, ge=10, le=500),
    authorized: bool = Depends(verify_admin_token)
):
    """Obtiene los últimos logs del sistema"""
    
    try:
        import os
        
        log_file = "logs/agendamiento.log"
        
        if not os.path.exists(log_file):
            return {
                "status": "no_logs",
                "message": "Archivo de logs no encontrado",
                "logs": []
            }
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "total_lines": len(all_lines),
            "returned_lines": len(recent_lines),
            "logs": [line.strip() for line in recent_lines]
        }
        
    except Exception as e:
        logging.error(f"Error obteniendo logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint público para verificar estado (sin autenticación)
@router.get("/system/status")
async def public_system_status():
    """Estado público del sistema (sin detalles sensibles)"""
    
    try:
        current_status = service_monitor.get_service_status()
        
        return {
            "status": current_status.value,
            "operational": current_status == ServiceStatus.ACTIVE,
            "timestamp": datetime.now().isoformat(),
            "message": "Sistema operativo" if current_status == ServiceStatus.ACTIVE else "Sistema en modo especial"
        }
        
    except Exception as e:
        logging.error(f"Error en estado público: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "operational": False, "message": "Error interno"}
        )

# Endpoints para simular errores durante demos/presentaciones
@router.post("/admin/debug/set-error-mode")
async def set_error_mode(
    mode: str = Query(..., description="partial_failure, total_failure"),
    duration: int = Query(300, description="Duración en segundos"),
    authorized: bool = Depends(verify_admin_token)
):
    """Simula errores del sistema para demos"""
    
    try:
        if mode == "partial_failure":
            # Simular lentitud del sistema
            service_monitor.set_maintenance_mode(f"Demo: Fallo parcial por {duration}s")
            logging.warning(f"[DEMO] Modo fallo parcial activado por {duration}s")
            
        elif mode == "total_failure":
            # Simular caída total
            service_monitor.set_inactive_mode(f"Demo: Fallo total por {duration}s")
            logging.error(f"[DEMO] Modo fallo total activado por {duration}s")
            
        else:
            raise HTTPException(status_code=400, detail="Modo inválido. Use: partial_failure, total_failure")
        
        return {
            "success": True,
            "mode": mode,
            "duration": duration,
            "message": f"Modo de error {mode} activado por {duration} segundos",
            "current_status": service_monitor.get_service_status().value
        }
        
    except Exception as e:
        logging.error(f"Error configurando modo de error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.post("/admin/debug/clear-error-mode")
async def clear_error_mode(authorized: bool = Depends(verify_admin_token)):
    """Limpia el modo de error y restaura el sistema"""
    
    try:
        service_monitor.restore_service()
        logging.info("[DEMO] Modo de error limpiado - sistema restaurado")
        
        return {
            "success": True,
            "message": "Modo de error limpiado, sistema restaurado",
            "current_status": service_monitor.get_service_status().value
        }
        
    except Exception as e:
        logging.error(f"Error limpiando modo de error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.post("/admin/maintenance/enable")
async def enable_maintenance_mode(
    reason: str = Query("Mantenimiento programado", description="Razón del mantenimiento"),
    authorized: bool = Depends(verify_admin_token)
):
    """Habilita modo mantenimiento (alias para /admin/system/maintenance)"""
    
    try:
        service_monitor.set_maintenance_mode(reason)
        logging.warning(f"Modo mantenimiento habilitado: {reason}")
        
        return {
            "success": True,
            "message": "Modo mantenimiento habilitado",
            "reason": reason,
            "status": service_monitor.get_service_status().value,
            "contingency_response": service_monitor.get_contingency_response()
        }
        
    except Exception as e:
        logging.error(f"Error habilitando mantenimiento: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")