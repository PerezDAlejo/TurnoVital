"""
Endpoint simple para que la secretaria marque cuando completó un caso.
Esto permite asignar automáticamente el siguiente caso de la cola.

USO:
POST /webhook/secretary-available
Body: { "case_id": "ABC123", "resolution": "completed" }
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

router = APIRouter()

class SecretaryAvailableRequest(BaseModel):
    case_id: str
    resolution: Optional[str] = "completed"
    notes: Optional[str] = None

@router.post("/secretary-available")
async def secretary_available(request: SecretaryAvailableRequest):
    """
    Endpoint para marcar que la secretaria completó un caso y está disponible.
    Automáticamente asigna el siguiente caso de la cola si existe.
    """
    try:
        from app.services.escalation_engine import escalation_engine
        
        logging.info(f"Secretaria completó caso {request.case_id}")
        
        # Resolver el caso actual
        success = escalation_engine.resolve_escalation(
            case_id=request.case_id,
            resolution_type=request.resolution,
            resolution_notes=request.notes
        )
        
        if success:
            return {
                "status": "success",
                "message": "Caso resuelto y siguiente caso asignado (si existe en cola)",
                "case_id": request.case_id
            }
        else:
            raise HTTPException(status_code=500, detail="Error resolviendo caso")
            
    except Exception as e:
        logging.error(f"Error in secretary-available endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queue-status")
async def queue_status():
    """
    Endpoint para ver el estado de la cola de casos.
    """
    try:
        from app.services.escalation_engine import escalation_engine
        
        # TODO: Implementar cuando tengamos BD con tabla de cola
        return {
            "queue_length": 0,
            "active_cases": 0,
            "secretary_status": "available"
        }
        
    except Exception as e:
        logging.error(f"Error in queue-status endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
