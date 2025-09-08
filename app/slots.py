"""Generación básica de slots disponibles (sin consulta directa a Saludtools todavía)."""
from datetime import datetime, timedelta, time
from typing import List, Dict
from app.config import IPS_CONFIG, es_horario_valido

INTERVALO_MIN = 30

# Mapas de preferencia a rangos
PREFERENCIAS = {
    "am": (time(5,0), time(11,59)),
    "medio_dia": (time(12,0), time(13,59)),
    "pm": (time(14,0), time(19,0)),
}

def generar_slots(dia: datetime, duracion_min: int, preferencia: str, max_opciones: int = 3) -> List[Dict]:
    dia_nombre = dia.strftime('%A').lower()
    if preferencia not in PREFERENCIAS:
        # fallback amplio
        rangos = [(time(5,0), time(19,0))]
    else:
        rangos = [PREFERENCIAS[preferencia]]
    slots = []
    for rango in rangos:
        inicio, fin = rango
        actual = datetime.combine(dia.date(), inicio)
        limite = datetime.combine(dia.date(), fin)
        while actual + timedelta(minutes=duracion_min) <= limite:
            h_fmt = actual.strftime('%H:%M')
            if es_horario_valido(dia_nombre, h_fmt):
                slots.append({
                    "start": actual,
                    "end": actual + timedelta(minutes=duracion_min)
                })
            actual += timedelta(minutes=INTERVALO_MIN)
            if len(slots) >= max_opciones:
                return slots
    return slots
