#!/usr/bin/env python3
"""Script de diagnóstico específico para APPOINTMENT CREATE.

Ejecuta un intento de creación de cita mostrando:
- Payload enviado
- Código HTTP
- Cuerpo bruto de respuesta

Usar para depurar errores 412 "cuerpo mal conformado" identificando qué campo sobra / falta.
"""
import asyncio
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from app.saludtools import SaludtoolsAPI

load_dotenv()

async def main():
    client = SaludtoolsAPI(environment="testing")
    ok = await client.authenticate()
    if not ok:
        print("No autenticado")
        return
    fecha = datetime.now() + timedelta(days=1)
    payload_base = {
        "startAppointment": fecha.strftime("%Y-%m-%d %H:%M"),
        "endAppointment": (fecha + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M"),
        "patientDocumentType": 1,
        "patientDocumentNumber": "90000001",  # Cambiar por uno existente si ya creado
        "doctorDocumentType": 1,
        "doctorDocumentNumber": "55223626",
        "modality": "CONVENTIONAL",
        "stateAppointment": "PENDING",
        "appointmentType": "CITADEPRUEBA",
        "clinic": int("47576"),
        "notificationState": "ATTEND",
    }
    import requests
    url = f"{client.base_url}/sync/event/v1/"
    event = {"eventType": "APPOINTMENT", "actionType": "CREATE", "body": payload_base}
    headers = client._get_headers()
    print("=== PAYLOAD ENVIADO ===")
    print(json.dumps(event, indent=2, ensure_ascii=False))
    try:
        r = requests.post(url, json=event, headers=headers)
        print("\n=== RESPUESTA ===")
        print("Status:", r.status_code)
        print(r.text)
    except Exception as e:
        print("Error request:", e)

if __name__ == "__main__":
    asyncio.run(main())
