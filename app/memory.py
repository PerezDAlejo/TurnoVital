"""Memoria conversacional básica.
Persistencia mínima: guarda y recupera mensajes recientes.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import psycopg2

RETENCION_MINUTOS = 30
MAX_MENSAJES = 15

def _conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    return psycopg2.connect(url)

def iniciar_conversacion(paciente_id: Optional[str]) -> Optional[str]:
    conn = _conn()
    if not conn:
        return None
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
