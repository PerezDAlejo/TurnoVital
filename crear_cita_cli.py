#!/usr/bin/env python
"""Crea una cita en Saludtools y la persiste en la BD local.
Uso:
  python crear_cita_cli.py --doc 92000001 --fecha 2025-08-15 --hora 14:30 --duracion 30 --tipo CITADEPRUEBA

Argumentos:
  --doc DOCUMENTO paciente (int/string)
  --fecha YYYY-MM-DD (fecha de inicio)
  --hora HH:MM (24h)
  --duracion minutos (default 30)
  --tipo tipo de cita (default CITADEPRUEBA)
  --comentario texto opcional
"""
import argparse, os, asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from dateutil import parser as dateparser
from app.saludtools import SaludtoolsAPI
from app import database

load_dotenv()

async def run(args):
    client = SaludtoolsAPI(environment="testing")
    await client.authenticate()
    paciente = await client.buscar_paciente(args.doc)
    if not paciente:
        print("Paciente no existe remotamente. Creándolo...")
        paciente = await client.crear_paciente({
            'firstName':'Demo','lastName':'Paciente CLI','documentType':1,'documentNumber':args.doc,
            'phone':'573000000000','email':'demo@example.com'
        })
        paciente = await client.buscar_paciente(args.doc)
    print("Paciente:", paciente)

    # Upsert local
    paciente_id_local = database.upsert_paciente(
        documento=paciente['documentNumber'],
        nombres=paciente.get('firstName','Demo'),
        apellidos=(paciente.get('firstLastName','Paciente') + ' ' + paciente.get('secondLastName','CLI')).strip(),
        telefono=paciente.get('phone'),
        email=paciente.get('email'),
        preferencia_contacto=None,
        tipo_paciente=None
    )

    start_dt = datetime.strptime(f"{args.fecha} {args.hora}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(minutes=args.duracion)

    payload = {
        'patientDocumentType':1,
        'patientDocumentNumber':args.doc,
        'doctorDocumentType':int(os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_TYPE','1')),
        'doctorDocumentNumber':os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER','11111'),
        'startAppointment':start_dt.strftime('%Y-%m-%d %H:%M'),
        'endAppointment':end_dt.strftime('%Y-%m-%d %H:%M'),
        'modality':'CONVENTIONAL',
        'stateAppointment':'PENDING',
        'appointmentType':args.tipo,
        'clinic':int(os.getenv('SALUDTOOLS_CLINIC_ID','8')),
        'notificationState':'ATTEND',
        'comment':args.comentario or 'CLI create'
    }
    print("Creando cita con payload:", payload)
    cita = await client.crear_cita_paciente(payload)
    print("Respuesta creación:", cita)
    if isinstance(cita, dict) and cita.get('id'):
        remote_id = cita['id']
        local_id = database.insertar_cita_enriquecida(
            paciente_id=paciente_id_local,
            especialista_id=payload['doctorDocumentNumber'],
            tipo_cita=payload['appointmentType'],
            start_at=start_dt,
            end_at=end_dt,
            duracion_min=args.duracion,
            notas=payload['comment'],  # dejamos de almacenar el patrón legacy saludtools_id=..
            estado='scheduled'
        )
        # Persistir id remoto en columna dedicada
        try:
            database.set_saludtools_id(local_id, remote_id)
        except Exception as e:
            print(f"[WARN] No se pudo setear saludtools_id en columna dedicada: {e}")
        database.registrar_historial_cita(local_id, 'created', {'saludtools_id': remote_id})
        print({'cita_local_uuid': local_id, 'saludtools_id': remote_id})
    else:
        print("No se pudo persistir localmente (respuesta sin id).")

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--doc', required=True)
    ap.add_argument('--fecha', required=True)
    ap.add_argument('--hora', required=True, help='HH:MM formato 24h')
    ap.add_argument('--duracion', type=int, default=30)
    ap.add_argument('--tipo', default='CITADEPRUEBA')
    ap.add_argument('--comentario')
    args = ap.parse_args()
    asyncio.run(run(args))
