"""
Módulo de integración con Saludtools API
Maneja autenticación, pacientes, citas y webhooks.
"""

import requests
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import json
import time
import random
try:
    from app.metrics import incr
except Exception:
    def incr(*args, **kwargs):
        pass

# Configuración de logging
logger = logging.getLogger(__name__)

class SaludtoolsAPI:
    def __init__(self, environment: Optional[str] = None):
        """
        Inicializa el cliente de Saludtools API

        Args:
            environment: Ambiente objetivo. Aceptados (case-insensitive):
                - pruebas: "testing", "test", "qa", "sandbox"
                - producción: "prod", "production", "live"
                Si no se especifica, se intenta leer de las variables de entorno
                SALUDTOOLS_ENVIRONMENT o ENVIRONMENT. Por defecto: "testing".
        """
        # Resolver ambiente desde argumento o variables de entorno
        env = (
            (environment or "")
            or os.getenv("SALUDTOOLS_ENVIRONMENT", "")
            or os.getenv("ENVIRONMENT", "")
        ).strip().lower()
        if not env:
            env = "testing"

        self.environment = env
        # Permitir override explícito por variable SALUDTOOLS_BASE_URL
        self.base_url = os.getenv("SALUDTOOLS_BASE_URL") or self._get_base_url()
        self.api_key = os.getenv("SALUDTOOLS_API_KEY")
        self.api_secret = os.getenv("SALUDTOOLS_API_SECRET")
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        if not self.api_key or not self.api_secret:
            logger.warning("Credenciales de Saludtools no configuradas. Usando modo mock.")
            self.mock_mode = True
        else:
            self.mock_mode = False
    
    def _get_base_url(self) -> str:
        """Retorna la URL base según el ambiente"""
        env = (self.environment or "").strip().lower()
        if env in {"testing", "test", "qa", "sandbox"}:
            # URL del ambiente QA confirmada por Saludtools
            return "https://saludtools.qa.carecloud.com.co/integration"
        if env in {"prod", "production", "live"}:
            return "https://saludtools.carecloud.com.co/integration"
        raise ValueError(
            "Environment inválido. Usa 'testing'/'qa' para pruebas o 'prod' para producción."
        )
    
    def _get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        """Genera headers para las requests"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if include_auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        return headers
    
    def _is_token_expired(self) -> bool:
        """Verifica si el token ha expirado"""
        if not self.token_expires_at:
            return True
        return datetime.utcnow() >= self.token_expires_at
    
    async def authenticate(self) -> bool:
        """
        Autentica con Saludtools y obtiene access_token
        
        Returns:
            bool: True si la autenticación fue exitosa
        """
        if self.mock_mode:
            logger.info("Modo mock: Autenticación simulada exitosa")
            self.access_token = "mock_access_token"
            self.token_expires_at = datetime.utcnow() + timedelta(hours=12)
            return True
        
        url = f"{self.base_url}/authenticate/apikey/v1/"
        payload = {"key": self.api_key, "secret": self.api_secret}
        max_attempts = int(os.getenv("RETRY_MAX", "3"))
        backoff_base = float(os.getenv("RETRY_BACKOFF_BASE", "0.8"))
        for attempt in range(1, max_attempts + 1):
            incr('saludtools_auth_attempt')
            try:
                resp = requests.post(url, json=payload, headers=self._get_headers(include_auth=False), timeout=15)
                if resp.status_code >= 500:
                    raise requests.exceptions.RequestException(f"Status {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                expires_in = data.get("expires_in", 86400)
                self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                incr('saludtools_auth_success')
                logger.info(f"Autenticación exitosa (attempt={attempt}) expira en {expires_in}s")
                return True
            except requests.exceptions.RequestException as e:
                if attempt == max_attempts:
                    incr('saludtools_auth_error')
                    logger.error("Autenticación fallida tras %s intentos: %s", max_attempts, e)
                    return False
                wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                logger.warning("Fallo auth intento=%s/%s error=%s (retry en %.2fs)", attempt, max_attempts, e, wait)
                time.sleep(wait)
    
    async def ensure_authenticated(self) -> bool:
        """Asegura que tenemos un token válido"""
        if self.access_token and not self._is_token_expired():
            return True
        
        return await self.authenticate()
    
    async def refresh_access_token(self) -> bool:
        """Refresca el access_token usando refresh_token"""
        if self.mock_mode:
            return await self.authenticate()
        
        # TODO: Implementar refresh token cuando Saludtools confirme el endpoint
        logger.info("Refresh token no implementado, re-autenticando...")
        return await self.authenticate()
    
    # PACIENTES
    def _build_event_payload(self, event_type: str, action_type: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Crea el payload estándar (eventType/actionType/body) sin campos extra no soportados."""
        return {"eventType": event_type, "actionType": action_type, "body": body}

    def _post_event(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """POST con reintentos exponenciales simples.

        Reintenta ante errores de red, timeouts, 5xx y 429.
        No reintenta otros 4xx.
        """
        url = f"{self.base_url}/sync/event/v1/"
        debug = os.getenv("SALUDTOOLS_DEBUG", "").lower() in {"1","true","yes","on"}
        max_attempts = int(os.getenv("RETRY_MAX", "3"))
        backoff_base = float(os.getenv("RETRY_BACKOFF_BASE", "0.8"))
        for attempt in range(1, max_attempts + 1):
            incr('saludtools_post_attempt')
            try:
                if debug and attempt == 1:
                    logger.debug("[saludtools] POST %s payload=%s", payload.get("actionType"), json.dumps(payload, ensure_ascii=False))
                resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=20)
                status = resp.status_code
                retryable = status >= 500 or status == 429
                if status >= 400 and not retryable:
                    content_snippet = resp.text[:800]
                    logger.error("Error Saludtools status=%s eventType=%s actionType=%s body=%s", status, payload.get("eventType"), payload.get("actionType"), content_snippet)
                    resp.raise_for_status()
                if retryable and attempt < max_attempts:
                    wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                    logger.warning("Retryable status=%s intento=%s/%s wait=%.2fs", status, attempt, max_attempts, wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json() if resp.content else {}
                if debug:
                    logger.debug("[saludtools] OK status=%s eventType=%s actionType=%s", status, payload.get("eventType"), payload.get("actionType"))
                return data
            except requests.exceptions.RequestException as e:
                if attempt == max_attempts:
                    incr('saludtools_post_error')
                    resp = getattr(e, 'response', None)
                    status = resp.status_code if resp is not None else 'NO_RESPONSE'
                    text = (resp.text[:600] if resp and getattr(resp,'text',None) else '')
                    logger.error("Excepción POST final status=%s eventType=%s actionType=%s error=%s snippet=%s", status, payload.get("eventType"), payload.get("actionType"), e, text)
                    return None
                wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                logger.warning("Excepción POST intento=%s/%s error=%s retry=%.2fs", attempt, max_attempts, e, wait)
                time.sleep(wait)
        return None

    async def buscar_paciente_por_documento(self, documento: str, tipo_documento: int = 1) -> Optional[Dict]:
        """Lee (READ) un paciente por tipo y número de documento usando la especificación oficial.

        Docs: /patientread -> actionType READ, eventType PATIENT
        Body requerido: { "documentType": <id>, "documentNumber": "..." }
        """
        if not await self.ensure_authenticated():
            return None

        if self.mock_mode:
            return {
                "id": 12345,
                "firstName": "Juan",
                "firstLastName": "Pérez",
                "documentType": tipo_documento,
                "documentNumber": documento,
                "phone": "3001234567",
                "email": "juan.perez@email.com"
            }

        payload = self._build_event_payload("PATIENT", "READ", {"documentType": tipo_documento, "documentNumber": documento})
        data = self._post_event(payload)
        if not data:
            return None
        body = data.get("body")
        if not body:
            return None
        return body
    
    async def crear_paciente(self, datos_paciente: Dict) -> Optional[Dict]:
        """Crea un paciente (CREATE) normalizando campos a la nomenclatura de la API.

        Campos esperados (según docs generales):
          - firstName (string)
          - secondName (opcional)
          - firstLastName (string)  (en tests internos usamos 'lastName' -> map a firstLastName)
          - secondLastName (opcional)
          - documentType (int id tipo documento)
          - documentNumber (string)
          - gender (int? / string?) (opcional)
          - birthDate (YYYY-MM-DD) (opcional)
          - phone / cellPhone (opcional)
          - email (opcional)
        """
        if not await self.ensure_authenticated():
            return None

        if self.mock_mode:
            return {
                "id": 12346,
                "firstName": datos_paciente.get("firstName"),
                "firstLastName": datos_paciente.get("firstLastName") or datos_paciente.get("lastName"),
                "documentNumber": datos_paciente.get("documentNumber"),
                "created": True
            }

        # Normalización de claves provenientes de capas superiores
        body = dict(datos_paciente)
        # Map lastName -> firstLastName si falta
        if "firstLastName" not in body and "lastName" in body:
            parts = str(body["lastName"]).split()
            if parts:
                body["firstLastName"] = parts[0]
                if len(parts) > 1 and "secondLastName" not in body:
                    body["secondLastName"] = " ".join(parts[1:])
        # Asegurar documentType / documentNumber (compat: documentTypeId -> documentType)
        if "documentType" not in body and "documentTypeId" in body:
            body["documentType"] = body.pop("documentTypeId")
        if "documentNumber" not in body and "document" in body:
            body["documentNumber"] = body.pop("document")

        # Filtrar solo campos potencialmente soportados (evitar ruido)
        allowed = {"firstName","secondName","firstLastName","secondLastName","documentType","documentNumber","gender","birthDate","phone","cellPhone","email","habeasData"}
        body = {k:v for k,v in body.items() if k in allowed}

        # Requeridos mínimos
        required = ["firstName","firstLastName","documentType","documentNumber"]
        faltantes = [r for r in required if r not in body or body[r] in (None,"")]
        if faltantes:
            logger.error(f"Faltan campos requeridos para crear paciente: {faltantes}")
            return None

        try:
            payload = self._build_event_payload("PATIENT", "CREATE", body)
            data = self._post_event(payload)
            if not data:
                return None
            return data.get("body") or data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creando paciente: {e}")
            return None
    
    # CITAS
    async def buscar_citas_por_documento(self, documento: str, tipo_documento: int = 1) -> List[Dict]:
        """Filtra citas por documento de paciente usando actionType SEARCH.

        Docs: /appointmentsearch -> requiere pageable.page & pageable.size (page inicia en 0)
        Cuerpo mínimo para filtrar por paciente: {
            "patientDocumentType": <id>,
            "patientDocumentNumber": "...",
            "pageable": {"page": 0, "size": 20}
        }
        """
        if not await self.ensure_authenticated():
            return []
        
        if self.mock_mode:
            return [
                {
                    "id": 67890,
                    "startDate": "2025-07-15 10:00",
                    "endDate": "2025-07-15 10:30",
                    "appointmentType": "Consulta general",
                    "appointmentState": "PENDING",
                    "patientDocument": documento
                }
            ]
        
        try:
            search_body = {
                "patientDocumentType": tipo_documento,
                "patientDocumentNumber": documento,
                "pageable": {"page": 0, "size": 20}
            }
            payload = self._build_event_payload("APPOINTMENT", "SEARCH", search_body)
            data = self._post_event(payload)
            if not data:
                return []
            body = data.get("body")
            if not body:
                return []
            # La estructura exitosa incluye body.content (lista) o body como lista (fallback viejo)
            if isinstance(body, dict) and "content" in body and isinstance(body["content"], list):
                return body["content"]
            if isinstance(body, list):
                return body
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error buscando citas para documento {documento}: {e}")
            return []
    
    # === Helpers internos ===
    @staticmethod
    def _fmt_datetime(dt_str: str) -> str:
        """Normaliza datetime string a 'YYYY-MM-DD HH:MM' (sin segundos)."""
        if 'T' in dt_str:
            dt_str = dt_str.replace('T', ' ')
        dt_str = dt_str.replace('Z','').strip()
        if '.' in dt_str:
            dt_str = dt_str.split('.')[0]
        parts = dt_str.split(':')
        if len(parts) >= 2:
            return f"{parts[0]}:{parts[1]}"
        return dt_str

    def _debug_enabled(self) -> bool:
        return os.getenv("SALUDTOOLS_DEBUG", "").lower() in {"1","true","yes","on"}

    # Cache simple (parametric endpoints) -> (key -> (data, fetched_at))
    _cache: Dict[str, tuple] = {}
    _cache_ttl_seconds = 300

    def _get_cached(self, key: str, loader: Callable[[], List[Dict]] ) -> List[Dict]:
        now = datetime.utcnow()
        if key in self._cache:
            data, ts = self._cache[key]
            if (now - ts).total_seconds() < self._cache_ttl_seconds:
                return data
        try:
            data = loader()
            self._cache[key] = (data, now)
            return data
        except Exception:
            return []

    async def crear_cita(self, datos_cita: Dict) -> Optional[Dict]:
        """
        Crea una nueva cita en Saludtools
        
        Args:
            datos_cita: Diccionario con datos de la cita
        
        Returns:
            Datos de la cita creada o None si falló
        """
        if not await self.ensure_authenticated():
            return None
        
        if self.mock_mode:
            return {
                "id": 67891,
                "startDate": datos_cita.get("startDate"),
                "endDate": datos_cita.get("endDate"),
                "appointmentType": datos_cita.get("appointmentType"),
                "appointmentState": "PENDING",
                "created": True
            }
        
        try:
            normalizada = dict(datos_cita)
            # Mapear alias internos a los de la API
            if "startDate" in normalizada:
                normalizada.setdefault("startAppointment", normalizada.pop("startDate"))
            if "endDate" in normalizada:
                normalizada.setdefault("endAppointment", normalizada.pop("endDate"))
            if "appointmentState" in normalizada:
                normalizada.setdefault("stateAppointment", normalizada.pop("appointmentState"))
            # Formato de fecha requerido: 'YYYY-MM-DD HH:mm'
            if isinstance(normalizada.get("startAppointment"), str):
                normalizada["startAppointment"] = self._fmt_datetime(normalizada["startAppointment"])
            if isinstance(normalizada.get("endAppointment"), str):
                normalizada["endAppointment"] = self._fmt_datetime(normalizada["endAppointment"])

            # Campos requeridos según docs
            requeridos = [
                "startAppointment","endAppointment","patientDocumentType","patientDocumentNumber",
                "doctorDocumentType","doctorDocumentNumber","modality","stateAppointment","appointmentType","clinic"
            ]
            # Auto-completar doctor y clínica desde variables de entorno si faltan
            if "doctorDocumentType" not in normalizada:
                env_doc_type = os.getenv("SALUDTOOLS_DOCTOR_DOCUMENT_TYPE")
                if env_doc_type:
                    normalizada["doctorDocumentType"] = int(env_doc_type)
            if "doctorDocumentNumber" not in normalizada:
                env_doc_num = os.getenv("SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER")
                if env_doc_num:
                    normalizada["doctorDocumentNumber"] = env_doc_num
            if "clinic" not in normalizada:
                env_clinic = os.getenv("SALUDTOOLS_CLINIC_ID")
                if env_clinic:
                    normalizada["clinic"] = int(env_clinic)
            faltantes = [c for c in requeridos if c not in normalizada or normalizada[c] in (None,"")]
            if faltantes:
                logger.error(f"Faltan campos requeridos para crear cita: {faltantes}")
                return None
            # Validación adicional: mostrar payload si luego ocurre 412
            debug_snapshot = {k: normalizada.get(k) for k in requeridos}

            # Compatibilidad opcional: sólo duplicar a 'clinicId' si variable lo habilita
            if (
                'clinic' in normalizada 
                and 'clinicId' not in normalizada 
                and os.getenv("SALUDTOOLS_ADD_CLINIC_ID", "").lower() in {"1","true","yes","on"}
            ):
                normalizada['clinicId'] = normalizada['clinic']

            debug_on = self._debug_enabled()
            if debug_on:
                try:
                    dbg = dict(normalizada)
                    if 'doctorDocumentNumber' in dbg and isinstance(dbg['doctorDocumentNumber'], str):
                        dd = dbg['doctorDocumentNumber']
                        dbg['doctorDocumentNumber'] = ('***' + dd[-3:]) if len(dd) > 3 else '***'
                    logger.info("[DEBUG] Payload crear cita=%s", json.dumps(dbg, ensure_ascii=False))
                except Exception:
                    logger.info("[DEBUG] Payload crear cita (repr)=%r", normalizada)

            # Validar doctor antes de intentar crear (para dar mensaje temprano)
            if not await self.validar_doctor(normalizada.get("doctorDocumentType"), normalizada.get("doctorDocumentNumber")):
                logger.error("Doctor no válido en Saludtools (tipo=%s, numero=%s)", normalizada.get("doctorDocumentType"), normalizada.get("doctorDocumentNumber"))
                return {"error": "DOCTOR_NOT_FOUND", "message": "El médico no existe o no está activo en Saludtools"}

            # Filtrar solo campos permitidos (lista conservadora). Evita 412 por campos extra.
            permitidos_create = {
                "startAppointment","endAppointment","patientDocumentType","patientDocumentNumber",
                "doctorDocumentType","doctorDocumentNumber","modality","stateAppointment",
                "appointmentType","clinic","comment","notificationState"
            }
            body_final = {k: v for k, v in normalizada.items() if k in permitidos_create and v not in (None, "")}
            payload = self._build_event_payload("APPOINTMENT", "CREATE", body_final)
            if debug_on:
                logger.info("[DEBUG] Body filtrado crear cita=%s", body_final)
            data = self._post_event(payload)
            if not data:
                return None
            # Normalizar respuesta: cuando body es null pero message contiene el id
            body = data.get("body")
            message = data.get("message") or ""
            appt_id = None
            if body and isinstance(body, dict):
                appt_id = body.get("id") or body.get("appointmentId")
            if not appt_id and message and "cita id:" in message.lower():
                # Extraer número después de 'cita id:'
                import re
                m = re.search(r"cita id:\s*(\d+)", message.lower())
                if m:
                    appt_id = int(m.group(1))
            if appt_id is not None:
                try:
                    incr(f"cita_tipo_{normalizada.get('appointmentType','UNKNOWN')}")
                except Exception:
                    pass
                return {
                    "id": appt_id,
                    "created": True,
                    "raw": data,
                    "state": normalizada.get("stateAppointment"),
                    "startAppointment": normalizada.get("startAppointment"),
                    "endAppointment": normalizada.get("endAppointment"),
                    "patientDocumentNumber": normalizada.get("patientDocumentNumber")
                }
            # Si el código fue 412 aunque no se extrajo id, log ampliado
            try:
                code_val = data.get('code') if isinstance(data, dict) else None
                if code_val == 412:
                    try:
                        incr('citas_412')
                    except Exception:
                        pass
                    logger.error("Diagnóstico 412 crear cita -> snapshot=%s response=%s", debug_snapshot, data)
            except Exception:
                pass
            # Si hubo 4xx y debug activo, registrar cuerpo bruto para comparación
            if debug_on and isinstance(data, dict) and data.get('code') and int(data.get('code')) >= 400:
                try:
                    logger.info("[DEBUG] Respuesta error crear cita=%s", json.dumps(data, ensure_ascii=False))
                except Exception:
                    logger.info("[DEBUG] Respuesta error crear cita (repr)=%r", data)
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creando cita: {e}")
            return None

    async def validar_doctor(self, doctor_document_type: Optional[int], doctor_document_number: Optional[str]) -> bool:
        """Valida existencia de un doctor usando APPOINTMENT SEARCH.

        Estrategia: realizar SEARCH con solo doctorDocumentType/doctorDocumentNumber y pageable mínima.
        - Si respuesta 200 => doctor reconocido (aunque sin citas => content puede estar vacío).
        - Si 412 y mensaje contiene 'No se ha encontrado ningun medico' => doctor inexistente.
        - Otros códigos => indeterminado (retorna False para forzar diagnóstico).
        """
        if self.mock_mode:
            return True
        if not doctor_document_type or not doctor_document_number:
            return False
        if not await self.ensure_authenticated():
            return False
        search_body = {
            "doctorDocumentType": doctor_document_type,
            "doctorDocumentNumber": doctor_document_number,
            "pageable": {"page": 0, "size": 1}
        }
        payload = self._build_event_payload("APPOINTMENT", "SEARCH", search_body)
        url = f"{self.base_url}/sync/event/v1/"
        try:
            resp = requests.post(url, json=payload, headers=self._get_headers())
            if resp.status_code == 200:
                return True
            if resp.status_code == 412 and "No se ha encontrado ningun medico" in resp.text:
                return False
            # Otros 4xx/5xx: log y considerar inválido
            logger.warning("Validación de doctor retornó status=%s body=%s", resp.status_code, resp.text[:300])
            return False
        except Exception as e:
            logger.error("Error validando doctor: %s", e)
            return False
    
    async def actualizar_cita(self, id_cita: int, datos_cita: Dict) -> Optional[Dict]:
        """
        Actualiza una cita existente
        
        Args:
            id_cita: ID de la cita a actualizar
            datos_cita: Nuevos datos de la cita
        
        Returns:
            Datos de la cita actualizada o None si falló
        """
        if not await self.ensure_authenticated():
            return None
        
        if self.mock_mode:
            return {
                "id": id_cita,
                "updated": True,
                **datos_cita
            }
        
        try:
            normalizada = dict(datos_cita)
            # Alias -> campos de API
            if "startDate" in normalizada and "startAppointment" not in normalizada:
                normalizada["startAppointment"] = normalizada.pop("startDate")
            if "endDate" in normalizada and "endAppointment" not in normalizada:
                normalizada["endAppointment"] = normalizada.pop("endDate")
            if "appointmentState" in normalizada and "stateAppointment" not in normalizada:
                normalizada["stateAppointment"] = normalizada.pop("appointmentState")

            # Formato fechas HH:MM
            if isinstance(normalizada.get("startAppointment"), str):
                normalizada["startAppointment"] = self._fmt_datetime(normalizada["startAppointment"])
            if isinstance(normalizada.get("endAppointment"), str):
                normalizada["endAppointment"] = self._fmt_datetime(normalizada["endAppointment"])

            # Filtrar campos permitidos (heurístico basado en create)
            if 'appointmentType' not in normalizada:
                # Fallback desde variable de entorno si existe
                fallback_appt = os.getenv('SALUDTOOLS_DEFAULT_APPOINTMENT_TYPE')
                if fallback_appt:
                    normalizada['appointmentType'] = fallback_appt
            # Autocompletar doctor / clínica si faltan
            if 'doctorDocumentType' not in normalizada:
                env_doc_type = os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_TYPE')
                if env_doc_type:
                    normalizada['doctorDocumentType'] = int(env_doc_type)
            if 'doctorDocumentNumber' not in normalizada:
                env_doc_num = os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER')
                if env_doc_num:
                    normalizada['doctorDocumentNumber'] = env_doc_num
            if 'clinic' not in normalizada:
                env_clinic = os.getenv('SALUDTOOLS_CLINIC_ID')
                if env_clinic:
                    normalizada['clinic'] = int(env_clinic)
            # Paciente (puede ser requerido por UPDATE)
            if 'patientDocumentType' not in normalizada and os.getenv('SALUDTOOLS_DEFAULT_PATIENT_DOC_TYPE'):
                normalizada['patientDocumentType'] = int(os.getenv('SALUDTOOLS_DEFAULT_PATIENT_DOC_TYPE'))
            if 'patientDocumentNumber' not in normalizada and os.getenv('SALUDTOOLS_DEFAULT_PATIENT_DOC_NUMBER'):
                normalizada['patientDocumentNumber'] = os.getenv('SALUDTOOLS_DEFAULT_PATIENT_DOC_NUMBER')
            permitidos = {"id","startAppointment","endAppointment","patientDocumentType","patientDocumentNumber","doctorDocumentType","doctorDocumentNumber","modality","stateAppointment","appointmentType","clinic","notificationState","comment"}
            normalizada["id"] = id_cita
            normalizada = {k:v for k,v in normalizada.items() if k in permitidos}

            if os.getenv("SALUDTOOLS_DEBUG", "").lower() in {"1","true","yes","on"}:
                try:
                    logger.info("[DEBUG] Payload actualizar cita=%s", json.dumps(normalizada, ensure_ascii=False))
                except Exception:
                    logger.info("[DEBUG] Payload actualizar cita (repr)=%r", normalizada)

            payload = self._build_event_payload("APPOINTMENT", "UPDATE", normalizada)
            return self._post_event(payload)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error actualizando cita {id_cita}: {e}")
            return None
    
    async def cancelar_cita(self, id_cita: int) -> bool:
        """
        Cancela una cita
        
        Args:
            id_cita: ID de la cita a cancelar
        
        Returns:
            True si se canceló exitosamente
        """
        if not await self.ensure_authenticated():
            return False
        if self.mock_mode:
            logger.info(f"Modo mock: Cita {id_cita} cancelada exitosamente")
            return True

        try:
            payload = self._build_event_payload("APPOINTMENT", "DELETE", {"id": id_cita})
            data = self._post_event(payload)
            if data is None:
                return False
            logger.info(f"Cita {id_cita} cancelada en Saludtools. Respuesta: {data}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error cancelando cita {id_cita}: {e}")
            return False

    # ===== Wrappers de conveniencia (compatibilidad con tests existentes) =====
    async def buscar_paciente(self, documento: str, tipo_documento: int = 1) -> Optional[Dict]:
        return await self.buscar_paciente_por_documento(documento, tipo_documento)

    async def buscar_citas_paciente(self, documento: str, tipo_documento: int = 1) -> List[Dict]:
        return await self.buscar_citas_por_documento(documento, tipo_documento)

    async def crear_cita_paciente(self, datos_cita: Dict) -> Optional[Dict]:
        return await self.crear_cita(datos_cita)

    async def editar_cita_paciente(self, id_cita: int, datos_cita: Dict) -> Optional[Dict]:
        return await self.actualizar_cita(id_cita, datos_cita)

    async def cancelar_cita_paciente(self, id_cita: int) -> bool:
        return await self.cancelar_cita(id_cita)
    
    # PARÁMETROS DEL SISTEMA
    async def obtener_tipos_documento(self) -> List[Dict]:
        """Obtiene los tipos de documento disponibles"""
        if self.mock_mode:
            return [
                {"id": 1, "name": "Cédula de ciudadanía"},
                {"id": 2, "name": "Cédula de extranjería"},
                {"id": 3, "name": "Carné diplomático"}
            ]
        
        def loader():
            url = f"{self.base_url}/parametric/documents/v1/"
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        return self._get_cached("parametric_documents", loader)
    
    async def obtener_estados_cita(self) -> List[Dict]:
        """Obtiene los estados de cita disponibles"""
        if self.mock_mode:
            return [
                {"id": "PENDING", "name": "Pendiente"},
                {"id": "CONFIRMED", "name": "Confirmada"},
                {"id": "CANCELLED", "name": "Cancelada"}
            ]
        
        def loader():
            url = f"{self.base_url}/parametric/states/v1/"
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        return self._get_cached("parametric_states", loader)
    
    async def obtener_tipos_cita(self) -> List[Dict]:
        """Obtiene los tipos de cita disponibles"""
        if self.mock_mode:
            try:
                from .config import obtener_todos_tipos_citas
                return obtener_todos_tipos_citas()
            except ImportError:
                return [
                    {"id": "primera_vez", "name": "Primera vez", "duracion": 30},
                    {"id": "control", "name": "Control", "duracion": 30}
                ]
        
        def loader():
            try:
                url = f"{self.base_url}/parametric/appointment-types/v1/"
                response = requests.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except Exception:
                from .config import obtener_todos_tipos_citas  # fallback
                return obtener_todos_tipos_citas()
        return self._get_cached("parametric_appointment_types", loader)

    async def obtener_clinicas(self) -> List[Dict]:
        """Obtiene la lista de clínicas disponibles para la compañía (intento heurístico de endpoint).

        Endpoint supuesto siguiendo patrón de otros paramétricos: /parametric/clinics/v1/
        Si el endpoint no existe (404) o falla, retorna lista vacía.
        """
        if self.mock_mode:
            return [
                {"id": 1, "name": "Clínica Demo Centro"},
                {"id": 2, "name": "Clínica Demo Norte"}
            ]
        try:
            url = f"{self.base_url}/parametric/clinics/v1/"
            response = requests.get(url, headers=self._get_headers())
            if response.status_code == 404:
                logger.warning("Endpoint de clínicas no encontrado (404). Verifique documentación oficial.")
                return []
            response.raise_for_status()
            data = response.json()
            # Aceptar tanto lista como dict con 'body'
            if isinstance(data, dict) and 'body' in data:
                body = data['body']
                if isinstance(body, dict) and 'content' in body and isinstance(body['content'], list):
                    return body['content']
                if isinstance(body, list):
                    return body
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.error("Error obteniendo clínicas: %s", e)
            return []


# Funciones de conveniencia
# El cliente detecta automáticamente el ambiente desde ENVIRONMENT/SALUDTOOLS_ENVIRONMENT
saludtools_client = SaludtoolsAPI()

async def buscar_paciente(documento: str) -> Optional[Dict]:
    """Busca un paciente por documento"""
    return await saludtools_client.buscar_paciente_por_documento(documento)

async def buscar_citas_paciente(documento: str) -> List[Dict]:
    """Busca citas de un paciente"""
    return await saludtools_client.buscar_citas_por_documento(documento)

async def crear_cita_paciente(datos_cita: Dict) -> Optional[Dict]:
    """Crea una cita para un paciente"""
    return await saludtools_client.crear_cita(datos_cita)

async def editar_cita_paciente(id_cita: int, datos_cita: Dict) -> Optional[Dict]:
    """Edita una cita existente"""
    return await saludtools_client.actualizar_cita(id_cita, datos_cita)

async def cancelar_cita_paciente(id_cita: int) -> bool:
    """Cancela una cita"""
    return await saludtools_client.cancelar_cita(id_cita)
