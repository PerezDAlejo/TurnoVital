#!/usr/bin/env python
"""Crea (si no existe) un paciente en Saludtools y lo sincroniza en la BD local.
Uso:
  python crear_paciente_cli.py --doc 94000001 --tipo-doc 1 --nombre "Ana" --apellido "Prueba" \
      --telefono 573000000000 --email ana.prueba@example.com

Notas:
- Si el paciente ya existe remotamente, solo se consulta y se hace upsert local.
- Documento es la clave para idempotencia.
"""
import argparse, asyncio
from dotenv import load_dotenv
from app.saludtools import SaludtoolsAPI
from app import database

load_dotenv()

async def run(a):
    client = SaludtoolsAPI(environment="testing")
    ok = await client.authenticate()
    if not ok:
        print("No autenticado")
        return
    existente = await client.buscar_paciente(a.doc)
    if existente:
        print("Paciente ya existe remotamente:", existente)
        paciente = existente
    else:
        print("Creando paciente remoto...")
        created = await client.crear_paciente({
            'firstName': a.nombre,
            'lastName': a.apellido,
            'documentType': a.tipo_doc,
            'documentNumber': a.doc,
            'phone': a.telefono,
            'email': a.email
        })
        print("Respuesta creación:", created)
        paciente = await client.buscar_paciente(a.doc)
        print("Paciente consultado:", paciente)

    if paciente:
        # Upsert local
        try:
            nombres = paciente.get('firstName') or a.nombre
            apellidos = (paciente.get('firstLastName') or a.apellido) + (' ' + paciente.get('secondLastName') if paciente.get('secondLastName') else '')
            pid = database.upsert_paciente(
                documento=paciente['documentNumber'],
                nombres=nombres,
                apellidos=apellidos.strip(),
                telefono=paciente.get('phone'),
                email=paciente.get('email'),
                preferencia_contacto=None,
                tipo_paciente=None
            )
            print({"paciente_local_uuid": pid})
        except Exception as e:
            print("[WARN] Falló upsert local:", e)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--doc', required=True)
    ap.add_argument('--tipo-doc', type=int, default=1)
    ap.add_argument('--nombre', required=True)
    ap.add_argument('--apellido', required=True)
    ap.add_argument('--telefono', default='573000000000')
    ap.add_argument('--email', default='demo@example.com')
    args = ap.parse_args()
    asyncio.run(run(args))
