"""Memoria conversacional básica.
Persistencia mínima: guarda y recupera mensajes recientes.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import psycopg2

RETENCION_MINUTOS = 30
MAX_MENSAJES = 15

# Campos seguidos para anti-loop (se guardan en columnas adicionales en conversaciones)
TRACKED_FIELDS = [
        'nombre', 'documento', 'fecha_deseada', 'franja', 'tipo_cita', 'descripcion',
        'telefono', 'email', 'preferencia_contacto', 'entidad', 'fecha_nacimiento'
]

# Umbrales por campo (si un mismo campo se solicita muchas veces sin avanzar)
CAMPO_MAX_REP = 3  # a la tercera se sugiere reformulación
# Umbral global de mensajes bot->usuario sin progreso efectivo
GLOBAL_MAX_STALL = 8

_ALTER_CHECK_DONE = False

def _ensure_columns(conn):
        """Asegura que existan columnas para tracking en 'conversaciones'.

        Evita una migración manual urgente; es idempotente en runtime.
        Columnas:
            campos_repetidos jsonb - contador por campo
            mensajes_sin_avance int - incrementa cuando el bot repregunta algo ya pedido
            ultimo_campo_pedido text - último campo solicitado explícitamente
            escalado_sugerido boolean - marca si ya se sugirió escalación para evitar spam
        """
        global _ALTER_CHECK_DONE
        if _ALTER_CHECK_DONE:
                return
        try:
                cur = conn.cursor()
                cur.execute("""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='conversaciones' AND column_name='campos_repetidos') THEN
                                ALTER TABLE conversaciones ADD COLUMN campos_repetidos jsonb DEFAULT '{}'::jsonb;
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='conversaciones' AND column_name='mensajes_sin_avance') THEN
                                ALTER TABLE conversaciones ADD COLUMN mensajes_sin_avance int DEFAULT 0;
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='conversaciones' AND column_name='ultimo_campo_pedido') THEN
                                ALTER TABLE conversaciones ADD COLUMN ultimo_campo_pedido text;
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='conversaciones' AND column_name='escalado_sugerido') THEN
                                ALTER TABLE conversaciones ADD COLUMN escalado_sugerido boolean DEFAULT false;
                            END IF;
                        END$$;
                """)
                conn.commit()
                cur.close()
                _ALTER_CHECK_DONE = True
        except Exception:
                # No bloquear si falla (por permisos por ejemplo)
                try:
                        cur.close()
                except Exception:
                        pass
                _ALTER_CHECK_DONE = True

def _conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    return psycopg2.connect(url)

def iniciar_conversacion(paciente_id: Optional[str]) -> Optional[str]:
    conn = _conn()
    if not conn:
        return None
    _ensure_columns(conn)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO conversaciones (paciente_id) VALUES (%s) RETURNING id
    """, (paciente_id,))
    cid = cur.fetchone()[0]
    conn.commit()
    cur.close(); conn.close()
    return cid

def obtener_conversacion_activa(paciente_id: Optional[str]) -> Optional[str]:
    conn = _conn()
    if not conn:
        return None
    _ensure_columns(conn)
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM conversaciones
        WHERE paciente_id IS NOT DISTINCT FROM %s
          AND estado = 'abierta'
          AND last_message_at > now() - interval '%s minutes'
        ORDER BY last_message_at DESC LIMIT 1
    """, (paciente_id, RETENCION_MINUTOS))
    row = cur.fetchone()
    cur.close(); conn.close()
    return row[0] if row else None

def guardar_mensaje(conversacion_id: str, rol: str, texto: str):
    conn = _conn()
    if not conn:
        return
    _ensure_columns(conn)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO mensajes_conversacion (conversacion_id, rol, texto)
        VALUES (%s, %s, %s)
    """, (conversacion_id, rol, texto))
    cur.execute("UPDATE conversaciones SET last_message_at = now() WHERE id = %s", (conversacion_id,))
    conn.commit(); cur.close(); conn.close()

