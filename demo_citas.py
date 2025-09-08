#!/usr/bin/env python3
"""Script demo rápido: crea paciente (si no existe), crea cita, la edita y cancela.
Ejecutar: python demo_citas.py
"""
import asyncio, os
from datetime import datetime, timedelta
from dateutil import parser as dateparser
from dotenv import load_dotenv
from app.saludtools import SaludtoolsAPI
from app import database

load_dotenv()

DOC = os.getenv("DEMO_PACIENTE_DOC", "92000001")

def p(t):
    print(f"\n=== {t} ===")

async def main():
    client = SaludtoolsAPI(environment="testing")
    await client.authenticate()
    # Paciente (buscar remoto Saludtools y asegurar en BD local)
    paciente = await client.buscar_paciente(DOC)
    if not paciente:
        p("CREAR PACIENTE")
        paciente = await client.crear_paciente({
            'firstName':'Demo',
            'lastName':'Paciente Uno',
            'documentType':1,
            'documentNumber':DOC,
            'phone':'573000000000',
            'email':'demo@example.com'
        })
        print(paciente)
        paciente = await client.buscar_paciente(DOC)
    p("PACIENTE")
    print(paciente)
    # Upsert paciente en BD local
    paciente_id_local = None
    try:
        paciente_id_local = database.upsert_paciente(
            documento=paciente['documentNumber'],
            nombres=paciente.get('firstName','Demo'),
            apellidos=(paciente.get('firstLastName','Paciente') + ' ' + paciente.get('secondLastName','Uno')).strip(),
            telefono=paciente.get('phone'),
            email=paciente.get('email'),
            preferencia_contacto=None,
            tipo_paciente=None
        )
    except Exception as e:
        print(f"[WARN] No se pudo upsert paciente en BD local: {e}")
    # Crear cita
    fecha = datetime.now() + timedelta(days=1)
    # Usar los nombres de campos exactos que funcionaron en script diagnóstico
    cita_payload = {
        'patientDocumentType':1,
        'patientDocumentNumber':DOC,
        'doctorDocumentType':int(os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_TYPE','1')),
        'doctorDocumentNumber':os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER','11111'),
        'startAppointment':fecha.strftime('%Y-%m-%d %H:%M'),
        'endAppointment':(fecha+timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M'),
        'modality':'CONVENTIONAL',
        'stateAppointment':'PENDING',
        'appointmentType':'CITADEPRUEBA',
        'clinic':int(os.getenv('SALUDTOOLS_CLINIC_ID','8')),
        'notificationState':'ATTEND',
        'comment':'Demo script'
    }
    p("CREAR CITA")
    cita = await client.crear_cita_paciente(cita_payload)
    print(cita)
    cid = cita.get('id') if isinstance(cita, dict) else None
    cita_local_id = None
    if cid and paciente_id_local:
        try:
            # Parseo de fechas
            start_dt = dateparser.parse(cita['startAppointment'])
            end_dt = dateparser.parse(cita['endAppointment']) if cita.get('endAppointment') else start_dt + timedelta(minutes=30)
            cita_local_id = database.insertar_cita_enriquecida(
                paciente_id=paciente_id_local,
                especialista_id=cita_payload['doctorDocumentNumber'],
                tipo_cita=cita_payload['appointmentType'],
                start_at=start_dt,
                end_at=end_dt,
                duracion_min=int((end_dt - start_dt).total_seconds()/60),
                notas=cita_payload.get('comment',''),
                estado='scheduled'
            )
            try:
                database.set_saludtools_id(cita_local_id, cid)
            except Exception:
                pass
            database.registrar_historial_cita(cita_local_id, 'created', {'saludtools_id': cid, 'start': cita['startAppointment']})
            print({"cita_local_uuid": cita_local_id})
        except Exception as e:
            print(f"[WARN] No se pudo insertar cita en BD local: {e}")
    # Listar
    p("LISTAR CITAS")
    citas = await client.buscar_citas_paciente(DOC)
    print(f"Total: {len(citas)}")
    # Editar
    if cid:
        p("EDITAR CITA")
        nueva_fecha = fecha + timedelta(hours=2)
        edit = await client.editar_cita_paciente(cid, {
            'startAppointment':nueva_fecha.strftime('%Y-%m-%d %H:%M'),
            'endAppointment':(nueva_fecha+timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M'),
            'appointmentType':'CITADEPRUEBA',
            'doctorDocumentType':int(os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_TYPE','1')),
            'doctorDocumentNumber':os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER','11111'),
            'clinic':int(os.getenv('SALUDTOOLS_CLINIC_ID','8')),
            'patientDocumentType':1,
            'patientDocumentNumber':DOC,
            'comment':'Editada en demo'
        })
        print(edit)
        if cita_local_id:
            try:
                new_start = dateparser.parse(edit['startAppointment']) if isinstance(edit, dict) and edit.get('startAppointment') else nueva_fecha
                new_end = dateparser.parse(edit['endAppointment']) if isinstance(edit, dict) and edit.get('endAppointment') else (new_start + timedelta(minutes=30))
                database.actualizar_cita_enriquecida(cita_local_id, new_start, new_end, notas='Editada en demo (sync)')
                database.registrar_historial_cita(cita_local_id, 'updated', {'saludtools_id': cid, 'new_start': new_start.isoformat()})
            except Exception as e:
                print(f"[WARN] No se pudo actualizar cita local: {e}")
    # Cancelar
    if cid:
        p("CANCELAR CITA")
        cancel = await client.cancelar_cita_paciente(cid)
        print({'cancelled':cancel})
        if cita_local_id:
            try:
                database.marcar_cita_cancelada(cita_local_id, reason='demo flow')
                database.registrar_historial_cita(cita_local_id, 'cancelled', {'saludtools_id': cid})
            except Exception as e:
                print(f"[WARN] No se pudo marcar cita local cancelada: {e}")

    if paciente_id_local:
        p("CITAS EN BD LOCAL (citas_enriquecida)")
        try:
            citas_local = database.listar_citas_enriquecidas_por_paciente(paciente_id_local)
            for c in citas_local:
                print(c)
        except Exception as e:
            print(f"[WARN] No se pudieron listar citas locales: {e}")

if __name__ == '__main__':
    asyncio.run(main())
