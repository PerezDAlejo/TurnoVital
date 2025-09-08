"""Script de demostración rápida de la base de datos.

Acciones:
1. Conectar usando DATABASE_URL
2. Asegurar paciente (upsert por documento)
3. Crear conversación si no existe una activa reciente
4. Insertar mensajes (usuario / bot)
5. Crear cita de ejemplo (citas_enriquecida)
6. Registrar historial de la cita (citas_historial)
7. Registrar log de acción (logs_acciones)
8. Mostrar un resumen (counts y últimas filas clave)

Uso:
  python quick_test_db.py

Requisitos:
  - Variable de entorno DATABASE_URL apuntando al Transaction Pooler (o direct) con extensión pgcrypto activa.
  - Ejecutado previamente migrations/01_schema.sql

Notas:
  - No modifica tablas legacy ("citas"). Usa el nuevo esquema.
  - Idempotente: si ya existe el paciente por documento, reutiliza.
"""
from __future__ import annotations
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, timezone
import json
import uuid
from dotenv import load_dotenv

# Cargar variables desde .env (si existe)
load_dotenv()

DOCUMENTO_DEMO = "DOC-DEMO-001"
ESPECIALISTA_DEMO = "fisioterapia"
TIPO_CITA_DEMO = "evaluacion"
DURACION_MIN = 30


def utc_now():
    return datetime.now(timezone.utc)


def get_conn():
    """Obtiene conexión intentando primero DATABASE_URL luego fallback a DATABASE_URL_DIRECT.

    Lanza error con mensaje guiado si no encuentra ninguna.
    """
    url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_DIRECT")
    if not url:
        raise RuntimeError(
            "DATABASE_URL no definido. Asegúrate de: 1) Tener .env con DATABASE_URL=... 2) Haber recargado el entorno."
        )
    try:
        return psycopg2.connect(url)
    except Exception as e:
        raise RuntimeError(f"Error conectando a la base de datos: {e}\nURL usada (ocultando credenciales): {url.split('@')[-1]}")


