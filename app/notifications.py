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


def notify_secretaries_escalation(
    telefono_usuario: str,
    motivo: str,
    ultimo_mensaje: str,
    extras: Optional[dict] = None,
    to_numbers_override: Optional[list[str]] = None,
) -> dict:
    """Envía una alerta por WhatsApp a todas las secretarias configuradas.

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
    extra_lines = []
    if extras:
        for k, v in extras.items():
            if v is None:
                continue
            extra_lines.append(f"• {k}: {v}")
    extra_block = ("\n" + "\n".join(extra_lines)) if extra_lines else ""

    body = (
        "📣 Nuevo caso para gestión humana\n"
        f"🕒 {ts}\n"
        f"👤 Usuario: {telefono_usuario}\n"
        f"🔎 Motivo: {motivo}\n"
        f"💬 Último mensaje: {ultimo_mensaje[:500]}\n"
        f"{extra_block}\n\n"
        "Responde al usuario por WhatsApp o llámalo directamente."
    )

    for to in to_numbers:
        try:
            msg = client.messages.create(from_=from_number, to=to, body=body)
            results["sent"].append({"to": to, "sid": getattr(msg, "sid", None)})
        except Exception as e:
            logging.error(f"Error enviando a secretaria {to}: {e}")
            results["errors"].append({"to": to, "error": str(e)})

    return results
