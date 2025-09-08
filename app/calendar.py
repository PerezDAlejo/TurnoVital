from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

# Dependencias de Google son opcionales en modo offline
try:  # pragma: no cover - import opcional
    from google.oauth2 import service_account  # type: ignore
    from googleapiclient.discovery import build  # type: ignore
except Exception:  # Si no están instaladas o hay fallo, seguimos en modo offline
    service_account = None  # type: ignore
    build = None  # type: ignore


load_dotenv()

CALENDAR_ID = os.getenv("CALENDAR_ID")
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Inicialización segura (lazy/condicional) para permitir modo offline
service = None
if (
    os.getenv("CALENDAR_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
    and service_account is not None
    and build is not None
    and CREDENTIALS_PATH
    and os.path.exists(CREDENTIALS_PATH)
    and CALENDAR_ID
):
    try:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        service = build("calendar", "v3", credentials=creds)
    except Exception as _e:  # pragma: no cover - si falla, trabajamos offline
        service = None

def ahora_utc():
    return datetime.now(timezone.utc)

def ensure_utc(dt):
    """Convierte cualquier datetime a timezone-aware en UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def esta_disponible(citas, nueva_fecha, duracion=30):
    nueva_fecha = ensure_utc(nueva_fecha)
    for cita in citas:
        inicio = ensure_utc(cita["fecha"])
        fin = inicio + timedelta(minutes=duracion)
        if inicio <= nueva_fecha < fin:
            return False
    return True

def disponibilidad_google_calendar(fecha, duracion=30):
    print(">>> disponibilidad_google_calendar called", flush=True)
    fecha = ensure_utc(fecha)
    fecha_fin = fecha + timedelta(minutes=duracion)
    body = {
        "timeMin": fecha.isoformat().replace('+00:00', 'Z'),
        "timeMax": fecha_fin.isoformat().replace('+00:00', 'Z'),
        "timeZone": "UTC",
        "items": [{"id": CALENDAR_ID}]
    }
    print("Google Calendar freeBusy request body:", body, flush=True)
    # Si no hay servicio o no hay CALENDAR_ID, asumimos disponible en modo offline
    if service is None or not CALENDAR_ID:
        return True
    try:
        resp = service.freebusy().query(body=body).execute()
        busy_times = resp.get("calendars", {}).get(CALENDAR_ID, {}).get("busy", [])
        return len(busy_times) == 0
    except Exception as e:
        print(f"❌ Error al verificar disponibilidad en Google Calendar: {e}", flush=True)
        print("Google Calendar freeBusy request body:", body, flush=True)
        # En caso de error remoto, no bloqueamos la agenda local
        return True

def insertar_en_google_calendar(fecha, descripcion, email):
    fecha = ensure_utc(fecha)
    evento = {
        "summary": descripcion,
        "description": f"Cita médica de: {email}",
        "start": {"dateTime": fecha.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": (fecha + timedelta(minutes=30)).isoformat(), "timeZone": "UTC"},
    }
    if service is None or not CALENDAR_ID:
        print("↩️ Google Calendar deshabilitado/offline: insert omitido", flush=True)
        return
    try:
        service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
        print("📅 Evento creado en Google Calendar", flush=True)
    except Exception as e:
        print("❌ Error al insertar en Google Calendar:", e, flush=True)

def eliminar_evento_google_calendar(fecha):
    fecha = ensure_utc(fecha)
    fecha_fin = fecha + timedelta(minutes=30)
    if service is None or not CALENDAR_ID:
        print("↩️ Google Calendar deshabilitado/offline: delete omitido", flush=True)
        return
    eventos = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=fecha.isoformat().replace('+00:00', 'Z'),
        timeMax=fecha_fin.isoformat().replace('+00:00', 'Z'),
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    for evento in eventos.get("items", []):
        service.events().delete(calendarId=CALENDAR_ID, eventId=evento["id"]).execute()
        print("🗑️ Evento eliminado del calendario", flush=True)

def editar_evento_google_calendar(fecha_original, nueva_fecha):
    fecha_original = ensure_utc(fecha_original)
    nueva_fecha = ensure_utc(nueva_fecha)
    fecha_fin = fecha_original + timedelta(minutes=30)
    if service is None or not CALENDAR_ID:
        print("↩️ Google Calendar deshabilitado/offline: update omitido", flush=True)
        return
    eventos = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=fecha_original.isoformat().replace('+00:00', 'Z'),
        timeMax=fecha_fin.isoformat().replace('+00:00', 'Z'),
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    for evento in eventos.get("items", []):
        evento["start"]["dateTime"] = nueva_fecha.isoformat().replace('+00:00', 'Z')
        evento["end"]["dateTime"] = (nueva_fecha + timedelta(minutes=30)).isoformat().replace('+00:00', 'Z')
        service.events().update(calendarId=CALENDAR_ID, eventId=evento["id"], body=evento).execute()
        print("🔄 Evento reprogramado en Google Calendar", flush=True)

def generar_disponibilidad(citas, dias=14):
    inicio = ahora_utc().replace(hour=8, minute=0, second=0, microsecond=0)
    disponibilidad = []
    duracion = timedelta(minutes=30)

    for d in range(dias):
        dia = inicio + timedelta(days=d)
        for i in range(20):  # De 8:00 a 18:00 (20 medias horas)
            slot = dia + i * duracion
            if slot.weekday() != 6 and esta_disponible(citas, slot) and disponibilidad_google_calendar(slot):
                disponibilidad.append(slot.isoformat())

    return disponibilidad

print(f"Using CALENDAR_ID: '{CALENDAR_ID}'", flush=True)