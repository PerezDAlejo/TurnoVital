# app/database.py
import psycopg2
import psycopg2.pool
from datetime import datetime, timezone
from app.calendar_ips import ensure_utc
from dotenv import load_dotenv
import os
import json
import logging
from contextlib import contextmanager
from typing import Optional

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_DIRECT")
TENANT_KEY = os.getenv("TENANT_KEY", "react")  # Default optimizado para IPS React

logger = logging.getLogger(__name__)

# Connection Pool para mejor performance
_connection_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

def init_connection_pool(minconn=2, maxconn=10):
    """Inicializa el pool de conexiones"""
    global _connection_pool
    if _connection_pool is None:
        try:
            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn, maxconn, DATABASE_URL
            )
            logger.info(f"Pool de conexiones inicializado: {minconn}-{maxconn}")
        except Exception as e:
            logger.error(f"Error inicializando pool: {e}")
            raise

def get_connection():
    """Obtiene conexión del pool o crea una nueva"""
    if _connection_pool:
        try:
            return _connection_pool.getconn()
        except Exception as e:
            logger.warning(f"Pool agotado, creando conexión directa: {e}")
    return psycopg2.connect(DATABASE_URL)

def return_connection(conn):
    """Devuelve conexión al pool"""
    if _connection_pool:
        _connection_pool.putconn(conn)
    else:
        conn.close()

@contextmanager
def get_db_connection():
    """Context manager para conexiones con tenant context automático"""
    conn = None
    try:
        conn = get_connection()
        # Establecer tenant context automáticamente
        with conn.cursor() as cursor:
            cursor.execute("SELECT set_config('app.tenant_key', %s, false)", (TENANT_KEY,))
        conn.commit()
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error en conexión DB: {e}")
        raise
    finally:
        if conn:
            return_connection(conn)

