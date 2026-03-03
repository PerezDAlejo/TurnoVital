"""
SERVERLESS HANDLER FOR SECURE FILE OPERATIONS
Manejador Lambda para operaciones de archivos seguros con integración OCR
Compatible con arquitectura serverless de AWS.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Configurar logging para serverless
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Imports lazy para evitar problemas en cold starts
def get_secure_file_storage():
    """Lazy import para evitar problemas en serverless"""
    try:
        from app.services.secure_file_storage import secure_file_storage
        return secure_file_storage
    except Exception as e:
        logger.error(f"Failed to import secure file storage: {e}")
        return None

def get_access_control_service():
    """Lazy import para access control"""
    try:
        from app.services.access_control import access_control_service
        return access_control_service
    except Exception as e:
        logger.error(f"Failed to import access control: {e}")
        return None

def get_ocr_file_integration():
    """Lazy import para OCR integration"""
    try:
        from app.services.ocr_file_integration import ocr_file_integration
        return ocr_file_integration
    except Exception as e:
        logger.error(f"Failed to import OCR integration: {e}")
        return None

def get_audit_logger():
    """Lazy import para audit logger"""
    try:
        from app.services.audit_logger import audit_logger
        return audit_logger
    except Exception as e:
        logger.error(f"Failed to import audit logger: {e}")
        return None

class ServerlessSecureFileHandler:
    """
    Manejador serverless para operaciones de archivos seguros
    Optimizado para AWS Lambda con gestión eficiente de memoria y timeouts
    """

    def __init__(self):
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
        self.timeout_buffer = 10  # segundos antes del timeout de Lambda

    async def handle_store_file(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Maneja el almacenamiento seguro de archivos

        Event structure:
        {
            "operation": "store_file",
            "file_data": "base64_encoded_file_data",
            "file_name": "document.pdf",
            "document_type": "orden_medica",
            "patient_document": "12345678",
            "patient_name": "Juan Pérez",
            "owner_user_id": "user123",
            "owner_role": "secretary",
            "metadata": {...}
        }
        """
        try:
            # Validar entrada
            if not event.get("file_data"):
                return self._error_response("Missing file_data")

            if not event.get("file_name"):
                return self._error_response("Missing file_name")

            # Decodificar archivo
            import base64
            try:
                file_data = base64.b64decode(event["file_data"])
            except Exception as e:
                return self._error_response(f"Invalid base64 file_data: {e}")

            # Verificar tamaño
            if len(file_data) > self.max_file_size:
                return self._error_response(f"File size exceeds maximum ({self.max_file_size} bytes)")

            # Obtener servicios
            storage = get_secure_file_storage()
            if not storage:
                return self._error_response("Secure file storage service unavailable")

            # Almacenar archivo
            result = await storage.store_file(
                file_data=file_data,
                file_name=event["file_name"],
                owner_user_id=event.get("owner_user_id", "serverless_system"),
                owner_role=event.get("owner_role", "system"),
                document_type=event.get("document_type", "temporal"),
                patient_document=event.get("patient_document"),
                patient_name=event.get("patient_name"),
                medical_info=event.get("medical_info"),
                ocr_text=event.get("ocr_text"),
                ocr_confidence=event.get("ocr_confidence")
            )

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "success": True,
                    "file_id": result.get("file_id"),
                    "file_size": result.get("file_size"),
                    "encrypted": result.get("encrypted", False),
                    "message": "File stored securely"
                })
            }

        except Exception as e:
            logger.error(f"Store file operation failed: {e}")
            return self._error_response(str(e))

    async def handle_retrieve_file(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Maneja la recuperación de archivos

        Event structure:
        {
            "operation": "retrieve_file",
            "file_id": "uuid-of-file",
            "user_id": "user123",
            "user_role": "doctor"
        }
        """
        try:
            file_id = event.get("file_id")
            if not file_id:
                return self._error_response("Missing file_id")

            # Verificar permisos
            access_control = get_access_control_service()
            if access_control:
                access_check = await access_control.check_file_access(
                    file_id,
                    event.get("user_id"),
                    event.get("user_role"),
                    "read"
                )
                if not access_check.get("granted"):
                    return {
                        "statusCode": 403,
                        "body": json.dumps({
                            "success": False,
                            "error": "Access denied",
                            "reason": access_check.get("reason")
                        })
                    }

            # Recuperar archivo
            storage = get_secure_file_storage()
            if not storage:
                return self._error_response("Secure file storage service unavailable")

            file_data = await storage.retrieve_file(
                file_id,
                event.get("user_id"),
                event.get("user_role")
            )

            # Codificar en base64 para respuesta
            import base64
            encoded_data = base64.b64encode(file_data).decode()

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "success": True,
                    "file_data": encoded_data,
                    "file_size": len(file_data)
                })
            }

        except Exception as e:
            logger.error(f"Retrieve file operation failed: {e}")
            return self._error_response(str(e))

    async def handle_process_medical_files(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Maneja el procesamiento de archivos médicos con OCR

        Event structure:
        {
            "operation": "process_medical_files",
            "media_data": [{"url": "https://...", "content_type": "image/jpeg"}],
            "patient_document": "12345678",
            "patient_name": "Juan Pérez",
            "owner_user_id": "user123",
            "owner_role": "secretary"
        }
        """
        try:
            media_data = event.get("media_data", [])
            if not media_data:
                return self._error_response("Missing or empty media_data")

            # Obtener servicio de integración OCR
            ocr_integration = get_ocr_file_integration()
            if not ocr_integration:
                return self._error_response("OCR file integration service unavailable")

            # Procesar archivos
            result = await ocr_integration.process_and_store_medical_files(
                media_data=media_data,
                patient_document=event.get("patient_document"),
                patient_name=event.get("patient_name"),
                owner_user_id=event.get("owner_user_id", "serverless_system"),
                owner_role=event.get("owner_role", "system"),
                additional_metadata=event.get("metadata")
            )

            return {
                "statusCode": 200,
                "body": json.dumps(result)
            }

        except Exception as e:
            logger.error(f"Process medical files operation failed: {e}")
            return self._error_response(str(e))

    async def handle_list_patient_files(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Maneja la lista de archivos de un paciente

        Event structure:
        {
            "operation": "list_patient_files",
            "patient_document": "12345678",
            "user_id": "user123",
            "user_role": "doctor",
            "document_type": "orden_medica"  // opcional
        }
        """
        try:
            patient_document = event.get("patient_document")
            if not patient_document:
                return self._error_response("Missing patient_document")

            # Obtener servicio de integración
            ocr_integration = get_ocr_file_integration()
            if not ocr_integration:
                return self._error_response("OCR file integration service unavailable")

            # Listar archivos
            files = await ocr_integration.get_medical_files_for_patient(
                patient_document=patient_document,
                user_id=event.get("user_id"),
                user_role=event.get("user_role"),
                document_type=event.get("document_type")
            )

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "success": True,
                    "files": files,
                    "total_count": len(files)
                })
            }

        except Exception as e:
            logger.error(f"List patient files operation failed: {e}")
            return self._error_response(str(e))

    async def handle_get_audit_trail(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Maneja la consulta del audit trail

        Event structure:
        {
            "operation": "get_audit_trail",
            "file_id": "uuid-of-file",  // opcional
            "user_id": "user123",      // opcional
            "limit": 50,
            "offset": 0
        }
        """
        try:
            audit = get_audit_logger()
            if not audit:
                return self._error_response("Audit logger service unavailable")

            # Obtener audit trail
            audit_trail = await audit.get_audit_trail(
                file_id=event.get("file_id"),
                user_id=event.get("user_id"),
                limit=event.get("limit", 50),
                offset=event.get("offset", 0)
            )

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "success": True,
                    "audit_trail": audit_trail,
                    "count": len(audit_trail)
                })
            }

        except Exception as e:
            logger.error(f"Get audit trail operation failed: {e}")
            return self._error_response(str(e))

    async def handle_delete_file(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Maneja la eliminación de archivos

        Event structure:
        {
            "operation": "delete_file",
            "file_id": "uuid-of-file",
            "user_id": "user123",
            "user_role": "admin"
        }
        """
        try:
            file_id = event.get("file_id")
            if not file_id:
                return self._error_response("Missing file_id")

            # Verificar permisos
            access_control = get_access_control_service()
            if access_control:
                access_check = await access_control.check_file_access(
                    file_id,
                    event.get("user_id"),
                    event.get("user_role"),
                    "delete"
                )
                if not access_check.get("granted"):
                    return {
                        "statusCode": 403,
                        "body": json.dumps({
                            "success": False,
                            "error": "Access denied for deletion"
                        })
                    }

            # Eliminar archivo
            storage = get_secure_file_storage()
            if not storage:
                return self._error_response("Secure file storage service unavailable")

            success = await storage.delete_file(
                file_id,
                event.get("user_id"),
                event.get("user_role")
            )

            return {
                "statusCode": 200 if success else 500,
                "body": json.dumps({
                    "success": success,
                    "message": "File deleted successfully" if success else "File deletion failed"
                })
            }

        except Exception as e:
            logger.error(f"Delete file operation failed: {e}")
            return self._error_response(str(e))

    def _error_response(self, message: str, status_code: int = 500) -> Dict[str, Any]:
        """Genera respuesta de error estandarizada"""
        return {
            "statusCode": status_code,
            "body": json.dumps({
                "success": False,
                "error": message,
                "timestamp": datetime.now().isoformat()
            })
        }

# Instancia global del manejador
secure_file_handler = ServerlessSecureFileHandler()

# Función principal de Lambda
async def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler principal para AWS Lambda
    """
    try:
        logger.info(f"Processing secure file operation: {event.get('operation')}")

        operation = event.get("operation")
        if not operation:
            return secure_file_handler._error_response("Missing operation")

        # Routing de operaciones
        operations = {
            "store_file": secure_file_handler.handle_store_file,
            "retrieve_file": secure_file_handler.handle_retrieve_file,
            "process_medical_files": secure_file_handler.handle_process_medical_files,
            "list_patient_files": secure_file_handler.handle_list_patient_files,
            "get_audit_trail": secure_file_handler.handle_get_audit_trail,
            "delete_file": secure_file_handler.handle_delete_file
        }

        handler = operations.get(operation)
        if not handler:
            return secure_file_handler._error_response(f"Unknown operation: {operation}")

        # Ejecutar operación
        result = await handler(event, context)

        logger.info(f"Operation {operation} completed with status {result.get('statusCode')}")
        return result

    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        return secure_file_handler._error_response(f"Internal server error: {str(e)}")

# Handler sincrónico para compatibilidad con runtime de Python
def handle_secure_file_operation(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    Handler sincrónico que envuelve el asíncrono para compatibilidad
    """
    import asyncio

    try:
        # Ejecutar en bucle de eventos
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Si ya hay un loop corriendo (como en algunos entornos serverless)
            return loop.create_task(lambda_handler(event, context))

        return loop.run_until_complete(lambda_handler(event, context))

    except Exception as e:
        logger.error(f"Synchronous handler error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "error": f"Synchronous handler error: {str(e)}"
            })
        }