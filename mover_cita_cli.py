#!/usr/bin/env python
"""Reprograma una cita existente en Saludtools y la sincroniza con la BD.
Uso:
  python mover_cita_cli.py --remote-id 4685000 --nueva-fecha 2025-08-15 --nueva-hora 16:00
  (Opcional) si no se conoce remote-id: --doc 92000001 --buscar-hora 10:30 --buscar-fecha 2025-08-15

Argumentos clave:
  --remote-id ID numérico de cita Saludtools (preferido)
  --doc documento paciente (para búsqueda alternativa)
  --buscar-fecha / --buscar-hora: fecha y hora aproximada original (HH:MM)
  --nueva-fecha / --nueva-hora: destino obligado
"""
import argparse, os, asyncio, sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from dateutil import parser as dateparser
from app.saludtools import SaludtoolsAPI
from app import database

load_dotenv()

async def localizar_cita_por_busqueda(client: SaludtoolsAPI, doc: str, fecha: str, hora: str):
    citas = await client.buscar_citas_paciente(doc)
    target_dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    # citas tienen startAppointment o startDate
    for c in citas:
        start_raw = c.get('startAppointment') or c.get('startDate')
        if not start_raw:
            continue
        try:
            sdt = dateparser.parse(start_raw)
        except:
            continue
        if sdt.strftime('%Y-%m-%d %H:%M') == target_dt.strftime('%Y-%m-%d %H:%M'):
            return c
    return None

async def run(args):
    client = SaludtoolsAPI(environment="testing")
    await client.authenticate()

    cita_remota = None
    remote_id = None

    if args.remote_id:
        remote_id = int(args.remote_id)
    else:
        if not (args.doc and args.buscar_fecha and args.buscar_hora):
            print("Debe especificar --remote-id o ( --doc + --buscar-fecha + --buscar-hora ).")
            return
        cita_remota = await localizar_cita_por_busqueda(client, args.doc, args.buscar_fecha, args.buscar_hora)
        if not cita_remota:
            print("No se encontró cita a reprogramar.")
            return
        remote_id = cita_remota.get('id')
        if not remote_id:
            print("Cita encontrada sin id, no se puede continuar.")
            return

    nueva_start = datetime.strptime(f"{args.nueva_fecha} {args.nueva_hora}", "%Y-%m-%d %H:%M")
    nueva_end = nueva_start + timedelta(minutes=args.duracion)

    payload_update = {
        'startAppointment': nueva_start.strftime('%Y-%m-%d %H:%M'),
        'endAppointment': nueva_end.strftime('%Y-%m-%d %H:%M'),
        'appointmentType': args.tipo,
        'doctorDocumentType': int(os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_TYPE','1')),
        'doctorDocumentNumber': os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER','11111'),
        'clinic': int(os.getenv('SALUDTOOLS_CLINIC_ID','8')),
    }
    # Necesitamos el documento paciente si no lo conocemos
    if not cita_remota and args.doc:
        # Buscar cualquiera para extraer patient doc; create requiere patientDocumentType/Number pero update también pide algunos
        payload_update['patientDocumentType'] = 1
        payload_update['patientDocumentNumber'] = args.doc
    elif cita_remota:
        payload_update['patientDocumentType'] = cita_remota.get('patientDocumentType',1)
        payload_update['patientDocumentNumber'] = cita_remota.get('patientDocumentNumber', args.doc)

    print("Reprogramando cita remota id=", remote_id, "payload=", payload_update)
    updated = await client.editar_cita_paciente(remote_id, payload_update)
    print("Respuesta update:", updated)

    # Sincronizar BD local
    if updated and isinstance(updated, dict):
        local = database.buscar_cita_por_saludtools_id(remote_id)
        if local:
            database.actualizar_cita_enriquecida(local['id'], nueva_start, nueva_end, notas=(local['notas'] or '') + ' | reprogramada')
            try:
                database.set_saludtools_id(local['id'], remote_id)
            except Exception:
                pass
            database.registrar_historial_cita(local['id'], 'updated', {'saludtools_id': remote_id, 'new_start': nueva_start.isoformat()})
            print({'cita_local_uuid': local['id'], 'saludtools_id': remote_id, 'sync': 'updated'})
        else:
            print('[WARN] No se encontró cita local para actualizar (quizá no fue creada con script crear).')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--remote-id')
    ap.add_argument('--doc')
    ap.add_argument('--buscar-fecha')
    ap.add_argument('--buscar-hora')
    ap.add_argument('--nueva-fecha', required=True)
    ap.add_argument('--nueva-hora', required=True)
    ap.add_argument('--duracion', type=int, default=30)
    ap.add_argument('--tipo', default='CITADEPRUEBA')
    args = ap.parse_args()
    asyncio.run(run(args))