def ensure_extension(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    conn.commit()


def get_or_create_paciente(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM pacientes WHERE documento=%s", (DOCUMENTO_DEMO,))
        row = cur.fetchone()
        if row:
            return row["id"], False
        cur.execute(
            """INSERT INTO pacientes (id, nombres, apellidos, documento, telefono, email, preferencia_contacto, tipo_paciente)
                 VALUES (gen_random_uuid(), %s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (
                "Paciente Demo",
                "Ejemplo",
                DOCUMENTO_DEMO,
                "3000000000",
                "demo@example.com",
                "whatsapp",
                "primera_vez",
            ),
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id, True


def create_or_get_conversacion(conn, paciente_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Conversación en las últimas 2 horas abierta
        cur.execute(
            """SELECT id FROM conversaciones 
                   WHERE paciente_id=%s AND estado='abierta' 
                   AND started_at > now() - interval '2 hours' 
                   ORDER BY started_at DESC LIMIT 1""",
            (paciente_id,),
        )
        row = cur.fetchone()
        if row:
            return row["id"], False
        cur.execute(
            "INSERT INTO conversaciones (id, paciente_id, canal, estado) VALUES (gen_random_uuid(), %s,'whatsapp','abierta') RETURNING id",
            (paciente_id,),
        )
        conv_id = cur.fetchone()["id"]
        conn.commit()
        return conv_id, True


def insert_mensajes(conn, conversacion_id):
    mensajes = [
        ("usuario", "Hola, quisiera agendar una cita de fisioterapia"),
        ("bot", "Claro, ¿qué día te queda mejor dentro de esta semana?"),
    ]
    with conn.cursor() as cur:
        for rol, texto in mensajes:
            cur.execute(
                "INSERT INTO mensajes_conversacion (id, conversacion_id, rol, texto) VALUES (gen_random_uuid(), %s, %s, %s)",
                (conversacion_id, rol, texto),
            )
        # Actualiza last_message_at
        cur.execute(
            "UPDATE conversaciones SET last_message_at=now() WHERE id=%s",
            (conversacion_id,),
        )
    conn.commit()


def create_cita(conn, paciente_id):
    start_at = utc_now() + timedelta(days=1)
    end_at = start_at + timedelta(minutes=DURACION_MIN)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO citas_enriquecida (id, paciente_id, especialista_id, tipo_cita, start_at, end_at, duracion_min, estado, fuente)
                 VALUES (gen_random_uuid(), %s,%s,%s,%s,%s,%s,'scheduled','whatsapp') RETURNING id""",
            (
                paciente_id,
                ESPECIALISTA_DEMO,
                TIPO_CITA_DEMO,
                start_at,
                end_at,
                DURACION_MIN,
            ),
        )
        cita_id = cur.fetchone()["id"]
        # Historial
        cur.execute(
            "INSERT INTO citas_historial (cita_id, evento, snapshot) VALUES (%s,%s,%s)",
            (
                cita_id,
                "created",
                json.dumps({
                    "estado": "scheduled",
                    "especialista": ESPECIALISTA_DEMO,
                    "tipo_cita": TIPO_CITA_DEMO,
                    "start_at": start_at.isoformat(),
                }),
            ),
        )
    conn.commit()
    return cita_id


def log_accion(conn, accion, metadata):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO logs_acciones (accion, metadata) VALUES (%s,%s)",
            (accion, json.dumps(metadata)),
        )
    conn.commit()


def resumen(conn, paciente_id, conversacion_id, cita_id):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) AS pacientes FROM pacientes")
        pacientes_count = cur.fetchone()["pacientes"]
        cur.execute("SELECT count(*) AS conversaciones FROM conversaciones")
        conv_count = cur.fetchone()["conversaciones"]
        cur.execute(
            "SELECT rol, texto, timestamp FROM mensajes_conversacion WHERE conversacion_id=%s ORDER BY timestamp",
            (conversacion_id,),
        )
        mensajes = cur.fetchall()
        cur.execute(
            "SELECT evento, timestamp FROM citas_historial WHERE cita_id=%s ORDER BY timestamp",
            (cita_id,),
        )
        hist = cur.fetchall()
        cur.execute(
            "SELECT accion, timestamp FROM logs_acciones ORDER BY timestamp DESC LIMIT 5"
        )
        logs = cur.fetchall()
    print("\n=== RESUMEN DEMO ===")
    print(f"Pacientes totales: {pacientes_count}")
    print(f"Conversaciones totales: {conv_count}")
    print(f"Paciente demo id: {paciente_id}")
    print(f"Conversacion id: {conversacion_id}")
    print(f"Cita id: {cita_id}")
    print("\nMensajes:")
    for m in mensajes:
        print(f"  [{m['rol']}] {m['texto']} ({m['timestamp']})")
    print("\nHistorial cita:")
    for h in hist:
        print(f"  Evento: {h['evento']} @ {h['timestamp']}")
    print("\nÚltimos logs:")
    for l in logs:
        print(f"  {l['timestamp']} - {l['accion']}")
    print("====================\n")


def main():
    print("Iniciando demo DB...")
    # Mostrar variables clave para depuración (sin exponer password)
    dbg = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_DIRECT")
    if not dbg:
        print("[DEBUG] No se encontró DATABASE_URL ni DATABASE_URL_DIRECT en variables de entorno.")
    else:
        print("[DEBUG] Usando host de conexión:", dbg.split('@')[-1].split('?')[0])
    conn = get_conn()
    try:
        ensure_extension(conn)
        paciente_id, nuevo_pac = get_or_create_paciente(conn)
        if nuevo_pac:
            print("Paciente demo creado.")
        else:
            print("Paciente demo reutilizado.")
        conversacion_id, nueva_conv = create_or_get_conversacion(conn, paciente_id)
        if nueva_conv:
            print("Conversación creada.")
        else:
            print("Conversación reutilizada.")
        insert_mensajes(conn, conversacion_id)
        cita_id = create_cita(conn, paciente_id)
        print("Cita creada.")
        log_accion(
            conn,
            "DEMO_CITA_CREADA",
            {"cita_id": str(cita_id), "paciente_id": str(paciente_id), "duracion": DURACION_MIN},
        )
        resumen(conn, paciente_id, conversacion_id, cita_id)
    finally:
        conn.close()
    print("Demo finalizada correctamente.")


if __name__ == "__main__":
    main()
