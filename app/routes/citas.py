from fastapi import APIRouter, HTTPException, Query
from app.models import CitaRequest, EditarCitaRequest, EliminarCitaRequest
from app import database, saludtools
from datetime import datetime, timedelta
import logging
import os
from app.metrics import incr  # métricas básicas
from time import time
from app.config import mapear_tipo_fisioterapia

router = APIRouter()
logger = logging.getLogger(__name__)

# Rate limit simple en memoria: (documento -> [timestamps recientes])
_rate_limit_window_sec = 60
_rate_limit_max = 3  # max 3 solicitudes / min por documento
_rate_bucket: dict[str, list[float]] = {}

def _check_rate(documento: str) -> bool:
    now = time()
    bucket = _rate_bucket.get(documento, [])
    # limpiar expirados
    bucket = [ts for ts in bucket if now - ts < _rate_limit_window_sec]
    allowed = len(bucket) < _rate_limit_max
    if allowed:
        bucket.append(now)
    _rate_bucket[documento] = bucket
    return allowed

@router.post("/agendar")
async def agendar_cita(cita: CitaRequest):
    """Agenda una nueva cita usando Saludtools API"""
    logger.info(f"📩 Solicitud de cita: {cita.nombre} - {cita.documento} - {cita.fecha_deseada}")
    try:
        if not _check_rate(cita.documento):
            incr('rate_limited')
            raise HTTPException(status_code=429, detail={"success": False, "mensaje": "Demasiadas solicitudes, intenta en un minuto"})

        paciente = await saludtools.buscar_paciente(cita.documento)
        if not paciente:
            datos_paciente = {
                "firstName": cita.nombre.split()[0],
                "lastName": " ".join(cita.nombre.split()[1:]) if len(cita.nombre.split()) > 1 else "",
                "documentType": 1,
                "documentNumber": cita.documento,
                "phone": cita.telefono,
                "email": cita.email if cita.email else "",
                "contactPreference": cita.preferencia_contacto or "whatsapp"
            }
            paciente = await saludtools.saludtools_client.crear_paciente(datos_paciente)
            logger.info(f"🆕 Nuevo paciente creado: {paciente.get('id')}")
        else:
            logger.info(f"👤 Paciente encontrado: {paciente.get('id')}")

        citas_existentes = await saludtools.buscar_citas_paciente(cita.documento)
        for cita_existente in citas_existentes:
            fecha_existente = datetime.fromisoformat(cita_existente.get("startDate", ""))
            if abs((fecha_existente - cita.fecha_deseada).total_seconds()) < 1800:
                incr('citas_conflicto')
                raise HTTPException(status_code=400, detail={"success": False, "mensaje": "Ya tienes una cita muy cerca de ese horario"})

        sanitized_appt_type = mapear_tipo_fisioterapia(cita.descripcion)
        clinic_env = os.getenv("SALUDTOOLS_CLINIC_ID")
        try:
            clinic_id_val = int(clinic_env) if clinic_env else None
        except Exception:
            clinic_id_val = None
        modalidad = os.getenv("SALUDTOOLS_DEFAULT_MODALITY") or "CONVENTIONAL"
        duracion_min = 60  # Cada cita dura 60 minutos según nuevas directrices
        datos_cita = {
            "patientDocumentType": 1,
            "patientDocumentNumber": cita.documento,
            "doctorDocumentType": int(os.getenv("SALUDTOOLS_DOCTOR_DOCUMENT_TYPE", "1")),
            "doctorDocumentNumber": os.getenv("SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER", "11111"),
            "startDate": cita.fecha_deseada.isoformat(),
            "endDate": (cita.fecha_deseada + timedelta(minutes=duracion_min)).isoformat(),
            "modality": modalidad,
            "appointmentState": "PENDING",
            "appointmentType": sanitized_appt_type,
            "clinic": clinic_id_val if clinic_id_val else int(os.getenv("SALUDTOOLS_CLINIC_ID", "0") or 0),
            "comment": (
                f"Agendada vía WhatsApp. Contacto: {cita.preferencia_contacto}; "
                f"Tipo: {cita.tipo_cita or sanitized_appt_type}; Especialista: {cita.especialista or 'N/D'}; "
                f"Plan: {getattr(cita, 'tipo_medicina', None) or 'N/D'}; Franja: {cita.franja or 'N/D'}; "
                f"OrdenMedica: {cita.tiene_orden_medica}"
            ),
            "notificationState": "ATTEND",
        }
        logger.info("🧪 Payload cita mínimo=%s", {k: datos_cita[k] for k in datos_cita})
        cita_creada = await saludtools.crear_cita_paciente(datos_cita)
        # Determinar si la creación remota fue exitosa (id numérico presente y code==200 si existe)
        remote_id = None
        remote_code = None
        if isinstance(cita_creada, dict):
            remote_id = cita_creada.get("id")
            try:
                remote_code = int(cita_creada.get("code")) if cita_creada.get("code") else None
            except Exception:
                remote_code = None
        remote_ok = bool(remote_id) and (remote_code in (None, 200))

        if not cita_creada or (isinstance(cita_creada, dict) and not remote_ok and cita_creada.get("error") == "DOCTOR_NOT_FOUND"):
            incr('citas_error_crear')
            raise HTTPException(status_code=400, detail={"success": False, "mensaje": "No se pudo crear la cita: médico no válido"})

        if not remote_ok:
            incr('citas_creadas_local_fallback')
        else:
            incr('citas_creadas')
            incr(f"citas_tipo_{sanitized_appt_type}")

        # Log diagnóstico siempre
        try:
            database.log_accion("CITA_INTENTO_CREAR", {
                "paciente_documento": cita.documento,
                "fecha": cita.fecha_deseada.isoformat(),
                "remote_ok": remote_ok,
                "remote_id": remote_id,
                "saludtools_response": cita_creada
            })
        except Exception as e:
            logger.warning(f"Error logging a Supabase: {e}")

        # Persistencia local enriquecida (estado distinto si remoto falló)
        local_estado = 'scheduled' if remote_ok else 'pending_remote'
        enriched_id = None
        try:
            paciente_local_id = database.obtener_paciente_por_documento(cita.documento)
            if not paciente_local_id:
                paciente_local_id = database.insertar_paciente(
                    cita.nombre,
                    cita.documento,
                    cita.telefono,
                    (cita.email or ""),
                    cita.preferencia_contacto,
                    plan_salud=getattr(cita, 'tipo_medicina', None),
                    tiene_orden_medica=getattr(cita, 'tiene_orden_medica', None)
                )
            start_at = cita.fecha_deseada
            end_at = cita.fecha_deseada + timedelta(minutes=duracion_min)
            try:
                enriched_id = database.insertar_cita_enriquecida(
                    paciente_local_id,
                    "fisio_auto",
                    sanitized_appt_type,
                    start_at,
                    end_at,
                    duracion_min,
                    cita.descripcion,
                    estado=local_estado,
                    fuente='whatsapp',
                    especialista_nombre=getattr(cita, 'especialista', None),
                    franja=getattr(cita, 'franja', None),
                    plan_salud=getattr(cita, 'tipo_medicina', None),
                    tiene_orden_medica=getattr(cita, 'tiene_orden_medica', None)
                )
                if remote_ok and isinstance(remote_id, int):
                    database.set_saludtools_id(enriched_id, remote_id)
            except Exception as e:
                logger.debug(f"No se pudo insertar cita enriquecida: {e}")
        except Exception as e:
            logger.debug(f"Fallo flujo enriched opcional: {e}")

        if remote_ok:
            logger.info(f"✅ Cita creada remotamente: {remote_id}")
            return {"success": True, "mensaje": "Cita agendada exitosamente en el sistema médico", "cita_id": remote_id, "fecha": cita.fecha_deseada.isoformat(), "remote_confirmada": True, "cita_id_local": enriched_id}
        else:
            logger.warning("⚠️ Creación remota falló (fallback local). Se requiere confirmación manual.")
            return {"success": True, "mensaje": "Cita registrada y pendiente de confirmación manual. Te confirmaremos en breve.", "remote_confirmada": False, "cita_id_local": enriched_id, "fecha": cita.fecha_deseada.isoformat(), "detalle_remoto": cita_creada}
    except HTTPException:
        raise
    except Exception as e:
        incr('citas_error_backend')
        logger.error(f"❌ Error agendando cita: {e}")
        raise HTTPException(status_code=500, detail={"success": False, "mensaje": f"Error interno del sistema: {str(e)}"})