def obtener_citas_paciente(paciente_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT fecha, descripcion FROM citas WHERE paciente_id = %s", (paciente_id,))
    citas = [{"fecha": ensure_utc(r[0]), "descripcion": r[1]} for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return citas

def insertar_paciente(nombre, documento, telefono, email, preferencia_contacto, plan_salud=None, tiene_orden_medica=None):
    conn = get_connection()
    cursor = conn.cursor()
    # Divide nombre en nombres / apellidos si es posible
    partes = (nombre or "").strip().split()
    nombres = partes[0] if partes else ""
    apellidos = " ".join(partes[1:]) if len(partes) > 1 else ""
    cursor.execute(
        """
        INSERT INTO pacientes (id, nombres, apellidos, documento, telefono, email, preferencia_contacto, plan_salud, tiene_orden_medica)
        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (nombres, apellidos, documento, telefono, email, preferencia_contacto, plan_salud, tiene_orden_medica)
    )
    paciente_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return paciente_id

def obtener_paciente_por_documento(documento):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM pacientes WHERE documento = %s", (documento,))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    return resultado[0] if resultado else None

def insertar_cita(paciente_id, fecha, descripcion):
    fecha = ensure_utc(fecha)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO citas (id, paciente_id, fecha, descripcion)
        VALUES (gen_random_uuid(), %s, %s, %s)
    """, (paciente_id, fecha, descripcion))
    conn.commit()
    cursor.close()
    conn.close()

def editar_cita(paciente_id, fecha_original, nueva_fecha):
    fecha_original = ensure_utc(fecha_original)
    nueva_fecha = ensure_utc(nueva_fecha)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE citas
        SET fecha = %s
        WHERE paciente_id = %s AND fecha = %s
    """, (nueva_fecha, paciente_id, fecha_original))
    conn.commit()
    cursor.close()
    conn.close()

def eliminar_cita(paciente_id, fecha):
    fecha = ensure_utc(fecha)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM citas WHERE paciente_id = %s AND fecha = %s", (paciente_id, fecha))
    conn.commit()
    cursor.close()
    conn.close()

def log_accion(accion, datos):
    """
    Registra acciones del sistema en Supabase para auditoría
    
    Args:
        accion: Tipo de acción (CITA_CREADA, CITA_EDITADA, etc.)
        datos: Diccionario con datos relevantes de la acción
    """
    try:
        # Usar Supabase si está configurado, sino usar PostgreSQL local
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if supabase_url and supabase_key:
            # TODO: Implementar log a Supabase cuando se configure
            # from supabase import create_client
            # supabase = create_client(supabase_url, supabase_key)
            # supabase.table("logs_sistema").insert({
            #     "accion": accion,
            #     "datos": datos,
            #     "timestamp": datetime.utcnow().isoformat(),
            #     "sistema": "saludtools_integration"
            # }).execute()
            print(f"📝 LOG: {accion} - {datos}")
        else:
            # Fallback a print si no hay Supabase configurado
            print(f"📝 LOG: {accion} - {datos}")
            
    except Exception as e:
        print(f"⚠️ Error en logging: {e}")
        # No fallar por errores de logging

# ===================== NUEVAS FUNCIONES ENRIQUECIDAS ===================== #

def upsert_paciente(
    documento: str,
    nombres: str,
    apellidos: str,
    telefono: str | None,
    email: str | None,
    preferencia_contacto: str | None,
    tipo_paciente: str | None = None,
    entidad: str | None = None,
    fecha_nacimiento: str | None = None,
    direccion: str | None = None,
    contacto_emergencia_nombre: str | None = None,
    contacto_emergencia_telefono: str | None = None,
    contacto_emergencia_parentesco: str | None = None,
):
    """Inserta o actualiza paciente por documento y retorna su id.

    Campos extendidos agregados en migración 05. Cualquier campo None no sobreescribe
    (excepto nombres/apellidos/telefono/email/preferencia_contacto que sí se actualizan siempre).
    fecha_nacimiento se acepta como str (YYYY-MM-DD) y se delega a Postgres para cast.
    """
    conn = get_connection()
    cur = conn.cursor()
    # Preparar sentencia dinámica para soportar columnas nuevas sin romper entorno antiguo.
    cur.execute(
        """
        INSERT INTO pacientes (
            documento, nombres, apellidos, telefono, email, preferencia_contacto, tipo_paciente,
            entidad, fecha_nacimiento, direccion,
            contacto_emergencia_nombre, contacto_emergencia_telefono, contacto_emergencia_parentesco
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::date, %s, %s, %s, %s)
        ON CONFLICT (documento)
        DO UPDATE SET nombres = EXCLUDED.nombres,
                      apellidos = EXCLUDED.apellidos,
                      telefono = EXCLUDED.telefono,
                      email = EXCLUDED.email,
                      preferencia_contacto = EXCLUDED.preferencia_contacto,
                      tipo_paciente = COALESCE(EXCLUDED.tipo_paciente, pacientes.tipo_paciente),
                      entidad = COALESCE(EXCLUDED.entidad, pacientes.entidad),
                      fecha_nacimiento = COALESCE(EXCLUDED.fecha_nacimiento, pacientes.fecha_nacimiento),
                      direccion = COALESCE(EXCLUDED.direccion, pacientes.direccion),
                      contacto_emergencia_nombre = COALESCE(EXCLUDED.contacto_emergencia_nombre, pacientes.contacto_emergencia_nombre),
                      contacto_emergencia_telefono = COALESCE(EXCLUDED.contacto_emergencia_telefono, pacientes.contacto_emergencia_telefono),
                      contacto_emergencia_parentesco = COALESCE(EXCLUDED.contacto_emergencia_parentesco, pacientes.contacto_emergencia_parentesco),
                      updated_at = now()
        RETURNING id
        """,
        (
            documento,
            nombres,
            apellidos,
            telefono,
            email,
            preferencia_contacto,
            tipo_paciente,
            entidad,
            fecha_nacimiento,
            direccion,
            contacto_emergencia_nombre,
            contacto_emergencia_telefono,
            contacto_emergencia_parentesco,
        ),
    )
    paciente_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return paciente_id

def update_paciente_extended(paciente_id: str, **kwargs):
    """Actualiza parcialmente campos extendidos del paciente.

    Acepta kwargs entre: entidad, fecha_nacimiento, direccion, contacto_emergencia_nombre,
    contacto_emergencia_telefono, contacto_emergencia_parentesco, plan_salud, tiene_orden_medica.
    Ignora claves desconocidas. No actualiza campos None.
    """
    allowed = {
        'entidad', 'fecha_nacimiento', 'direccion', 'contacto_emergencia_nombre',
        'contacto_emergencia_telefono', 'contacto_emergencia_parentesco', 'plan_salud', 'tiene_orden_medica'
    }
    sets = []
    values = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if k == 'fecha_nacimiento':
                sets.append(f"{k} = %s::date")
            else:
                sets.append(f"{k} = %s")
            values.append(v)
    if not sets:
        return False
    values.append(paciente_id)
    sql = f"UPDATE pacientes SET {', '.join(sets)}, updated_at = now() WHERE id = %s"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, values)
    conn.commit()
    cur.close()
    conn.close()
    return True

def insertar_cita_enriquecida(paciente_id: str, especialista_id: str, tipo_cita: str, start_at, end_at, duracion_min: int, notas: str | None, estado: str = 'scheduled', fuente: str = 'whatsapp', especialista_nombre: str | None = None, franja: str | None = None, plan_salud: str | None = None, tiene_orden_medica: bool | None = None):
    """Inserta una cita enriquecida y retorna su id.

    A partir de la migración 02_add_saludtools_id.sql existe una columna dedicada
    para saludtools_id. Este valor se insertará después (cuando se conozca la respuesta
    del API remoto) usando set_saludtools_id().
    """
    start_at = ensure_utc(start_at)
    end_at = ensure_utc(end_at)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO citas_enriquecida (
            paciente_id, especialista_id, especialista_nombre, tipo_cita, estado, fuente,
            start_at, end_at, duracion_min, franja, plan_salud, tiene_orden_medica, notas
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (paciente_id, especialista_id, especialista_nombre, tipo_cita, estado, fuente, start_at, end_at, duracion_min, franja, plan_salud, tiene_orden_medica, notas)
    )
    cita_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return cita_id

def actualizar_cita_enriquecida(cita_id: str, start_at, end_at, notas: str | None = None):
    start_at = ensure_utc(start_at)
    end_at = ensure_utc(end_at)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE citas_enriquecida
        SET start_at = %s, end_at = %s, duracion_min = EXTRACT(EPOCH FROM (%s - %s))/60, notas = COALESCE(%s, notas), updated_at = now()
        WHERE id = %s
        """,
        (start_at, end_at, end_at, start_at, notas, cita_id)
    )
    conn.commit()
    cur.close()
    conn.close()

def marcar_cita_cancelada(cita_id: str, reason: str | None = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE citas_enriquecida
        SET estado = 'cancelled', cancelled_at = now(), cancellation_reason = COALESCE(%s, cancellation_reason), updated_at = now()
        WHERE id = %s
        """,
        (reason, cita_id)
    )
    conn.commit()
    cur.close()
    conn.close()

def buscar_cita_enriquecida_por_paciente_y_inicio(paciente_id: str, start_at, tolerancia_minutos: int = 30):
    """Busca una cita cuyo start_at esté dentro de la tolerancia dada."""
    start_at = ensure_utc(start_at)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, start_at, end_at FROM citas_enriquecida
        WHERE paciente_id = %s
          AND start_at BETWEEN %s - (%s * interval '1 minute') AND %s + (%s * interval '1 minute')
        ORDER BY ABS(EXTRACT(EPOCH FROM (start_at - %s))) ASC
        LIMIT 1
        """,
        (paciente_id, start_at, tolerancia_minutos, start_at, tolerancia_minutos, start_at)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def registrar_historial_cita(cita_id: str, evento: str, snapshot: dict):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO citas_historial (cita_id, evento, snapshot)
        VALUES (%s, %s, %s::jsonb)
        """,
        (cita_id, evento, json.dumps(snapshot, ensure_ascii=False))
    )
    conn.commit()
    cur.close()
    conn.close()

def log_accion_db(accion: str, metadata: dict):
    """Inserta log estructurado en logs_acciones."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO logs_acciones (accion, metadata) VALUES (%s, %s::jsonb)""",
        (accion, json.dumps(metadata, ensure_ascii=False))
    )
    conn.commit()
    cur.close()
    conn.close()

# === Consultas de apoyo para demo ===
def listar_citas_enriquecidas_por_paciente(paciente_id: str):
    """Retorna citas enriquecidas básicas para un paciente (ordenadas por start_at desc)."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, start_at, end_at, estado, tipo_cita, especialista_id, notas
            FROM citas_enriquecida
            WHERE paciente_id = %s
            ORDER BY start_at DESC
            LIMIT 10
            """,
            (paciente_id,)
        )
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                'id': r[0],
                'start_at': ensure_utc(r[1]),
                'end_at': ensure_utc(r[2]),
                'estado': r[3],
                'tipo_cita': r[4],
                'especialista_id': r[5],
                'notas': r[6],
            })
        return result
    finally:
        cur.close()
        conn.close()

