"""
Notificaciones a secretarias por WhatsApp (Twilio).

Envía alertas cuando detectamos un flujo que debe ser atendido por humano.
Config mediante variables de entorno:
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_WHATSAPP_FROM (ej: whatsapp:+14155238886 en sandbox)
- SECRETARY_WHATSAPP_TO (lista separada por comas; ej: "+573001112233,+573004445566")
- NOTIFY_SECRETARIES=true|false (opcional, default true en prod)
- ENVIRONMENT=testing|prod (controla comportamiento por entorno)
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

try:
    from twilio.rest import Client  # type: ignore
except Exception:  # pragma: no cover - twilio puede no estar instalado en algunos entornos
    Client = None  # fallback


def _parse_secretary_numbers(raw: str) -> list[str]:
    """Parsea una lista separada por comas a formato whatsapp:+<number>.

    Acepta entradas con o sin prefijo "whatsapp:" y con/ sin espacios.
    """
    if not raw:
        return []
    nums: list[str] = []
    for item in raw.split(","):
        n = item.strip()
        if not n:
            continue
        if not n.startswith("whatsapp:"):
            n = f"whatsapp:{n}"
        nums.append(n)
    return nums


def _twilio_client():
    if Client is None:
        logging.warning("Twilio Client no disponible; omitiendo envíos a secretarias.")
        return None
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        logging.warning("Credenciales de Twilio faltantes; no se enviarán notificaciones a secretarias.")
        return None
    try:
        return Client(sid, token)
    except Exception as e:
        logging.error(f"Error creando cliente Twilio: {e}")
        return None


def _should_notify() -> bool:
    # Permite desactivar en testing
    env = (os.getenv("ENVIRONMENT") or "testing").lower()
    flag = os.getenv("NOTIFY_SECRETARIES", "").lower()
    if flag in {"0", "false", "no"}:
        return False
    # Por defecto, en testing también notificamos si hay números y twilio
    return True


def notify_admin_critical(evento: str, detalle: str, contexto: Optional[dict] = None) -> dict:
    """Envía una alerta crítica a un número ADMIN_WHATSAPP si está configurado.

    Variables de entorno:
      - ADMIN_WHATSAPP (ej: +573001112233)
      - TWILIO_WHATSAPP_FROM
    Retorna dict con resultado o motivo de omisión.
    """
    admin_raw = os.getenv("ADMIN_WHATSAPP")
    if not admin_raw:
        return {"skipped": "no-admin-config"}
    if not _should_notify():
        return {"skipped": "notifications-disabled"}
    client = _twilio_client()
    from_number = os.getenv("TWILIO_WHATSAPP_FROM")
    if not client or not from_number:
        return {"skipped": "missing-twilio-config"}
    admin_to = admin_raw if admin_raw.startswith("whatsapp:") else f"whatsapp:{admin_raw}"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    ctx_lines = []
    if contexto:
        for k,v in list(contexto.items())[:8]:
            if v is None:
                continue
            sval = str(v)
            if len(sval) > 100:
                sval = sval[:97] + '…'
            ctx_lines.append(f"• {k}: {sval}")
    body = (
        "🚨 ALERTA CRÍTICA SISTEMA\n"
        f"🕒 {ts}\n"
        f"⚠️ Evento: {evento}\n"
        f"📄 Detalle: {detalle[:300]}\n"
        + ("\n" + "\n".join(ctx_lines) if ctx_lines else "")
    )
    try:
        msg = client.messages.create(from_=from_number, to=admin_to, body=body)
        return {"sent": True, "sid": getattr(msg, "sid", None)}
    except Exception as e:
        logging.error(f"Error enviando alerta crítica: {e}")
        return {"sent": False, "error": str(e)}


def notify_secretaries_escalation(
    telefono_usuario: str,
    motivo: str,
    ultimo_mensaje: str,
    extras: Optional[dict] = None,
    to_numbers_override: Optional[list[str]] = None,
) -> dict:
    """Envía una alerta por WhatsApp a todas las secretarias configuradas.
    
    FLEXIBLE: Construye mensaje con los datos disponibles, no requiere todos los campos.
    
    Retorna un resumen del intento de envío por cada destinatario.
    """
    results: dict = {"sent": [], "skipped": [], "errors": []}

    if not _should_notify():
        results["skipped"].append("not-enabled")
        return results

    client = _twilio_client()
    from_number = os.getenv("TWILIO_WHATSAPP_FROM")
    to_numbers = []
    if to_numbers_override:
        # Permite pasar números explícitos (ya sea con o sin prefijo whatsapp:)
        for n in to_numbers_override:
            if n.startswith("whatsapp:"):
                to_numbers.append(n)
            else:
                to_numbers.append(f"whatsapp:{n}")
    else:
        to_raw = os.getenv("SECRETARY_WHATSAPP_TO", "")
        to_numbers = _parse_secretary_numbers(to_raw)

    if not client or not from_number or not to_numbers:
        missing = {
            "client": bool(client),
            "from": bool(from_number),
            "to_numbers": bool(to_numbers),
        }
        logging.warning(f"Notificación a secretarias omitida por falta de config: {missing}")
        results["skipped"].append("missing-config")
        return results

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Construir mensaje de forma flexible - solo con datos disponibles
    message_parts = ["📣 Nuevo caso para gestión humana"]
    message_parts.append(f"🕒 {ts}")
    
    # Solo agregar campos si existen y son válidos
    if telefono_usuario and telefono_usuario != "Desconocido":
        message_parts.append(f"👤 Usuario: {telefono_usuario}")
    
    if motivo:
        message_parts.append(f"🔎 Motivo: {motivo}")
    
    if ultimo_mensaje:
        # Limitar longitud del mensaje
        msg_preview = ultimo_mensaje[:500] if len(ultimo_mensaje) > 500 else ultimo_mensaje
        message_parts.append(f"💬 Último mensaje: {msg_preview}")
    
    # Agregar extras si existen
    if extras:
        extra_lines = []
        for k, v in extras.items():
            if v is None or v == "":
                continue
            # Limitar longitud de valores largos
            val = str(v)
            if len(val) > 140:
                val = val[:137] + '…'
            extra_lines.append(f"• {k}: {val}")
        
        if extra_lines:
            message_parts.append("\n" + "\n".join(extra_lines))
    
    message_parts.append("\nResponde al usuario por WhatsApp o llámalo directamente.")
    
    body = "\n".join(message_parts)

    # TESTING MODE: Por defecto permitir auto-notificación (false), no bloquear ("0")
    skip_self = (os.getenv("SKIP_SELF_NOTIFICATION", "false").lower() in {"1","true","yes","on"})
    raw_user = telefono_usuario.replace("whatsapp:", "") if telefono_usuario else ""
    for to in to_numbers:
        # Evitar notificación a uno mismo (mismo número que el usuario) si flag activo
        if skip_self and raw_user and to.replace("whatsapp:", "") == raw_user:
            results["skipped"].append({"to": to, "reason": "self-notification"})
            continue
        try:
            msg = client.messages.create(from_=from_number, to=to, body=body)
            results["sent"].append({"to": to, "sid": getattr(msg, "sid", None)})
        except Exception as e:
            logging.error(f"Error enviando a secretaria {to}: {e}")
            results["errors"].append({"to": to, "error": str(e)})

    return results

__all__ = [
    'notify_secretaries_escalation', 'notify_admin_critical'
]
