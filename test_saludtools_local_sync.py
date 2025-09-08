"""Test de sincronización local con columna saludtools_id.

Requisitos:
- DB accesible vía DATABASE_URL
- Credenciales Saludtools opcionales (si faltan entra en mock_mode y el test se ajusta)
"""
import os
import asyncio
from datetime import datetime, timedelta
from app.saludtools import SaludtoolsAPI
from app import database
from fastapi.testclient import TestClient
from app.main import app


async def _crear_cita_real_o_mock(doc: str):
    client = SaludtoolsAPI(environment="testing")
    await client.authenticate()
    paciente = await client.buscar_paciente(doc)
    if not paciente:
        paciente = await client.crear_paciente({
            'firstName':'Test','lastName':'Local Sync','documentType':1,'documentNumber':doc
        })
        paciente = await client.buscar_paciente(doc)
    paciente_id_local = database.upsert_paciente(
        documento=paciente['documentNumber'],
        nombres=paciente.get('firstName','Test'),
        apellidos=paciente.get('firstLastName','Paciente'),
        telefono=paciente.get('phone'),
        email=paciente.get('email'),
        preferencia_contacto=None,
        tipo_paciente=None
    )
    start = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
    end = start + timedelta(minutes=30)
    payload = {
        'patientDocumentType':1,
        'patientDocumentNumber':doc,
        'doctorDocumentType':int(os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_TYPE','1')),
        'doctorDocumentNumber':os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER','11111'),
        'startAppointment':start.strftime('%Y-%m-%d %H:%M'),
        'endAppointment':end.strftime('%Y-%m-%d %H:%M'),
        'modality':'CONVENTIONAL',
        'stateAppointment':'PENDING',
        'appointmentType':'TESTSYNC',
        'clinic':int(os.getenv('SALUDTOOLS_CLINIC_ID','8')),
        'notificationState':'ATTEND',
        'comment':'test local sync'
    }
    cita = await client.crear_cita_paciente(payload)
    assert cita, "La creación remota/Mock devolvió None"
    cid = cita.get('id')
    assert cid, f"Respuesta cita sin id: {cita}"
    local_uuid = database.insertar_cita_enriquecida(
        paciente_id=paciente_id_local,
        especialista_id=payload['doctorDocumentNumber'],
        tipo_cita=payload['appointmentType'],
        start_at=start,
        end_at=end,
        duracion_min=30,
        notas=payload['comment'],
        estado='scheduled'
    )
    database.set_saludtools_id(local_uuid, cid)
    return cid, local_uuid


def test_sync_lookup():
    doc = os.getenv('TEST_DOC_SYNC', '99000001')
    cid, local_uuid = asyncio.run(_crear_cita_real_o_mock(doc))
    # Lookup directa DB helper
    found = database.buscar_cita_por_saludtools_id(cid)
    assert found, 'No se encontró cita por saludtools_id en DB'
    # Endpoint API
    client_http = TestClient(app)
    resp = client_http.get(f"/citas/by-remote/{cid}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get('success') is True
    assert data['cita']['id'], 'Cita sin id local en respuesta'
    # Sanity: notas no deben contener el patrón legacy
    assert not (data['cita'].get('notas') or '').startswith('saludtools_id='), 'Notas aún contienen patrón legacy'