def buscar_cita_por_saludtools_id(remote_id: int | str):
    """Busca una cita_enriquecida por el id remoto usando la columna dedicada si existe.

    Fallback: si la columna no está poblada intenta el patrón legacy dentro de notas.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                """
                SELECT id, paciente_id, start_at, end_at, estado, tipo_cita, especialista_id, notas
                FROM citas_enriquecida
                WHERE saludtools_id = %s
                LIMIT 1
                """,
                (int(remote_id),)
            )
        except Exception:
            # Columna puede no existir aún -> fallback legacy
            pattern = f"saludtools_id={remote_id}%"
            cur.execute(
                """
                SELECT id, paciente_id, start_at, end_at, estado, tipo_cita, especialista_id, notas
                FROM citas_enriquecida
                WHERE notas LIKE %s
                LIMIT 1
                """,
                (pattern,)
            )
        row = cur.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'paciente_id': row[1],
            'start_at': ensure_utc(row[2]),
            'end_at': ensure_utc(row[3]),
            'estado': row[4],
            'tipo_cita': row[5],
            'especialista_id': row[6],
            'notas': row[7]
        }
    finally:
        cur.close()
        conn.close()

def update_notas_cita(local_id: str, nuevas_notas: str):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE citas_enriquecida SET notas = %s, updated_at = now() WHERE id = %s",
            (nuevas_notas, local_id)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def set_saludtools_id(local_id: str, saludtools_id: int):
    """Setea la columna saludtools_id para una cita local (idempotente)."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                "UPDATE citas_enriquecida SET saludtools_id = %s, updated_at = now() WHERE id = %s",
                (saludtools_id, local_id)
            )
        except Exception:
            # Columna podría no estar migrada todavía, ignorar silenciosamente
            pass
        conn.commit()
    finally:
        cur.close()
        conn.close()