@router.put("/editar")
async def editar_cita(data: EditarCitaRequest):
    """Edita una cita existente en Saludtools"""
    logger.info(f"📝 Editando cita: {data.documento} - {data.fecha_original} -> {data.nueva_fecha}")

    try:
        # 1. Buscar paciente
        paciente = await saludtools.buscar_paciente(data.documento)
        if not paciente:
            incr('citas_error_paciente')
            raise HTTPException(
                status_code=404,
                detail={"success": False, "mensaje": "Paciente no encontrado"}
            )

        # 2. Buscar citas del paciente
        citas = await saludtools.buscar_citas_paciente(data.documento)
        
        # 3. Encontrar la cita a editar
        cita_a_editar = None
        for cita in citas:
            fecha_cita = datetime.fromisoformat(cita.get("startDate", ""))
            if abs((fecha_cita - data.fecha_original).total_seconds()) < 900:  # 15 minutos de tolerancia
                cita_a_editar = cita
                break

        if not cita_a_editar:
            incr('citas_error_no_encontrada')
            raise HTTPException(
                status_code=404,
                detail={"success": False, "mensaje": "No se encontró una cita en la fecha especificada"}
            )

        # 4. Actualizar cita en Saludtools
        nuevos_datos = {
            "startDate": data.nueva_fecha.isoformat(),
            "endDate": (data.nueva_fecha + timedelta(minutes=30)).isoformat(),
            "notes": f"Cita reprogramada vía WhatsApp. Fecha original: {data.fecha_original.isoformat()}"
        }

        cita_actualizada = await saludtools.editar_cita_paciente(
            cita_a_editar.get("id"), 
            nuevos_datos
        )

        if not cita_actualizada:
            incr('citas_error_editar')
            raise HTTPException(
                status_code=500,
                detail={"success": False, "mensaje": "Error al actualizar la cita en el sistema médico"}
            )

        # 5. Log en Supabase
        try:
            database.log_accion("CITA_EDITADA", {
                "paciente_documento": data.documento,
                "cita_id": cita_a_editar.get("id"),
                "fecha_original": data.fecha_original.isoformat(),
                "fecha_nueva": data.nueva_fecha.isoformat()
            })
        except Exception as e:
            logger.warning(f"Error logging a Supabase: {e}")
        incr('citas_editadas')
        logger.info(f"✅ Cita editada exitosamente: {cita_a_editar.get('id')}")
        return {
            "success": True,
            "mensaje": "Cita reprogramada exitosamente",
            "nueva_fecha": data.nueva_fecha.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        incr('citas_error_backend')
        logger.error(f"❌ Error editando cita: {e}")
        raise HTTPException(
            status_code=500,
            detail={"success": False, "mensaje": f"Error interno: {str(e)}"}
        )

@router.delete("/eliminar")
async def eliminar_cita(data: EliminarCitaRequest):
    """Cancela una cita en Saludtools"""
    logger.info(f"🗑️ Cancelando cita: {data.documento} - {data.fecha}")

    try:
        # 1. Buscar paciente
        paciente = await saludtools.buscar_paciente(data.documento)
        if not paciente:
            incr('citas_error_paciente')
            raise HTTPException(
                status_code=404,
                detail={"success": False, "mensaje": "Paciente no encontrado"}
            )

        # 2. Buscar citas del paciente
        citas = await saludtools.buscar_citas_paciente(data.documento)
        
        # 3. Encontrar la cita a cancelar
        cita_a_cancelar = None
        for cita in citas:
            fecha_cita = datetime.fromisoformat(cita.get("startDate", ""))
            if abs((fecha_cita - data.fecha).total_seconds()) < 900:  # 15 minutos de tolerancia
                cita_a_cancelar = cita
                break

        if not cita_a_cancelar:
            incr('citas_error_no_encontrada')
            raise HTTPException(
                status_code=404,
                detail={"success": False, "mensaje": "No se encontró una cita en la fecha especificada"}
            )

        # 4. Cancelar cita en Saludtools
        cancelada = await saludtools.cancelar_cita_paciente(cita_a_cancelar.get("id"))

        if not cancelada:
            incr('citas_error_cancelar')
            raise HTTPException(
                status_code=500,
                detail={"success": False, "mensaje": "Error al cancelar la cita en el sistema médico"}
            )

        # 5. Log en Supabase
        try:
            database.log_accion("CITA_CANCELADA", {
                "paciente_documento": data.documento,
                "cita_id": cita_a_cancelar.get("id"),
                "fecha": data.fecha.isoformat()
            })
        except Exception as e:
            logger.warning(f"Error logging a Supabase: {e}")
        incr('citas_canceladas')
        logger.info(f"✅ Cita cancelada exitosamente: {cita_a_cancelar.get('id')}")
        return {
            "success": True,
            "mensaje": "Cita cancelada exitosamente"
        }

    except HTTPException:
        raise
    except Exception as e:
        incr('citas_error_backend')
        logger.error(f"❌ Error cancelando cita: {e}")
        raise HTTPException(
            status_code=500,
            detail={"success": False, "mensaje": f"Error interno: {str(e)}"}
        )

@router.get("/citas")
async def listar_citas(documento: str = Query(..., description="Documento del paciente")):
    """Lista todas las citas de un paciente desde Saludtools"""
    logger.info(f"📋 Listando citas para documento: {documento}")

    try:
        # 1. Verificar que el paciente existe
        paciente = await saludtools.buscar_paciente(documento)
        if not paciente:
            raise HTTPException(
                status_code=404,
                detail={"success": False, "mensaje": "Paciente no encontrado"}
            )

        # 2. Obtener citas desde Saludtools
        citas = await saludtools.buscar_citas_paciente(documento)

        # 3. Formatear respuesta
        citas_formateadas = []
        for cita in citas:
            try:
                fecha_inicio = datetime.fromisoformat(cita.get("startDate", ""))
                citas_formateadas.append({
                    "id": cita.get("id"),
                    "fecha": fecha_inicio.isoformat(),
                    "fecha_legible": fecha_inicio.strftime("%d/%m/%Y %H:%M"),
                    "tipo": cita.get("appointmentType", "Consulta"),
                    "estado": cita.get("appointmentState", "PENDING"),
                    "notas": cita.get("notes", "")
                })
            except Exception as e:
                logger.warning(f"Error formateando cita {cita.get('id')}: {e}")

        logger.info(f"📋 Encontradas {len(citas_formateadas)} citas para {documento}")
        return {
            "success": True,
            "citas": citas_formateadas,
            "total": len(citas_formateadas)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listando citas: {e}")
        raise HTTPException(
            status_code=500,
            detail={"success": False, "mensaje": f"Error interno: {str(e)}"}
        )

@router.get("/disponibilidad")
async def disponibilidad(documento: str = Query(..., description="Documento del paciente"), dias: int = 7):
    """
    Genera horarios disponibles considerando las citas existentes del paciente
    Nota: En producción, esto debería integrar con el calendario de disponibilidad de Saludtools
    """
    logger.info(f"🕐 Generando disponibilidad para {documento}, próximos {dias} días")

    try:
        # Por ahora, generamos disponibilidad básica
        # TODO: Integrar con calendario real de Saludtools cuando esté disponible
        
        horarios_disponibles = []
        fecha_actual = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        for dia in range(1, dias + 1):
            fecha_dia = fecha_actual + timedelta(days=dia)
            
            # Solo días laborales (lunes a viernes)
            if fecha_dia.weekday() < 5:
                # Horarios de 8:00 AM a 5:00 PM cada 30 minutos
                for hora in range(8, 17):
                    for minuto in [0, 30]:
                        horario = fecha_dia.replace(hour=hora, minute=minuto)
                        horarios_disponibles.append({
                            "fecha": horario.isoformat(),
                            "fecha_legible": horario.strftime("%d/%m/%Y %H:%M"),
                            "disponible": True  # TODO: Verificar con Saludtools
                        })

        # Limitar a los primeros 10 horarios
        return {
            "success": True,
            "disponibilidad": horarios_disponibles[:10],
            "nota": "Disponibilidad básica. En producción se integrará con calendario real de Saludtools"
        }

    except Exception as e:
        logger.error(f"❌ Error generando disponibilidad: {e}")
        raise HTTPException(
            status_code=500,
            detail={"success": False, "mensaje": f"Error interno: {str(e)}"}
        )

@router.get("/citas/by-remote/{saludtools_id}")
async def obtener_cita_por_saludtools_id(saludtools_id: int):
    """Recupera una cita local usando el id remoto (columna saludtools_id).

    Nota: actualmente solo consulta la BD local (no hay endpoint directo de Saludtools para buscar por id aislado en la integración de eventos)."""
    try:
        from app import database
        cita = database.buscar_cita_por_saludtools_id(saludtools_id)
        if not cita:
            raise HTTPException(status_code=404, detail={"success": False, "mensaje": "Cita no encontrada localmente"})
        return {"success": True, "origen": "local", "cita": cita}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error buscando cita por remote id {saludtools_id}: {e}")
        raise HTTPException(status_code=500, detail={"success": False, "mensaje": "Error interno"})