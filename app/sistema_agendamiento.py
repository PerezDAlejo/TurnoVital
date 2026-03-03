"""
Funciones de alto nivel para el sistema de agendamiento.
Simplifica el uso de las APIs y proporciona interfaces unificadas.
"""

from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime
import logging

from app.saludtools import SaludtoolsAPI
from app.database import (
    upsert_paciente, buscar_paciente_por_cedula, insertar_paciente,
    crear_cita_con_validacion, listar_citas_enriquecidas_por_paciente,
    marcar_cita_cancelada, insertar_cita_enriquecida
)

logger = logging.getLogger(__name__)

class SistemaAgendamiento:
    """Interfaz unificada para el sistema de agendamiento."""
    
    def __init__(self):
        self.saludtools = SaludtoolsAPI()
    
    async def crear_cita_paciente(self, datos_cita: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea una cita completa con paciente (si no existe) y cita.
        
        Args:
            datos_cita: Diccionario con datos del paciente y cita
                - nombre: str
                - documento: str
                - telefono: str
                - email: str (opcional)
                - fecha: datetime o str
                - tipo_cita: str (FISIO, PRIMERAVEZ, etc)
                - descripcion: str (opcional)
                
        Returns:
            Dict con resultado de la operación
        """
        try:
            # 1. Buscar o crear paciente localmente
            paciente_id = await self._obtener_o_crear_paciente_local(datos_cita)
            if not paciente_id:
                return {"error": "No se pudo crear el paciente"}
            
            # 2. Intentar crear paciente en Saludtools (si no existe)
            await self._asegurar_paciente_saludtools(datos_cita)
            
            # 3. Crear cita en Saludtools
            cita_saludtools = await self._crear_cita_saludtools(datos_cita)
            
            # 4. Crear cita local
            cita_local = await self._crear_cita_local(paciente_id, datos_cita, cita_saludtools)
            
            return {
                "exito": True,
                "paciente_id": paciente_id,
                "cita_local": cita_local,
                "cita_saludtools": cita_saludtools,
                "mensaje": "Cita creada exitosamente"
            }
            
        except Exception as e:
            logger.error(f"Error creando cita: {e}")
            return {"error": f"Error interno: {str(e)}"}
    
    async def consultar_citas_paciente(self, documento: str) -> Dict[str, Any]:
        """Consulta citas de un paciente tanto local como en Saludtools."""
        try:
            # Buscar paciente local
            paciente = buscar_paciente_por_cedula(documento)
            if not paciente:
                return {"error": "Paciente no encontrado"}
            
            # Obtener citas locales
            citas_locales = listar_citas_enriquecidas_por_paciente(paciente)
            
            # Obtener citas de Saludtools
            citas_saludtools = await self.saludtools.buscar_citas_por_documento(documento)
            
            return {
                "exito": True,
                "paciente": paciente,
                "citas_locales": citas_locales,
                "citas_saludtools": citas_saludtools,
                "total_citas": len(citas_locales) + len(citas_saludtools)
            }
            
        except Exception as e:
            logger.error(f"Error consultando citas: {e}")
            return {"error": f"Error interno: {str(e)}"}
    
    async def cancelar_cita(self, cita_id: str, motivo: str = None) -> Dict[str, Any]:
        """Cancela una cita tanto localmente como en Saludtools."""
        try:
            # Cancelar localmente
            resultado_local = marcar_cita_cancelada(cita_id, motivo)
            
            # TODO: Implementar cancelación en Saludtools cuando esté disponible
            # resultado_saludtools = await self.saludtools.cancelar_cita(saludtools_id)
            
            return {
                "exito": True,
                "cita_cancelada": resultado_local,
                "mensaje": "Cita cancelada exitosamente"
            }
            
        except Exception as e:
            logger.error(f"Error cancelando cita: {e}")
            return {"error": f"Error interno: {str(e)}"}
    
    async def _obtener_o_crear_paciente_local(self, datos: Dict) -> Optional[str]:
        """Busca paciente local o lo crea si no existe."""
        documento = datos.get("documento")
        if not documento:
            return None
            
        # Buscar existente
        paciente_existente = buscar_paciente_por_cedula(documento)
        if paciente_existente:
            return paciente_existente
        
        # Crear nuevo - dividir nombre en nombres y apellidos
        nombre_completo = datos.get("nombre", "")
        partes = nombre_completo.split()
        nombres = partes[0] if partes else "Sin"
        apellidos = " ".join(partes[1:]) if len(partes) > 1 else "Nombre"
        
        paciente_data = {
            "documento": documento,
            "nombres": nombres,
            "apellidos": apellidos,
            "telefono": datos.get("telefono"),
            "email": datos.get("email"),
            "preferencia_contacto": "whatsapp",
        }
        
        # Usar la función simple de insertar paciente para compatibilidad
        return insertar_paciente(
            nombre=nombre_completo,
            documento=documento,
            telefono=datos.get("telefono"),
            email=datos.get("email"),
            preferencia_contacto="whatsapp"
        )
    
    async def _asegurar_paciente_saludtools(self, datos: Dict):
        """Asegura que el paciente existe en Saludtools."""
        documento = datos.get("documento")
        if not documento:
            return None
            
        # Buscar en Saludtools
        paciente = await self.saludtools.buscar_paciente_por_documento(documento)
        if paciente:
            return paciente
        
        # Crear en Saludtools si no existe
        nombres = str(datos.get("nombre", "")).split()
        paciente_data = {
            "firstName": nombres[0] if nombres else "Sin",
            "firstLastName": " ".join(nombres[1:]) if len(nombres) > 1 else "Nombre",
            "documentTypeId": 1,  # CC por defecto
            "documentNumber": documento,
            "phone": datos.get("telefono"),
            "email": datos.get("email")
        }
        
        return await self.saludtools.crear_paciente(paciente_data)
    
    async def _crear_cita_saludtools(self, datos: Dict) -> Optional[Dict]:
        """Crea la cita en Saludtools con información completa incluyendo órdenes médicas."""
        fecha = datos.get("fecha")
        if isinstance(fecha, str):
            fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
        
        # Calcular fecha fin (1 hora después por defecto)
        from datetime import timedelta
        fecha_fin = fecha + timedelta(hours=1)
        
        # Construir comentario con información de orden médica si existe
        comentario_parts = []
        
        # Información básica de la cita
        if datos.get("descripcion"):
            comentario_parts.append(f"Descripción: {datos.get('descripcion')}")
        
        # Información de orden médica
        if datos.get("tiene_orden_medica"):
            comentario_parts.append("--- ORDEN MÉDICA ---")
            
            if datos.get("numero_orden"):
                comentario_parts.append(f"Número de orden: {datos.get('numero_orden')}")
            
            if datos.get("doctor_prescriptor"):
                doctor_info = datos.get("doctor_prescriptor")
                if datos.get("especialidad_prescriptor"):
                    doctor_info += f" ({datos.get('especialidad_prescriptor')})"
                comentario_parts.append(f"Doctor prescriptor: {doctor_info}")
            
            if datos.get("fecha_orden"):
                comentario_parts.append(f"Fecha orden: {datos.get('fecha_orden')}")
            
            if datos.get("diagnostico"):
                comentario_parts.append(f"Diagnóstico: {datos.get('diagnostico')}")
            
            if datos.get("tratamiento_prescrito"):
                comentario_parts.append(f"Tratamiento: {datos.get('tratamiento_prescrito')}")
        
        # Información del plan de salud
        if datos.get("plan_salud"):
            comentario_parts.append(f"Plan de salud: {datos.get('plan_salud')}")
        
        # Especialista preferido
        if datos.get("especialista_preferido"):
            comentario_parts.append(f"Especialista preferido: {datos.get('especialista_preferido')}")
        
        comentario_completo = "\n".join(comentario_parts) if comentario_parts else None
        
        cita_data = {
            "startAppointment": fecha.strftime("%Y-%m-%d %H:%M"),
            "endAppointment": fecha_fin.strftime("%Y-%m-%d %H:%M"),
            "patientDocumentTypeId": 1,
            "patientDocumentNumber": datos.get("documento"),
            "appointmentType": datos.get("tipo_cita", "FISIO"),
            "stateAppointment": "PENDING",
            "modality": "PRESENCIAL"
        }
        
        # Agregar comentario solo si hay información relevante
        if comentario_completo:
            cita_data["comment"] = comentario_completo
        
        return await self.saludtools.crear_cita(cita_data)
    
    async def _crear_cita_local(self, paciente_id: str, datos: Dict, cita_saludtools: Optional[Dict]) -> str:
        """Crea la cita local."""
        fecha = datos.get("fecha")
        if isinstance(fecha, str):
            fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
        
        # Calcular fecha fin
        from datetime import timedelta
        fecha_fin = fecha + timedelta(hours=1)
        
        # Crear cita usando insertar_cita_enriquecida
        cita_id = insertar_cita_enriquecida(
            paciente_id=paciente_id,
            especialista_id="default",
            tipo_cita=datos.get("tipo_cita", "FISIO"),
            start_at=fecha,
            end_at=fecha_fin,
            duracion_min=60,
            notas=datos.get("descripcion", f"Cita de {datos.get('tipo_cita', 'fisioterapia')}"),
            plan_salud=datos.get("plan_salud"),
            tiene_orden_medica=datos.get("tiene_orden_medica")
        )
        
        # Establecer Saludtools ID si existe
        if cita_saludtools and "id" in cita_saludtools:
            from app.database import set_saludtools_id
            set_saludtools_id(cita_id, cita_saludtools["id"])
        
        return cita_id


# Instancia global para uso fácil
sistema_agendamiento = SistemaAgendamiento()


# Funciones de conveniencia para mantener compatibilidad
async def crear_cita_paciente(datos_cita: Dict[str, Any]) -> Dict[str, Any]:
    """Función de conveniencia para crear cita con paciente."""
    return await sistema_agendamiento.crear_cita_paciente(datos_cita)


async def consultar_citas_paciente(documento: str) -> Dict[str, Any]:
    """Función de conveniencia para consultar citas de paciente."""
    return await sistema_agendamiento.consultar_citas_paciente(documento)