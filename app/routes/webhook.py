# app/routes/webhook.py
from fastapi import APIRouter, Request, Response
import xml.etree.ElementTree as ET
from app import ai
from app import config
from app import notifications
from app import database as db
import json
import os
import traceback
from app.routes.citas import agendar_cita, editar_cita, eliminar_cita, listar_citas
from app.models import CitaRequest, EditarCitaRequest, EliminarCitaRequest
import dateutil.parser
from datetime import datetime, timedelta, timezone
import html
import logging

router = APIRouter()
API_URL = os.getenv("API_URL", "http://localhost:8000")

# Configuración de logging a archivo
# Asegura carpeta de logs
try:
    os.makedirs('logs', exist_ok=True)
except Exception:
    pass

logging.basicConfig(
    filename=os.path.join('logs', 'agendamiento.log'),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Memoria mejorada: historial de conversación (usuario+IA) por teléfono
conversaciones = {}
# Estado de escalaciones a humano: telefono -> {"activo": bool, "timestamp": datetime, "motivo": str, "historial": list}
escalaciones = {}
# Gestión simple de secretarias y cola en memoria
secretarias = {}  # whatsapp:+57... -> {assigned: int}
cola_casos = []   # lista de caseIds en espera
case_to_phone = {}  # caseId -> telefono
ESCALATION_KEYWORDS = [
    "cita medica", "cita médica", "medico", "médico", "doctor", "especialista",
    "humano", "persona", "secretaria", "secretaría", "agente", "asesor"
]
MAX_TURNOS = 5  # Debe coincidir con el de ai.py
USE_DB_HANDOFF = os.getenv("HANDOFF_PERSISTENCE", "0").lower() in {"1","true","yes","on"}

def _gen_case_id() -> str:
    try:
        import uuid
        return f"CAS-{str(uuid.uuid4())[:8].upper()}"
    except Exception:
        return f"CAS-{int(datetime.utcnow().timestamp())}"

def _ensure_secretarias_loaded():
    if secretarias:
        return
    raw = os.getenv("SECRETARY_WHATSAPP_TO", "")
    nums = [n.strip() for n in raw.split(',') if n.strip()]
    for n in nums:
        key = n if n.startswith('whatsapp:') else f'whatsapp:{n}'
        secretarias.setdefault(key, {"assigned": 0})

def _pick_available_secretaria() -> str | None:
    _ensure_secretarias_loaded()
    # Capacidad por secretaria (por defecto 1)
    cap = 1
    try:
        cap = max(1, int(os.getenv("SECRETARY_CAPACITY", "1")))
    except Exception:
        cap = 1
    candidates = [(num, info) for num, info in secretarias.items() if int(info.get("assigned", 0)) < cap]
    if not candidates:
        return None
    candidates.sort(key=lambda kv: int(kv[1].get("assigned", 0)))
    return candidates[0][0]

def _assign_next_from_queue():
    """Intenta asignar el siguiente caso en cola a una secretaria disponible y notifica."""
    if not cola_casos:
        return None
    target = _pick_available_secretaria()
    if not target:
        return None
    case_id = cola_casos.pop(0)
    telefono = case_to_phone.get(case_id)
    if not telefono or telefono not in escalaciones:
        return None
    # Marcar asignación
    info = secretarias.setdefault(target, {"assigned": 0})
    info["assigned"] = int(info.get("assigned", 0)) + 1
    secretarias[target] = info
    escalaciones[telefono]["assignment"] = {"assigned_to": target}
    escalaciones[telefono].pop("queued", None)
    # Notificar a secretaria asignada
    try:
        # Intentar extraer último mensaje del usuario del historial
        ultimo_msg = ""
        for rol, txt in reversed(escalaciones[telefono].get("historial", [])):
            if rol == "usuario":
                ultimo_msg = txt
                break
        notifications.notify_secretaries_escalation(
            telefono_usuario=telefono,
            motivo="queued_case_assigned",
            ultimo_mensaje=ultimo_msg or "(sin mensaje reciente)",
            extras={"caseId": case_id},
            to_numbers_override=[target],
        )
    except Exception as _e:
        logging.warning(f"Fallo al notificar secretaria asignada de cola: {_e}")
    return {"caseId": case_id, "assigned_to": target}

def twiml_message(text: str):
    try:
        response = ET.Element("Response")
        message = ET.SubElement(response, "Message")
        message.text = html.escape(text if text else "")
        xml = ET.tostring(response, encoding="unicode")
        print(f"[twiml_message] XML generado: {xml}")
        return Response(content=xml, media_type="application/xml")
    except Exception as e:
        print(f"[twiml_message] Error generando XML: {e}")
        print(traceback.format_exc())
        return Response(content="<Response><Message>Ocurrió un error inesperado. Intenta de nuevo.</Message></Response>", media_type="application/xml")

@router.post("/webhook/twilio")
async def twilio_webhook(request: Request):
    try:
        form = await request.form()
        mensaje = form.get("Body", "").strip()
        telefono = form.get("From", "")
        print(f"[webhook] 📩 Mensaje recibido: '{mensaje}'")
        logging.info(f"Mensaje recibido: '{mensaje}'")

        # Si ya está escalado a humano: solo almacenar y responder placeholder
        if telefono in escalaciones and escalaciones[telefono]["activo"]:
            hist = escalaciones[telefono].setdefault("historial", [])
            hist.append(("usuario", mensaje))
            return twiml_message("👩‍⚕️ Un miembro del equipo ya está al tanto y continuará la conversación enseguida. Si deseas volver al asistente escribe 'reiniciar'.")

        historial = conversaciones.get(telefono, [])

        # SOLO limpia historial y responde si el usuario explícitamente pide reinicio
        if mensaje and any(cmd in mensaje.lower() for cmd in ["reiniciar", "empezar de nuevo", "ayuda"]):
            conversaciones[telefono] = []
            respuesta_ia = "He reiniciado la conversación. ¿En qué puedo ayudarte hoy? ¿Quieres agendar, consultar, editar o cancelar una cita?"
            print(f"[webhook] Respuesta de reinicio: {respuesta_ia}")
            return twiml_message(respuesta_ia)

        # Detección temprana de intención de escalación a humano
        lower_msg = mensaje.lower()
        if any(kw in lower_msg for kw in ESCALATION_KEYWORDS) and any(term in lower_msg for term in ["cita medica", "cita médica", "doctor", "especialista", "humano", "secretaria", "secretaría"]):
            conversaciones.setdefault(telefono, []).append(("usuario", mensaje))
            case_id = _gen_case_id()
            escalaciones[telefono] = {
                "activo": True,
                "timestamp": datetime.utcnow().isoformat(),
                "motivo": "detected_medical_manual_flow",
                "historial": conversaciones[telefono][:],
                "caseId": case_id,
            }
            case_to_phone[case_id] = telefono
            logging.info(f"[escalacion] Escalada a humano para {telefono}")
            try:
                target_sec = _pick_available_secretaria()
                if target_sec:
                    notif = notifications.notify_secretaries_escalation(
                        telefono_usuario=telefono,
                        motivo="detected_medical_manual_flow",
                        ultimo_mensaje=mensaje,
                        extras={"observacion": "Escalada por palabras clave", "caseId": case_id},
                        to_numbers_override=[target_sec],
                    )
                    escalaciones[telefono]["notification"] = notif
                    # Incrementar carga
                    if USE_DB_HANDOFF:
                        db.handoff_upsert_secretary(target_sec)
                        db.handoff_inc_assigned(target_sec, +1)
                        db.handoff_create_escalation(case_id, telefono, "detected_medical_manual_flow", {"historial": conversaciones[telefono][:]}, "claimed")
                        db.handoff_set_assignment(case_id, target_sec, "claimed")
                    else:
                        info = secretarias.setdefault(target_sec, {"assigned": 0})
                        info["assigned"] = int(info.get("assigned", 0)) + 1
                        secretarias[target_sec] = info
                    escalaciones[telefono]["assignment"] = {"assigned_to": target_sec}
                else:
                    escalaciones[telefono]["queued"] = True
                    if USE_DB_HANDOFF:
                        db.handoff_create_escalation(case_id, telefono, "detected_medical_manual_flow", {"historial": conversaciones[telefono][:]}, "queued")
                        db.handoff_mark_queued(case_id)
                    else:
                        cola_casos.append(case_id)
            except Exception as _e:
                logging.warning(f"Fallo al notificar secretarias: {_e}")
            return twiml_message("📨 He derivado tu solicitud a una secretaria para atención personalizada. En breve te responderán. Escribe 'reiniciar' si deseas volver conmigo.")

        # Acumula historial normalmente
        historial.append(("usuario", mensaje))

        try:
            respuesta_ia = ai.analizar_mensaje(mensaje, historial)
            print(f"[webhook] IA responde: {respuesta_ia}")
            logging.info(f"IA responde: {respuesta_ia}")
        except Exception as e:
            print(f"[webhook] Error IA: {e}")
            return twiml_message("Lo siento, hubo un error al procesar tu mensaje con la IA.")

        historial.append(("valeria", respuesta_ia))

        # Prevención de loops: solo si el mensaje de la IA es exactamente igual al anterior
        if len(historial) >= 2 and historial[-1][1].strip() == historial[-2][1].strip():
            print("[webhook] ⚠️ Mensaje repetido detectado, sugiriendo reinicio.")
            return twiml_message("🤖 Parece que estamos repitiendo la conversación. Escribe 'reiniciar' para comenzar de nuevo.")

        conversaciones[telefono] = historial
        print(f"[DEBUG] TELEFONO: {telefono}")
        print(f"[DEBUG] HISTORIAL: {historial}")

        try:
            data = json.loads(respuesta_ia)
            print(f"[webhook] JSON detectado: {json.dumps(data, indent=2)}")
            logging.info(f"JSON detectado: {json.dumps(data, indent=2)}")
            intencion = data.get("intencion")
            datos = data.get("datos", {})
        except json.JSONDecodeError:
            return twiml_message(respuesta_ia)

        required_fields = {
            "agendar": ["nombre", "documento", "fecha_deseada", "descripcion", "preferencia_contacto"],
            "consultar": ["documento"],
            "cancelar": ["documento", "fecha"],
            "editar": ["documento", "fecha_original", "nueva_fecha"]
        }

        fecha_campos = ["fecha_deseada", "fecha", "fecha_original", "nueva_fecha"]
        for campo in fecha_campos:
            if campo in datos and isinstance(datos[campo], str) and datos[campo]:
                try:
                    datos[campo] = dateutil.parser.parse(datos[campo])
                except Exception as e:
                    return twiml_message(f"El formato de la fecha no es válido para '{campo}'. Usa el formato YYYY-MM-DD HH:MM.")

        # Ajuste: nunca pedir email si la preferencia es solo WhatsApp
        campos_requeridos = required_fields.get(intencion, [])
        if intencion == "agendar" and datos.get("preferencia_contacto") == "whatsapp":
            campos_requeridos = [c for c in campos_requeridos if c != "email"]
        faltantes = [campo for campo in campos_requeridos if not datos.get(campo)]
        if faltantes:
            return twiml_message(f"Para continuar necesito: {', '.join(faltantes)}. ¿Podrías proporcionarlos?")

        try:
            if intencion == "agendar":
                # Reglas de derivación: citas NO fisioterapia van a secretaría
                def _is_physio(datos_json: dict) -> bool:
                    tipo = (datos_json.get("tipo_cita") or "").replace(" ", "").upper()
                    if tipo in {"PRIMERAVEZ", "CONTROL", "ACONDICIONAMIENTO"}:
                        return True
                    # Si se especifica especialista, validar su categoría
                    esp_nombre = (datos_json.get("especialista") or "").strip().lower()
                    if esp_nombre:
                        for esp in config.ESPECIALISTAS:
                            if esp.get("nombre", "").strip().lower() == esp_nombre:
                                return esp.get("categoria") == "fisioterapia"
                    return False

                if not _is_physio(datos):
                    conversaciones.setdefault(telefono, []).append(("usuario", mensaje))
                    case_id = _gen_case_id()
                    escalaciones[telefono] = {
                        "activo": True,
                        "timestamp": datetime.utcnow().isoformat(),
                        "motivo": "agendar_medica_manual",
                        "historial": conversaciones[telefono][:],
                        "caseId": case_id,
                    }
                    case_to_phone[case_id] = telefono
                    extras = {
                        "nombre": datos.get("nombre"),
                        "documento": datos.get("documento"),
                        "telefono_reportado": datos.get("telefono"),
                        "preferencia_contacto": datos.get("preferencia_contacto"),
                        "descripcion": datos.get("descripcion"),
                        "fecha_deseada": str(datos.get("fecha_deseada")) if datos.get("fecha_deseada") else None,
                    }
                    try:
                        target_sec = _pick_available_secretaria()
                        if target_sec:
                            notif = notifications.notify_secretaries_escalation(
                                telefono_usuario=telefono,
                                motivo="agendar_medica_manual",
                                ultimo_mensaje=mensaje,
                                extras={**extras, "caseId": case_id},
                                to_numbers_override=[target_sec],
                            )
                            escalaciones[telefono]["notification"] = notif
                            if USE_DB_HANDOFF:
                                db.handoff_upsert_secretary(target_sec)
                                db.handoff_inc_assigned(target_sec, +1)
                                db.handoff_create_escalation(case_id, telefono, "agendar_medica_manual", {"historial": conversaciones[telefono][:], **extras}, "claimed")
                                db.handoff_set_assignment(case_id, target_sec, "claimed")
                            else:
                                info = secretarias.setdefault(target_sec, {"assigned": 0})
                                info["assigned"] = int(info.get("assigned", 0)) + 1
                                secretarias[target_sec] = info
                            escalaciones[telefono]["assignment"] = {"assigned_to": target_sec}
                        else:
                            escalaciones[telefono]["queued"] = True
                            if USE_DB_HANDOFF:
                                db.handoff_create_escalation(case_id, telefono, "agendar_medica_manual", {"historial": conversaciones[telefono][:], **extras}, "queued")
                                db.handoff_mark_queued(case_id)
                            else:
                                cola_casos.append(case_id)
                    except Exception as _e:
                        logging.warning(f"Fallo al notificar secretarias: {_e}")
                    return twiml_message("📨 Esta solicitud será atendida por una secretaria. En breve se comunicarán contigo para coordinar tu cita médica. Si deseas volver al asistente, escribe 'reiniciar'.")

                if datos.get("preferencia_contacto") == "whatsapp" and not datos.get("email"):
                    datos["email"] = None

                fecha = datos["fecha_deseada"]
                ahora = datetime.now(timezone.utc)
                # Asegura que la fecha tenga zona horaria UTC
                if fecha.tzinfo is None:
                    fecha = fecha.replace(tzinfo=timezone.utc)
                if not (ahora <= fecha <= ahora + timedelta(days=14)):
                    return twiml_message("⚠️ Las citas solo pueden agendarse dentro de los próximos 14 días. Por favor, proporciona una fecha válida.")

                cita_req = CitaRequest(**datos)
                respuesta = await agendar_cita(cita_req)
                conversaciones[telefono] = []
                print(f"[webhook] Cita agendada: {respuesta}")
                logging.info(f"Cita agendada: {respuesta}")
                return twiml_message("✅ ¡Listo! Tu cita fue agendada con éxito. Si necesitas otra gestión, solo dime.")

            if intencion == "consultar":
                doc = datos.get("documento")
                resultado = await listar_citas(documento=doc)
                citas = resultado.get("citas", [])
                conversaciones[telefono] = []
                if not citas:
                    return twiml_message("📭 No tienes citas agendadas.")
                msg = "📅 Tus próximas citas:\n" + "\n".join([f"{c['fecha']} - {c['descripcion']}" for c in citas])
                return twiml_message(msg)

            if intencion == "cancelar":
                eliminar_req = EliminarCitaRequest(**datos)
                respuesta = await eliminar_cita(eliminar_req)
                conversaciones[telefono] = []
                print(f"[webhook] Cita cancelada: {respuesta}")
                logging.info(f"Cita cancelada: {respuesta}")
                return twiml_message("🗑️ Tu cita ha sido cancelada. Si deseas hacer otra gestión, estaré aquí para ayudarte.")

            if intencion == "editar":
                editar_req = EditarCitaRequest(**datos)
                respuesta = await editar_cita(editar_req)
                conversaciones[telefono] = []
                print(f"[webhook] Cita editada: {respuesta}")
                logging.info(f"Cita editada: {respuesta}")
                return twiml_message("🔄 Tu cita ha sido modificada con éxito. ¡Gracias por usar nuestro servicio!")

            return twiml_message("No entendí bien tu solicitud. ¿Deseas agendar, consultar, editar o cancelar una cita?")

        except Exception as e:
            print(f"[webhook] Error de backend: {e}")
            logging.error(f"Error de backend: {e}")
            detalle = getattr(e, "detail", str(e))
            if isinstance(detalle, dict):
                detalle = detalle.get("mensaje", str(detalle))
            return twiml_message(f"❌ Ocurrió un error: {detalle}")

    except Exception as e:
        print(f"[webhook] Error general: {e}")
        logging.error(f"Error general: {e}\n{traceback.format_exc()}")
        return twiml_message("Ocurrió un error inesperado. Intenta de nuevo.")


@router.get("/human/escalations")
async def listar_escalaciones():
    """Devuelve las conversaciones escaladas a humano (en memoria)."""
    return {
        "total": len(escalaciones),
    "items": escalaciones,
    "secretarias": secretarias,
    "queue": cola_casos,
    }


@router.post("/human/release/{telefono}")
async def liberar_escalacion(telefono: str):
    """Libera una escalación y devuelve el contexto. Permite que el bot retome si el usuario escribe nuevamente."""
    if telefono in escalaciones:
        data = escalaciones.pop(telefono)
    # Si estaba asignado a alguna secretaria, decrementa su carga
        asign = data.get("assignment", {})
        to = asign.get("assigned_to") if isinstance(asign, dict) else None
        if to and to in secretarias:
            secretarias[to]["assigned"] = max(0, int(secretarias[to].get("assigned", 0)) - 1)
    # Intentar asignar siguientes en cola
    asign_next = _assign_next_from_queue()
    return {"success": True, "liberado": telefono, "contexto": data, "next_assigned": asign_next}
    return {"success": False, "mensaje": "Telefono no estaba escalado"}


@router.post("/human/claim/{telefono}")
async def claim_escalacion(telefono: str, request: Request):
    """Asigna el caso a una secretaria. Usa ?to=whatsapp:+57... o elige automáticamente la menos cargada."""
    if telefono not in escalaciones:
        return {"success": False, "mensaje": "Caso no encontrado"}
    _ensure_secretarias_loaded()
    to = request.query_params.get("to") or request.headers.get("X-Secretary")
    if to and not to.startswith("whatsapp:"):
        to = f"whatsapp:{to}"
    if not to:
        to = _pick_available_secretaria()
    if not to:
        # sin capacidad: en cola
        case_id = escalaciones[telefono].get("caseId")
        if case_id and case_id not in cola_casos:
            cola_casos.append(case_id)
        return {"success": False, "queued": True}
    info = secretarias.setdefault(to, {"assigned": 0})
    info["assigned"] = int(info.get("assigned", 0)) + 1
    secretarias[to] = info
    escalaciones[telefono]["assignment"] = {"assigned_to": to}
    return {"success": True, "assigned_to": to, "caseId": escalaciones[telefono].get("caseId")}


@router.post("/human/resolve/{telefono}")
async def resolve_escalacion(telefono: str):
    """Marca el caso como resuelto y libera la secretaria."""
    if telefono not in escalaciones:
        return {"success": False, "mensaje": "Caso no encontrado"}
    data = escalaciones.pop(telefono)
    asign = data.get("assignment", {})
    to = asign.get("assigned_to") if isinstance(asign, dict) else None
    if to and to in secretarias:
        secretarias[to]["assigned"] = max(0, int(secretarias[to].get("assigned", 0)) - 1)
    # Intentar asignar siguientes en cola
    asign_next = _assign_next_from_queue()
    # Limpiar reverse index
    cid = data.get("caseId")
    if cid and cid in case_to_phone:
        case_to_phone.pop(cid, None)
    return {"success": True, "resuelto": telefono, "contexto": data, "next_assigned": asign_next}