# ===================== HANDOFF PERSISTENCIA ===================== #

def handoff_upsert_secretary(phone: str, display_name: str | None = None, capacity: int = 1, active: bool = True):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO secretarias (phone, display_name, tenant_key, capacity, active)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (phone)
        DO UPDATE SET display_name = COALESCE(EXCLUDED.display_name, secretarias.display_name),
                      capacity = EXCLUDED.capacity,
                      active = EXCLUDED.active,
                      updated_at = now()
        """,
        (phone, display_name, TENANT_KEY, capacity, active)
    )
    conn.commit()
    cur.close()
    conn.close()

def handoff_list_secretaries():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT phone, display_name, capacity, assigned, active FROM secretarias WHERE tenant_key = %s ORDER BY phone", (TENANT_KEY,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"phone": r[0], "display_name": r[1], "capacity": r[2], "assigned": r[3], "active": r[4]}
        for r in rows
    ]

def handoff_pick_available_secretary():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT phone
        FROM secretarias
        WHERE tenant_key = %s AND active = true AND assigned < capacity
        ORDER BY assigned ASC, updated_at ASC
        LIMIT 1
        """,
        (TENANT_KEY,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def handoff_inc_assigned(phone: str, delta: int = 1):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE secretarias SET assigned = GREATEST(0, assigned + %s), updated_at = now() WHERE phone = %s AND tenant_key = %s""",
        (delta, phone, TENANT_KEY)
    )
    conn.commit()
    cur.close()
    conn.close()

def handoff_create_escalation(case_id: str, telefono_usuario: str, motivo: str, historial: dict, estado: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO escalaciones_handoff (case_id, telefono_usuario, motivo, tenant_key, estado, historial)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (case_id) DO NOTHING
        """,
        (case_id, telefono_usuario, motivo, TENANT_KEY, estado, json.dumps(historial, ensure_ascii=False))
    )
    conn.commit()
    cur.close()
    conn.close()

