"""Script de verificación integral del entorno.

Uso:
  python verify_environment.py            # Chequeo rápido
  python verify_environment.py --deep     # Incluye pruebas ligeras adicionales (evita en CI si no quieres llamadas externas costosas)

Salida: resumen de categorías (ENV VARS, DB, SALUDTOOLS, AI, TWILIO opcional, CALENDAR opcional)
Código de salida !=0 si hay fallos críticos (DB o Saludtools auth reales fallan).
"""
from __future__ import annotations
import os, sys, argparse
from datetime import datetime
from typing import List
from dotenv import load_dotenv

load_dotenv()

CRITICAL_MISSING: List[str] = []
WARNINGS: List[str] = []


def status_line(label: str, status: str, detail: str = ""):
    print(f"[{status:<7}] {label} {('- ' + detail) if detail else ''}")


def check_env():
    required_core = [
        'DATABASE_URL',
        'OPENAI_API_KEY',
        'SALUDTOOLS_API_KEY',
        'SALUDTOOLS_API_SECRET',
        'SALUDTOOLS_DOCTOR_DOCUMENT_TYPE',
        'SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER',
        'SALUDTOOLS_CLINIC_ID'
    ]
    optional = [
        'GEMINI_API_KEY', 'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_WHATSAPP_FROM',
        'CALENDAR_ID', 'GOOGLE_CREDENTIALS_PATH', 'SUPABASE_URL', 'SUPABASE_KEY'
    ]
    for var in required_core:
        if not os.getenv(var):
            CRITICAL_MISSING.append(var)
            status_line(var, 'FAIL', 'falta')
        else:
            status_line(var, 'OK', 'presente')
    for var in optional:
        if os.getenv(var):
            status_line(var, 'OK', 'opcional presente')
        else:
            status_line(var, 'WARN', 'opcional ausente')
            WARNINGS.append(f"Falta variable opcional {var}")


def check_db():
    import psycopg2
    url = os.getenv('DATABASE_URL')
    if not url:
        status_line('DB', 'FAIL', 'DATABASE_URL no definido')
        CRITICAL_MISSING.append('DATABASE_URL')
        return
    try:
        import time
        t0 = time.time()
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute('SELECT 1')
        cur.fetchone()
        cur.close(); conn.close()
        status_line('DB', 'OK', f'conexión exitosa ({(time.time()-t0)*1000:.1f} ms)')
    except Exception as e:
        status_line('DB', 'FAIL', f'error conexión: {e}')
        CRITICAL_MISSING.append('DB_CONNECTION')


async def check_saludtools(deep: bool):
    from app.saludtools import SaludtoolsAPI
    client = SaludtoolsAPI(environment=os.getenv('SALUDTOOLS_ENVIRONMENT') or os.getenv('ENVIRONMENT') or 'testing')
    ok = await client.authenticate()
    if not ok:
        status_line('Saludtools Auth', 'FAIL', 'no se autenticó (modo mock si faltan credenciales)')
        CRITICAL_MISSING.append('SALUDTOOLS_AUTH')
        return
    if client.mock_mode:
        status_line('Saludtools Auth', 'OK', 'mock_mode (sin credenciales reales)')
    else:
        status_line('Saludtools Auth', 'OK', 'token obtenido')
    if deep and not client.mock_mode:
        docs = await client.obtener_tipos_documento()
        status_line('Saludtools Param docs', 'OK' if docs else 'WARN', f'{len(docs) if docs else 0} tipos documento')


def check_ai(deep: bool):
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        status_line('OpenAI', 'FAIL', 'OPENAI_API_KEY falta')
        CRITICAL_MISSING.append('OPENAI_API_KEY')
        return
    if not key.startswith('sk-') and 'proj' not in key:
        status_line('OpenAI', 'WARN', 'formato de key inusual')
    else:
        status_line('OpenAI', 'OK', 'key formato válido')
    if deep:
        try:
            import openai
            openai.api_key = key
            _ = openai.models.list()
            status_line('OpenAI List', 'OK', 'acceso API')
        except Exception as e:
            status_line('OpenAI List', 'WARN', f'no se validó vía API: {e}')


def check_twilio():
    sid = os.getenv('TWILIO_ACCOUNT_SID')
    token = os.getenv('TWILIO_AUTH_TOKEN')
    from_ = os.getenv('TWILIO_WHATSAPP_FROM')
    if sid and token and from_:
        status_line('Twilio', 'OK', 'vars presentes (no se llama API)')
    else:
        status_line('Twilio', 'WARN', 'faltan variables para envío saliente (solo recibir webhook local)')


def check_calendar():
    if os.getenv('CALENDAR_ID') and os.getenv('GOOGLE_CREDENTIALS_PATH'):
        status_line('Calendar', 'OK', 'vars presentes (no se valida credencial)')
    else:
        status_line('Calendar', 'WARN', 'calendar no configurado (solo se omiten funciones)')


def summary():
    print('\n===== RESUMEN =====')
    if CRITICAL_MISSING:
        print('FALLOS CRÍTICOS:')
        for c in CRITICAL_MISSING:
            print(' -', c)
    else:
        print('Sin fallos críticos.')
    if WARNINGS:
        print('\nAdvertencias:')
        for w in WARNINGS:
            print(' -', w)
    print('\nTimestamp:', datetime.utcnow().isoformat())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--deep', action='store_true', help='Ejecuta verificaciones adicionales (API externas)')
    args = parser.parse_args()
    check_env()
    check_db()
    check_ai(args.deep)
    check_twilio()
    check_calendar()
    import asyncio
    asyncio.run(check_saludtools(args.deep))
    summary()
    if CRITICAL_MISSING:
        sys.exit(1)


if __name__ == '__main__':
    main()