def cargar_historial(conversacion_id: str) -> List[Dict]:
    conn = _conn()
    if not conn:
        return []
    cur = conn.cursor()
    cur.execute("""
        SELECT rol, texto, timestamp FROM mensajes_conversacion
        WHERE conversacion_id = %s
        ORDER BY timestamp DESC LIMIT %s
    """, (conversacion_id, MAX_MENSAJES))
    rows = cur.fetchall()
    cur.close(); conn.close()
    # Devolver en orden cronológico
    return [{"rol": r[0], "texto": r[1], "timestamp": r[2].isoformat()} for r in reversed(rows)]

def cerrar_conversacion(conversacion_id: str):
    conn = _conn();
    if not conn:
        return
    cur = conn.cursor()
    cur.execute("UPDATE conversaciones SET estado='cerrada' WHERE id = %s", (conversacion_id,))
    conn.commit(); cur.close(); conn.close()

# ===================== TRACKING REPETICION ===================== #

def incrementar_campo_repetido(conversacion_id: str, campo: str):
    if campo not in TRACKED_FIELDS:
        return
    conn = _conn();
    if not conn:
        return
    _ensure_columns(conn)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE conversaciones
        SET campos_repetidos = jsonb_set(
              COALESCE(campos_repetidos, '{}'::jsonb),
              ARRAY[%s],
              to_jsonb( ( (COALESCE( (campos_repetidos ->> %s)::int, 0) + 1) ) )
            ),
            ultimo_campo_pedido = %s,
            mensajes_sin_avance = mensajes_sin_avance + 1,
            last_message_at = now()
        WHERE id = %s
        RETURNING (campos_repetidos ->> %s)::int AS total
        """,
        (campo, campo, campo, conversacion_id, campo)
    )
    row = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    return (row[0] if row else None)

def marcar_avance(conversacion_id: str, campo: Optional[str] = None):
    """Resetea contador de mensajes_sin_avance y opcionalmente elimina contador de campo al recibir dato válido."""
    conn = _conn();
    if not conn:
        return
    _ensure_columns(conn)
    cur = conn.cursor()
    if campo and campo in TRACKED_FIELDS:
        # Set campo a 0 (o remover clave)
        cur.execute(
            """
            UPDATE conversaciones
            SET mensajes_sin_avance = 0,
                campos_repetidos = (campos_repetidos - %s),
                last_message_at = now()
            WHERE id = %s
            """,
            (campo, conversacion_id)
        )
    else:
        cur.execute(
            """
            UPDATE conversaciones
            SET mensajes_sin_avance = 0, last_message_at = now()
            WHERE id = %s
            """,
            (conversacion_id,)
        )
    conn.commit(); cur.close(); conn.close()

def obtener_estado_repeticion(conversacion_id: str) -> dict:
    conn = _conn();
    if not conn:
        return {}
    _ensure_columns(conn)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT campos_repetidos, mensajes_sin_avance, ultimo_campo_pedido, escalado_sugerido
        FROM conversaciones WHERE id = %s
        """,
        (conversacion_id,)
    )
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        return {}
    return {
        'campos_repetidos': row[0] or {},
        'mensajes_sin_avance': row[1] or 0,
        'ultimo_campo_pedido': row[2],
        'escalado_sugerido': bool(row[3]) if row[3] is not None else False,
        'umbral_campo': CAMPO_MAX_REP,
        'umbral_global': GLOBAL_MAX_STALL,
    }

def marcar_escalado_sugerido(conversacion_id: str):
    conn = _conn();
    if not conn:
        return
    _ensure_columns(conn)
    cur = conn.cursor()
    cur.execute("UPDATE conversaciones SET escalado_sugerido = true, last_message_at = now() WHERE id = %s", (conversacion_id,))
    conn.commit(); cur.close(); conn.close()

__all__ = [
    'iniciar_conversacion','obtener_conversacion_activa','guardar_mensaje','cargar_historial','cerrar_conversacion',
    'incrementar_campo_repetido','marcar_avance','obtener_estado_repeticion','marcar_escalado_sugerido',
    'TRACKED_FIELDS','CAMPO_MAX_REP','GLOBAL_MAX_STALL'
]
