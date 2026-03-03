"""
MANAGER DE GOOGLE CALENDAR (MVP TURNOVITAL)
===========================================
Maneja la autenticación y creación de eventos en Google Calendar.
"""

import os
import logging
from datetime import datetime, timedelta
import pytz

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    GOOGLE_LIBS_INSTALLED = True
except ImportError:
    GOOGLE_LIBS_INSTALLED = False

logger = logging.getLogger(__name__)

# Scopes para Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarManager:
    """Gestiona integración con Google Calendar."""
    
    def __init__(self):
        self.creds = None
        self.service = None
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary") # primary usa el de la cuenta de servicio por defecto o el id que se pase
        self.tz = pytz.timezone('America/Bogota')
        self._inicializar()
        
    def _inicializar(self):
        if not GOOGLE_LIBS_INSTALLED:
            logger.warning("Faltan librerías de Google Cloud. Instalar con: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
            return
            
        creds_path = os.path.join(os.getcwd(), 'credentials.json')
        if os.path.exists(creds_path):
            try:
                self.creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
                self.service = build('calendar', 'v3', credentials=self.creds)
                logger.info("✅ Conexión con Google Calendar establecida exitosamente.")
            except Exception as e:
                logger.error(f"❌ Error al cargar credentials.json: {str(e)}")
        else:
            logger.warning("⚠️ No se encontró credentials.json en la raíz del proyecto. El agendamiento en Calendar está simulado.")

    async def crear_evento(self, nombre: str, servicio: str, fecha: str, hora: str, telefono: str = "") -> dict:
        """
        Crea un evento en el calendario.
        fecha: YYYY-MM-DD
        hora: HH:MM
        """
        if not self.service:
            # Modo Simulación / Fallback si no hay credenciales
            logger.info(f"SIMULACIÓN: Creando evento en calendar para {nombre} - {servicio} el {fecha} {hora}")
            return {"success": True, "event_id": "simulated_id", "simulated": True}
            
        try:
            # Parsear fecha y hora
            fecha_hora_str = f"{fecha} {hora}"
            inicio_dt = datetime.strptime(fecha_hora_str, "%Y-%m-%d %H:%M")
            inicio_dt = self.tz.localize(inicio_dt)
            # Asumimos cita de 1 hora
            fin_dt = inicio_dt + timedelta(hours=1)
            
            event = {
                'summary': f"{servicio} - {nombre}",
                'location': 'TurnoVital Clinic',
                'description': f"Cita agendada vía WhatsApp TurnoVital.\nTeléfono: {telefono}",
                'start': {
                    'dateTime': inicio_dt.isoformat(),
                    'timeZone': 'America/Bogota',
                },
                'end': {
                    'dateTime': fin_dt.isoformat(),
                    'timeZone': 'America/Bogota',
                },
            }
            
            event_result = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
            logger.info(f"✅ Evento creado en Google Calendar: {event_result.get('htmlLink')}")
            
            return {
                "success": True,
                "event_id": event_result.get('id'),
                "link": event_result.get('htmlLink'),
                "simulated": False
            }
            
        except Exception as e:
            logger.error(f"❌ Error al crear evento en Google Calendar: {str(e)}")
            return {"success": False, "error": str(e)}

    async def consultar_disponibilidad(self, fecha: str) -> list:
        """
        Consultaría los bloques libres del día (MVP avanzado).
        Por ahora, el bot confía en la elección del usuario o pregunta directamente.
        """
        pass
