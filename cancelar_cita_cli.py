#!/usr/bin/env python
"""Cancela una cita en Saludtools y sincroniza la BD local.
Uso:
  python cancelar_cita_cli.py --remote-id 4685043
  o
  python cancelar_cita_cli.py --doc 92000001 --fecha 2025-08-15 --hora 14:30
"""
import argparse, os, asyncio
from datetime import datetime
from dotenv import load_dotenv
from dateutil import parser as dateparser
from app.saludtools import SaludtoolsAPI
from app import database

load_dotenv()

async def localizar_cita(client: SaludtoolsAPI, doc: str, fecha: str, hora: str):
    citas = await client.buscar_citas_paciente(doc)
    target = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    for c in citas:
        sr = c.get('startAppointment') or c.get('startDate')
        if not sr:
            continue
        try:
            sdt = dateparser.parse(sr)
        except:
            continue
        if sdt.strftime('%Y-%m-%d %H:%M') == target.strftime('%Y-%m-%d %H:%M'):
            return c
    return None

async def run(args):
    client = SaludtoolsAPI(environment="testing")
    await client.authenticate()

    remote_id = args.remote_id
    if not remote_id:
        if not (args.doc and args.fecha and args.hora):
            print("Debe proporcionar --remote-id o ( --doc + --fecha + --hora ).")
            return
        cita = await localizar_cita(client, args.doc, args.fecha, args.hora)
        if not cita:
            print("No se encontró cita a cancelar.")
            return
        remote_id = cita.get('id')
        if not remote_id:
            print("Cita encontrada sin id.")
            return

    remote_id = int(remote_id)
    print("Cancelando cita remota id=", remote_id)
    ok = await client.cancelar_cita_paciente(remote_id)
    print({'cancelled': ok})

    if ok:
        local = database.buscar_cita_por_saludtools_id(remote_id)
        if local:
            try:
                database.set_saludtools_id(local['id'], remote_id)
            except Exception:
                pass
            database.marcar_cita_cancelada(local['id'], reason='cli cancel')
            database.registrar_historial_cita(local['id'], 'cancelled', {'saludtools_id': remote_id})
            print({'cita_local_uuid': local['id'], 'saludtools_id': remote_id, 'sync': 'cancelled'})
        else:
            print('[WARN] No se encontró cita local para marcar cancelada.')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--remote-id')
    ap.add_argument('--doc')
    ap.add_argument('--fecha')
    ap.add_argument('--hora')
    args = ap.parse_args()
    asyncio.run(run(args))