def handoff_set_assignment(case_id: str, secretaria_phone: str | None, estado: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE escalaciones_handoff SET assigned_to = %s, estado = %s, updated_at = now() WHERE case_id = %s AND tenant_key = %s""",
        (secretaria_phone, estado, case_id, TENANT_KEY)
    )
    conn.commit()
    cur.close()
    conn.close()

def handoff_mark_queued(case_id: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE escalaciones_handoff SET estado = 'queued', queued_at = now(), updated_at = now() WHERE case_id = %s AND tenant_key = %s""",
        (case_id, TENANT_KEY)
    )
    conn.commit()
    cur.close()
    conn.close()

def handoff_next_queued_case():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT case_id, telefono_usuario
        FROM escalaciones_handoff
        WHERE tenant_key = %s AND estado = 'queued'
        ORDER BY queued_at ASC
        LIMIT 1
        """,
        (TENANT_KEY,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return {"case_id": row[0], "telefono_usuario": row[1]}

def handoff_close_case(case_id: str, final_state: str = 'resolved'):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE escalaciones_handoff SET estado = %s, updated_at = now() WHERE case_id = %s AND tenant_key = %s""",
        (final_state, case_id, TENANT_KEY)
    )
    conn.commit()
    cur.close()
    conn.close()

# ============================================================================
# FUNCIONES DE COMPATIBILIDAD PARA TESTS Y CÓDIGO LEGACY
# ============================================================================

def buscar_paciente_por_cedula(documento):
    """Alias para obtener_paciente_por_documento para compatibilidad."""
    return obtener_paciente_por_documento(documento)

def obtener_citas_activas_paciente(paciente_id):
    """Obtiene citas activas de un paciente."""
    return listar_citas_enriquecidas_por_paciente(paciente_id)

def cancelar_cita(cita_id: str, reason: str = "Cancelada por solicitud del paciente"):
    """Alias para marcar_cita_cancelada."""
    return marcar_cita_cancelada(cita_id, reason)

def crear_cita_con_validacion(paciente_id: str, fecha, descripcion: str, **kwargs):
    """Función de compatibilidad para crear citas con validación."""
    from datetime import datetime
    if isinstance(fecha, str):
        fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
    
    # Usar insertar_cita_enriquecida si tenemos más datos
    if kwargs:
        return insertar_cita_enriquecida(
            paciente_id=paciente_id,
            especialista_id=kwargs.get('especialista_id', 'default'),
            tipo_cita=kwargs.get('tipo_cita', 'FISIO'),
            start_at=fecha,
            end_at=kwargs.get('end_at', fecha),
            duracion_min=kwargs.get('duracion_min', 60),
            notas=descripcion,
            **{k: v for k, v in kwargs.items() if k not in ['especialista_id', 'tipo_cita', 'end_at', 'duracion_min']}
        )
    else:
        return insertar_cita(paciente_id, fecha, descripcion)

def crear_paciente(nombre, documento, telefono, email=None, preferencia_contacto="whatsapp", plan_salud=None, tiene_orden_medica=None):
    """Alias para insertar_paciente - compatibilidad con imports"""
    return insertar_paciente(nombre, documento, telefono, email, preferencia_contacto, plan_salud, tiene_orden_medica)

def obtener_citas_por_documento(documento):
    """Obtener todas las citas de un paciente por su documento"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.fecha, c.descripcion, p.nombres, p.apellidos 
        FROM citas c 
        JOIN pacientes p ON c.paciente_id = p.id 
        WHERE p.documento = %s 
        ORDER BY c.fecha
    """, (documento,))
    citas = []
    for row in cursor.fetchall():
        citas.append({
            "fecha": ensure_utc(row[0]),
            "descripcion": row[1],
            "paciente": f"{row[2]} {row[3]}".strip()
        })
    cursor.close()
    conn.close()
    return citas
