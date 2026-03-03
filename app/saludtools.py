"""
MÓDULO DE INTEGRACIÓN CON SALUDTOOLS API
========================================
Cliente completo para interactuar con la API de Saludtools.

Funcionalidades:
- Autenticación y gestión de tokens
- CRUD de pacientes
- CRUD de citas médicas
- Gestión de webhooks
- Sistema de reintentos automático (Bug #5 fix)

Características de Confiabilidad:
- Reintentos automáticos con backoff exponencial
- Validación de tokens y re-autenticación automática
- Logging estructurado de todas las operaciones
- Manejo robusto de errores
"""

import requests
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import json
import time
import random
from functools import wraps
try:
    from app.metrics import incr
except Exception:
    def incr(*args, **kwargs):
        pass

# Configuración de logging
logger = logging.getLogger(__name__)

# 🆕 BUG #5 FIX: Decorador de reintentos para operaciones críticas
def retry_on_failure(max_attempts: int = 3, backoff_factor: float = 1.5, exceptions: tuple = (Exception,)):
    """
    Decorador para reintentar operaciones fallidas con backoff exponencial.
    
    Problema original: Las operaciones de SaludTools fallaban sin reintentar,
    causando pérdida de agendamientos por errores transitorios de red.
    
    Solución: Implementa patrón de reintentos con espera exponencial entre intentos.
    
    Args:
        max_attempts: Número máximo de intentos (default: 3)
        backoff_factor: Factor de multiplicación para delay entre reintentos (default: 1.5)
                       Delay = backoff_factor ^ (attempt - 1) segundos
        exceptions: Tupla de excepciones a capturar para reintento (default: todas)
    
    Ejemplo:
        Intento 1: falla inmediatamente
        Intento 2: espera 1.5s antes de intentar
        Intento 3: espera 2.25s antes de intentar final
    
    Returns:
        Decorator: Función decoradora que añade lógica de reintentos
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            """Wrapper para funciones asíncronas"""
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = backoff_factor ** (attempt - 1)
                        logger.warning(f"⚠️ {func.__name__} falló (intento {attempt}/{max_attempts}): {e}. Reintentando en {delay:.1f}s...")
                        await asyncio_sleep(delay)
                    else:
                        logger.error(f"❌ {func.__name__} falló después de {max_attempts} intentos: {e}")
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            """Wrapper para funciones síncronas"""
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = backoff_factor ** (attempt - 1)
                        logger.warning(f"⚠️ {func.__name__} falló (intento {attempt}/{max_attempts}): {e}. Reintentando en {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"❌ {func.__name__} falló después de {max_attempts} intentos: {e}")
            raise last_exception
        
        # Detectar si la función es asíncrona o síncrona y aplicar wrapper correspondiente
        import asyncio
        import inspect
        if inspect.iscoroutinefunction(func):
            async def asyncio_sleep(delay):
                await asyncio.sleep(delay)
            return async_wrapper
        else:
            return sync_wrapper
    return decorator

class SaludtoolsAPI:
    """
    Cliente principal para interactuar con Saludtools API.
    
    Gestiona toda la comunicación con el sistema de agendamiento médico,
    incluyendo autenticación, pacientes y citas.
    """
    
    def __init__(self, environment: Optional[str] = None):
        """
        Inicializa el cliente de Saludtools API.

        Args:
            environment: Ambiente objetivo. Valores aceptados (case-insensitive):
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
        # Validar ambiente
        try:
            _ = self._get_base_url()
        except ValueError as e:
            raise ValueError(f"Invalid Saludtools environment '{self.environment}': {e}")

        # Permitir override explícito por variable SALUDTOOLS_BASE_URL
        self.base_url = os.getenv("SALUDTOOLS_BASE_URL") or self._get_base_url()

        # Environment-specific credential handling
        env_suffix = f"_{self.environment.upper()}" if self.environment else ""
        self.api_key = (
            os.getenv(f"SALUDTOOLS_API_KEY{env_suffix}") or
            os.getenv("SALUDTOOLS_API_KEY")
        )
        self.api_secret = (
            os.getenv(f"SALUDTOOLS_API_SECRET{env_suffix}") or
            os.getenv("SALUDTOOLS_API_SECRET")
        )
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        # Documento del paciente (usado para operaciones que lo requieren)
        self.paciente_documento = os.getenv("PACIENTE_DOCUMENTO", "1067883455")  # Default para testing

        if not self.api_key or not self.api_secret:
            logger.warning("Credenciales de Saludtools no configuradas. Usando modo mock.")
            self.mock_mode = True
        else:
            self.mock_mode = False

        # Validar credenciales si no es modo mock
        if not self.mock_mode:
            validation = self.validate_credentials_format()
            if not validation["valid"]:
                error_msg = "Credenciales inválidas: " + "; ".join(validation["errors"])
                raise ValueError(error_msg)
            if validation["warnings"]:
                logger.warning("Advertencias de credenciales: " + "; ".join(validation["warnings"]))
    
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

    def validate_credentials_format(self) -> Dict[str, Any]:
        """
        Valida el formato de las credenciales antes de usarlas

        Returns:
            Dict con validación: valid (bool), errors (list), warnings (list)
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Validar API key
        if not self.api_key:
            result["errors"].append("SALUDTOOLS_API_KEY no está configurada")
            result["valid"] = False
        elif not isinstance(self.api_key, str):
            result["errors"].append("SALUDTOOLS_API_KEY debe ser una cadena de texto")
            result["valid"] = False
        elif len(self.api_key.strip()) == 0:
            result["errors"].append("SALUDTOOLS_API_KEY no puede estar vacía")
            result["valid"] = False
        elif len(self.api_key.strip()) < 10:
            result["warnings"].append("SALUDTOOLS_API_KEY parece muy corta (menos de 10 caracteres)")

        # Validar API secret
        if not self.api_secret:
            result["errors"].append("SALUDTOOLS_API_SECRET no está configurada")
            result["valid"] = False
        elif not isinstance(self.api_secret, str):
            result["errors"].append("SALUDTOOLS_API_SECRET debe ser una cadena de texto")
            result["valid"] = False
        elif len(self.api_secret.strip()) == 0:
            result["errors"].append("SALUDTOOLS_API_SECRET no puede estar vacía")
            result["valid"] = False
        elif len(self.api_secret.strip()) < 10:
            result["warnings"].append("SALUDTOOLS_API_SECRET parece muy corta (menos de 10 caracteres)")

        # Validar formato básico (si parecen UUID o similares)
        import re
        # Permitir Base64 estándar en secrets (incluye +, /, =)
        if self.api_key and not re.match(r'^[a-zA-Z0-9\-_\.]+$', self.api_key.strip()):
            result["warnings"].append("SALUDTOOLS_API_KEY contiene caracteres no estándar")

        # Secret puede ser Base64 - solo advertir si tiene caracteres raros (no +/=)
        if self.api_secret and not re.match(r'^[a-zA-Z0-9\-_\.+=\/]+$', self.api_secret.strip()):
            result["warnings"].append("SALUDTOOLS_API_SECRET contiene caracteres no permitidos")

        return result
    
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

        # Validar credenciales antes de intentar autenticación
        if not self.api_key or not self.api_secret:
            logger.error("Credenciales faltantes: api_key o api_secret no configurados")
            return False

        # Intentar autenticación con credenciales principales
        success = await self._authenticate_with_credentials(self.api_key, self.api_secret)
        if success:
            return True

        # Fallback: intentar con credenciales alternativas si están configuradas
        fallback_key = os.getenv("SALUDTOOLS_API_KEY_FALLBACK")
        fallback_secret = os.getenv("SALUDTOOLS_API_SECRET_FALLBACK")

        if fallback_key and fallback_secret:
            logger.warning("Intentando autenticación con credenciales de fallback")
            success = await self._authenticate_with_credentials(fallback_key, fallback_secret)
            if success:
                logger.info("Autenticación exitosa con credenciales de fallback")
                return True

        # Si todo falla, intentar con endpoints alternativos
        return await self._authenticate_with_fallback_endpoints()

    async def _authenticate_with_credentials(self, api_key: str, api_secret: str) -> bool:
        """Autentica usando credenciales específicas"""
        url = f"{self.base_url}/authenticate/apikey/v1/"
        payload = {"key": api_key, "secret": api_secret}
        max_attempts = int(os.getenv("RETRY_MAX", "3"))
        backoff_base = float(os.getenv("RETRY_BACKOFF_BASE", "0.8"))

        logger.info("Iniciando autenticación con Saludtools (url=%s, max_attempts=%s)", url, max_attempts)

        for attempt in range(1, max_attempts + 1):
            incr('saludtools_auth_attempt')
            try:
                logger.debug("Auth attempt %s/%s: POST %s with payload key=*** secret=***", attempt, max_attempts, url)
                resp = requests.post(url, json=payload, headers=self._get_headers(include_auth=False), timeout=15)

                logger.debug("Auth response status=%s, headers=%s", resp.status_code, dict(resp.headers))

                if resp.status_code >= 500:
                    logger.warning("Auth attempt %s: Server error status=%s", attempt, resp.status_code)
                    raise requests.exceptions.RequestException(f"Server error: Status {resp.status_code}")

                if resp.status_code == 401:
                    logger.error("Auth attempt %s: Credenciales inválidas (401 Unauthorized)", attempt)
                    incr('saludtools_auth_error')
                    return False

                if resp.status_code == 403:
                    logger.error("Auth attempt %s: Acceso denegado (403 Forbidden)", attempt)
                    incr('saludtools_auth_error')
                    return False

                if resp.status_code == 400:
                    logger.error("Auth attempt %s: Solicitud malformada (400 Bad Request)", attempt)
                    incr('saludtools_auth_error')
                    return False

                resp.raise_for_status()

                try:
                    data = resp.json()
                    logger.debug("Auth response body: %s", json.dumps(data, ensure_ascii=False))
                except ValueError as e:
                    logger.error("Auth attempt %s: Respuesta JSON inválida: %s", attempt, e)
                    incr('saludtools_auth_error')
                    return False

                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                expires_in = data.get("expires_in", 86400)

                if not self.access_token:
                    logger.error("Auth attempt %s: access_token no encontrado en respuesta", attempt)
                    incr('saludtools_auth_error')
                    return False

                self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                incr('saludtools_auth_success')
                logger.info("Autenticación exitosa (attempt=%s) expira en %s segundos", attempt, expires_in)
                return True

            except requests.exceptions.Timeout:
                logger.warning("Auth attempt %s: Timeout después de 15s", attempt)
                if attempt == max_attempts:
                    logger.error("Autenticación fallida: Timeout tras %s intentos", max_attempts)
                    incr('saludtools_auth_error')
                    return False
                wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                logger.info("Reintentando auth en %.2fs", wait)
                time.sleep(wait)

            except requests.exceptions.ConnectionError as e:
                logger.warning("Auth attempt %s: Error de conexión: %s", attempt, e)
                if attempt == max_attempts:
                    logger.error("Autenticación fallida: Error de conexión tras %s intentos", max_attempts)
                    incr('saludtools_auth_error')
                    return False
                wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                logger.info("Reintentando auth en %.2fs", wait)
                time.sleep(wait)

            except requests.exceptions.RequestException as e:
                logger.warning("Auth attempt %s: Error de request: %s", attempt, e)
                if attempt == max_attempts:
                    logger.error("Autenticación fallida tras %s intentos: %s", max_attempts, e)
                    incr('saludtools_auth_error')
                    return False
                wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                logger.info("Reintentando auth en %.2fs", wait)
                time.sleep(wait)

        return False

    async def _authenticate_with_fallback_endpoints(self) -> bool:
        """Intenta autenticación con endpoints alternativos"""
        fallback_endpoints = [
            "/authenticate/apikey/",  # Sin v1
            "/auth/apikey/v1/",       # Endpoint alternativo
            "/oauth/token"            # OAuth endpoint (si aplica)
        ]

        for endpoint in fallback_endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                payload = {"key": self.api_key, "secret": self.api_secret}

                logger.info("Intentando autenticación con endpoint alternativo: %s", endpoint)
                resp = requests.post(url, json=payload, headers=self._get_headers(include_auth=False), timeout=10)

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        self.access_token = data.get("access_token")
                        if self.access_token:
                            self.token_expires_at = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 86400))
                            logger.info("Autenticación exitosa con endpoint alternativo: %s", endpoint)
                            return True
                    except ValueError:
                        pass

                logger.debug("Endpoint alternativo %s falló con status %s", endpoint, resp.status_code)

            except Exception as e:
                logger.debug("Error con endpoint alternativo %s: %s", endpoint, e)

        logger.error("Todos los endpoints de autenticación fallaron")
        return False
    
    async def ensure_authenticated(self) -> bool:
        """Asegura que tenemos un token válido"""
        if self.access_token and not self._is_token_expired():
            return True
        
        return await self.authenticate()
    
    async def refresh_access_token(self) -> bool:
        """Refresca el access_token usando refresh_token"""
        if self.mock_mode:
            return await self.authenticate()

        if not self.refresh_token:
            logger.warning("No hay refresh_token disponible, re-autenticando...")
            return await self.authenticate()

        # Intentar refresh token
        success = await self._refresh_with_token()
        if success:
            return True

        # Fallback: re-autenticar si refresh falla
        logger.warning("Refresh token falló, intentando re-autenticación...")
        return await self.authenticate()

    async def _refresh_with_token(self) -> bool:
        """Intenta refrescar el token usando el refresh_token"""
        url = f"{self.base_url}/authenticate/refresh/v1/"
        payload = {"refresh_token": self.refresh_token}
        max_attempts = int(os.getenv("RETRY_MAX", "2"))  # Menos intentos para refresh

        logger.info("Intentando refresh token en %s", url)

        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(url, json=payload, headers=self._get_headers(include_auth=False), timeout=10)

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        new_access_token = data.get("access_token")
                        new_refresh_token = data.get("refresh_token")
                        expires_in = data.get("expires_in", 86400)

                        if new_access_token:
                            self.access_token = new_access_token
                            if new_refresh_token:
                                self.refresh_token = new_refresh_token
                            self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                            logger.info("Refresh token exitoso, expira en %s segundos", expires_in)
                            return True
                        else:
                            logger.error("Refresh response sin access_token")
                            return False
                    except ValueError as e:
                        logger.error("Respuesta JSON inválida en refresh: %s", e)
                        return False

                elif resp.status_code == 401:
                    logger.warning("Refresh token inválido o expirado")
                    return False

                else:
                    logger.warning("Refresh falló con status %s: %s", resp.status_code, resp.text[:200])

            except Exception as e:
                logger.warning("Error en refresh attempt %s: %s", attempt, e)

        return False

    async def test_connectivity_and_credentials(self) -> Dict[str, Any]:
        """
        Prueba la conectividad con la API y la validez de las credenciales

        Returns:
            Dict con resultados del test:
            - connectivity: bool - True si se puede conectar al endpoint base
            - credentials: bool - True si las credenciales son válidas
            - authentication: bool - True si la autenticación completa funciona
            - errors: List[str] - Lista de errores encontrados
            - credential_validation: Dict - Resultados de validación de formato
        """
        results = {
            "connectivity": False,
            "credentials": False,
            "authentication": False,
            "errors": [],
            "credential_validation": {}
        }

        if self.mock_mode:
            results["connectivity"] = True
            results["credentials"] = True
            results["authentication"] = True
            results["credential_validation"] = {"valid": True, "errors": [], "warnings": []}
            return results

        # Test 0: Validación de formato de credenciales
        validation = self.validate_credentials_format()
        results["credential_validation"] = validation
        if not validation["valid"]:
            results["errors"].extend(validation["errors"])
            logger.error("Formato de credenciales inválido: %s", "; ".join(validation["errors"]))
            return results

        # Test 1: Conectividad básica
        try:
            logger.debug("Testing basic connectivity to %s", self.base_url)
            resp = requests.get(self.base_url, timeout=10)
            results["connectivity"] = True
            logger.debug("Basic connectivity test passed")
        except requests.exceptions.RequestException as e:
            results["errors"].append(f"Connectivity test failed: {e}")
            logger.warning("Connectivity test failed: %s", e)
            return results

        # Test 2: Validación de credenciales (autenticación)
        try:
            logger.debug("Testing credential validation via authentication")
            auth_success = await self.authenticate()
            if auth_success:
                results["credentials"] = True
                results["authentication"] = True
                logger.debug("Credential and authentication tests passed")
            else:
                results["errors"].append("Authentication failed - check credentials")
                logger.warning("Authentication test failed")
        except Exception as e:
            results["errors"].append(f"Authentication test error: {e}")
            logger.error("Authentication test error: %s", e)

        return results
    
    # PACIENTES
    def _build_event_payload(self, event_type: str, action_type: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Crea el payload estándar (eventType/actionType/body) sin campos extra no soportados."""
        return {"eventType": event_type, "actionType": action_type, "body": body}

    async def _post_event(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """POST con reintentos exponenciales simples.

        Reintenta ante errores de red, timeouts, 5xx y 429.
        Maneja específicamente errores 412 con credenciales rotadas.
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

                # Manejo especial para 412: intentar rotación de credenciales
                if status == 412:
                    error_details = self._parse_412_error(resp.text)
                    logger.warning("Error 412 detectado: %s", error_details.get("message", "Sin detalles"))

                    # Intentar rotación de credenciales si está habilitado
                    if os.getenv("SALUDTOOLS_ENABLE_CREDENTIAL_ROTATION", "").lower() in {"1","true","yes","on"}:
                        if await self._rotate_credentials_and_retry(payload):
                            # Si la rotación funcionó, retornar el resultado de la nueva llamada
                            continue

                    # Si no hay rotación o falló, manejar como error normal
                    content_snippet = resp.text[:800]
                    logger.error("Error 412 Saludtools eventType=%s actionType=%s body=%s details=%s",
                               payload.get("eventType"), payload.get("actionType"), content_snippet, error_details)
                    incr('saludtools_412_error')
                    return {"error": "412_PRECONDITION_FAILED", "message": error_details.get("message", "Precondition Failed"), "code": 412}

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

    def _parse_412_error(self, response_text: str) -> Dict[str, Any]:
        """Parsea la respuesta de error 412 para extraer información útil"""
        try:
            data = json.loads(response_text)
            return {
                "message": data.get("message", "Precondition Failed"),
                "code": data.get("code", 412),
                "details": data.get("details", {})
            }
        except (json.JSONDecodeError, TypeError):
            return {"message": response_text[:200] if response_text else "Precondition Failed"}

    async def _rotate_credentials_and_retry(self, payload: Dict[str, Any]) -> bool:
        """Intenta rotar credenciales y reintentar la operación"""
        logger.info("Intentando rotación de credenciales para 412")

        # Lista de credenciales alternativas para probar
        credential_sets = []

        # Credenciales principales
        if self.api_key and self.api_secret:
            credential_sets.append((self.api_key, self.api_secret))

        # Credenciales de fallback
        fallback_key = os.getenv("SALUDTOOLS_API_KEY_FALLBACK")
        fallback_secret = os.getenv("SALUDTOOLS_API_SECRET_FALLBACK")
        if fallback_key and fallback_secret:
            credential_sets.append((fallback_key, fallback_secret))

        # Credenciales específicas del ambiente
        env_suffix = f"_{self.environment.upper()}" if self.environment else ""
        alt_key = os.getenv(f"SALUDTOOLS_API_KEY_ALT{env_suffix}") or os.getenv("SALUDTOOLS_API_KEY_ALT")
        alt_secret = os.getenv(f"SALUDTOOLS_API_SECRET_ALT{env_suffix}") or os.getenv("SALUDTOOLS_API_SECRET_ALT")
        if alt_key and alt_secret:
            credential_sets.append((alt_key, alt_secret))

        # Probar cada conjunto de credenciales
        for i, (test_key, test_secret) in enumerate(credential_sets):
            if i == 0:  # Saltar las credenciales actuales si ya se probaron
                continue

            logger.debug("Probando credenciales alternativas %d", i)
            success = await self._authenticate_with_credentials(test_key, test_secret)
            if success:
                logger.info("Rotación exitosa con credenciales %d, reintentando operación", i)
                # Reintentar la operación original con las nuevas credenciales
                result = await self._post_event(payload)
                if result:
                    return True

        logger.warning("Rotación de credenciales falló")
        return False

    @retry_on_failure(max_attempts=3, backoff_factor=1.5, exceptions=(requests.RequestException, ConnectionError))
    async def buscar_paciente_por_documento(self, documento: str, tipo_documento: int = 1) -> Optional[Dict]:
        """🔄 BUG #5 FIX: Lee (READ) un paciente con reintentos automáticos.

        Docs: /patientread -> actionType READ, eventType PATIENT
        Body requerido: { "documentType": <id>, "documentNumber": "..." }
        Nota: La API usa "documentType" (sin "Id" al final)
        """
        if not await self.ensure_authenticated():
            return None

        if self.mock_mode:
            return {
                "id": 12345,
                "firstName": "Juan",
                "firstLastName": "Pérez",
                "documentTypeId": tipo_documento,
                "documentNumber": documento,
                "phone": "3001234567",
                "email": "juan.perez@email.com"
            }

        # Formato correcto según documentación SaludTools: documentType (sin "Id")
        payload = self._build_event_payload("PATIENT", "READ", {"documentType": tipo_documento, "documentNumber": documento})
        data = await self._post_event(payload)
        if not data:
            return None
        body = data.get("body")
        if not body:
            return None
        return body
    
    @retry_on_failure(max_attempts=3, backoff_factor=2.0, exceptions=(requests.RequestException, ConnectionError))
    async def crear_paciente(self, datos_paciente: Dict) -> Optional[Dict]:
        """🔄 BUG #5 FIX: Crea un paciente con reintentos automáticos.

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
        
        # ✅ Normalizar campos de documento según documentación SaludTools
        # La API espera "documentType" (sin "Id") según patrón consistente
        if "documentType" not in body and "documentTypeId" in body:
            body["documentType"] = body.pop("documentTypeId")
        if "documentNumber" not in body and "document" in body:
            body["documentNumber"] = body.pop("document")

        # Filtrar solo campos potencialmente soportados (evitar ruido)
        allowed = {"firstName","secondName","firstLastName","secondLastName","documentType","documentNumber","gender","birthDate","phone","cellPhone","email","habeasData"}
        body = {k:v for k,v in body.items() if k in allowed}

        # Requeridos mínimos (usando documentType según documentación)
        required = ["firstName","firstLastName","documentType","documentNumber"]
        faltantes = [r for r in required if r not in body or body[r] in (None,"")]
        if faltantes:
            logger.error(f"Faltan campos requeridos para crear paciente: {faltantes}")
            return None

        try:
            payload = self._build_event_payload("PATIENT", "CREATE", body)
            data = await self._post_event(payload)
            if not data:
                return None
            return data.get("body") or data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creando paciente: {e}")
            return None
    
    # PROFESIONALES / DOCTORES
    async def buscar_profesional_por_nombre(self, nombre: str) -> List[Dict]:
        """
        Busca profesionales (doctores/fisioterapeutas) por nombre
        
        Args:
            nombre: Nombre del profesional a buscar
        
        Returns:
            Lista de profesionales que coinciden
        
        Nota: Este metodo es un placeholder para futuras integraciones.
        Actualmente retorna lista vacia ya que SaludTools no tiene endpoint
        publico de busqueda de profesionales.
        """
        # TODO: Implementar cuando SaludTools provea endpoint de busqueda
        logger.info(f"Busqueda de profesional: {nombre}")
        
        if self.mock_mode:
            # Retornar datos mock para testing
            return [{
                "id": 1,
                "firstName": "Miguel",
                "firstLastName": "Rodriguez",
                "documentNumber": "1234567890",
                "especialidad": "Fisioterapia"
            }]
        
        # Por ahora retornar vacio - esto no rompe funcionalidad critica
        # El sistema puede asignar fisioterapeutas automaticamente
        return []
    
    # CITAS
    async def listar_citas_paciente(self, documento: str = None, tipo_documento: int = 1) -> List[Dict]:
        """
        Lista citas del paciente (alias de buscar_citas_por_documento)
        
        Args:
            documento: Documento del paciente (opcional, usa el configurado)
            tipo_documento: Tipo de documento (default: 1 - CC)
        
        Returns:
            Lista de citas del paciente
        """
        # Si no se proporciona documento, usar el del paciente configurado
        if not documento:
            documento = self.paciente_documento
        
        return await self.buscar_citas_por_documento(documento, tipo_documento)
    
    @retry_on_failure(max_attempts=3, backoff_factor=1.5, exceptions=(requests.RequestException, ConnectionError))
    async def buscar_citas_por_documento(self, documento: str, tipo_documento: int = 1) -> List[Dict]:
        """🔄 BUG #5 FIX: Filtra citas por documento de paciente con reintentos automáticos.

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
            data = await self._post_event(payload)
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

    @retry_on_failure(max_attempts=3, backoff_factor=2.0, exceptions=(requests.RequestException, ConnectionError, TimeoutError))
    async def crear_cita(self, datos_cita: Dict) -> Optional[Dict]:
        """
        🔄 BUG #5 FIX: Crea una nueva cita en Saludtools con reintentos automáticos
        
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
            
            # ✅ CAMPOS DE DOCUMENTO YA TIENEN EL FORMATO CORRECTO
            # Según docs de SaludTools: "patientDocumentType" (sin "Id")
            # NO convertir - la documentación oficial usa estos nombres exactos
            
            # Formato de fecha requerido: 'YYYY-MM-DD HH:mm'
            if isinstance(normalizada.get("startAppointment"), str):
                normalizada["startAppointment"] = self._fmt_datetime(normalizada["startAppointment"])
            if isinstance(normalizada.get("endAppointment"), str):
                normalizada["endAppointment"] = self._fmt_datetime(normalizada["endAppointment"])

            # Campos requeridos según docs oficiales de SaludTools
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

            # Simplificar payload: la doc oficial solo exige los campos básicos. Quitamos extras potencialmente inválidos.
            for extr in ["appointmentTypeName","appointmentTypeId","duration","clinicId"]:
                if extr in normalizada:
                    normalizada.pop(extr, None)

            base_permitidos = {"startAppointment","endAppointment","patientDocumentType","patientDocumentNumber","doctorDocumentType","doctorDocumentNumber","modality","stateAppointment","notificationState","appointmentType","clinic","comment"}

            def _mk(src: Dict) -> Dict:
                return {k: src[k] for k in base_permitidos if k in src and src[k] not in (None, "")}

            variantes: list[tuple[str, Dict]] = []
            variantes.append(("original", _mk(normalizada)))
            fb_type = os.getenv("SALUDTOOLS_APPOINTMENT_TYPE_FALLBACK", "CITADEPRUEBA")
            if normalizada.get("appointmentType") != fb_type:
                alt = dict(normalizada); alt["appointmentType"] = fb_type; variantes.append(("fallback_type", _mk(alt)))
            fb_doc = os.getenv("SALUDTOOLS_FALLBACK_DOCTOR_DOC", "11111")
            if normalizada.get("doctorDocumentNumber") != fb_doc:
                alt2 = dict(normalizada); alt2["doctorDocumentNumber"] = fb_doc; variantes.append(("fallback_doctor", _mk(alt2)))

            data = None
            last_variant = None
            for nombre_var, body_final in variantes:
                payload = self._build_event_payload("APPOINTMENT", "CREATE", body_final)
                if debug_on:
                    logger.info("[DEBUG] Intento crear cita variante=%s body=%s", nombre_var, body_final)
                data = await self._post_event(payload)
                last_variant = nombre_var
                if not data:
                    continue
                code_val = None
                try:
                    code_val = int(data.get('code')) if isinstance(data, dict) and data.get('code') else None
                except Exception:
                    pass
                if code_val == 412:
                    logger.warning("[saludtools] 412 variante=%s msg=%s", nombre_var, data.get('message'))
                    continue
                break
            if debug_on and data is not None:
                logger.info("[DEBUG] Resultado crear cita variante_final=%s -> %s", last_variant, data)
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
                    incr('citas_412')
                    logger.error("Diagnóstico 412 crear cita (todas variantes) snapshot=%s response=%s", debug_snapshot, data)
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
    
    @retry_on_failure(max_attempts=3, backoff_factor=2.0, exceptions=(requests.RequestException, ConnectionError))
    async def actualizar_cita(self, id_cita: int, datos_cita: Dict) -> Optional[Dict]:
        """
        🔄 BUG #5 FIX: Actualiza una cita existente con reintentos automáticos
        
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
            base = dict(datos_cita)
            # Normalizar alias
            if "startDate" in base and "startAppointment" not in base:
                base["startAppointment"] = base.pop("startDate")
            if "endDate" in base and "endAppointment" not in base:
                base["endAppointment"] = base.pop("endDate")
            if "appointmentState" in base and "stateAppointment" not in base:
                base["stateAppointment"] = base.pop("appointmentState")
            # Formato fechas
            if isinstance(base.get("startAppointment"), str):
                base["startAppointment"] = self._fmt_datetime(base["startAppointment"])
            if isinstance(base.get("endAppointment"), str):
                base["endAppointment"] = self._fmt_datetime(base["endAppointment"])

            # Completar mínimos desde entorno / deducidos
            if 'doctorDocumentType' not in base and os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_TYPE'):
                base['doctorDocumentType'] = int(os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_TYPE'))
            if 'doctorDocumentNumber' not in base and os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER'):
                base['doctorDocumentNumber'] = os.getenv('SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER')
            if 'clinic' not in base and os.getenv('SALUDTOOLS_CLINIC_ID'):
                base['clinic'] = int(os.getenv('SALUDTOOLS_CLINIC_ID'))
            if 'appointmentType' not in base and os.getenv('SALUDTOOLS_DEFAULT_APPOINTMENT_TYPE'):
                base['appointmentType'] = os.getenv('SALUDTOOLS_DEFAULT_APPOINTMENT_TYPE')
            # Paciente obligatorio según mensaje de error del API
            if 'patientDocumentType' not in base and 'patientDocumentNumber' in base and os.getenv('SALUDTOOLS_DEFAULT_PATIENT_DOC_TYPE'):
                # Solo usar default type si tenemos número en el payload
                base['patientDocumentType'] = int(os.getenv('SALUDTOOLS_DEFAULT_PATIENT_DOC_TYPE'))
            if 'patientDocumentNumber' not in base and 'patientDocumentType' in base and os.getenv('SALUDTOOLS_DEFAULT_PATIENT_DOC_NUMBER'):
                base['patientDocumentNumber'] = os.getenv('SALUDTOOLS_DEFAULT_PATIENT_DOC_NUMBER')
            # Si faltan ambos campos de paciente abortamos antes de enviar (evita 412 redundante)
            if 'patientDocumentType' not in base or 'patientDocumentNumber' not in base:
                logger.error("[update_cita] Faltan patientDocumentType/patientDocumentNumber para actualizar cita %s", id_cita)
                return {"error": "MISSING_PATIENT_ID", "message": "Faltan identificadores de paciente para UPDATE"}
            # Estado/modalidad opcionales pero a veces requeridos
            if 'modality' not in base:
                base['modality'] = os.getenv('SALUDTOOLS_DEFAULT_MODALITY', 'CONVENTIONAL')
            if 'stateAppointment' not in base:
                base['stateAppointment'] = 'PENDING'
            # Eliminar campos potencialmente conflictivos
            for extr in ["appointmentTypeName","appointmentTypeId","duration","clinicId"]:
                base.pop(extr, None)
            base['id'] = id_cita

            permitidos = {"id","startAppointment","endAppointment","patientDocumentType","patientDocumentNumber","doctorDocumentType","doctorDocumentNumber","modality","stateAppointment","appointmentType","clinic","comment"}
            minimal = {k: base[k] for k in permitidos if k in base and base[k] not in (None,"")}

            # Variantes (similar a crear): original y cambio de appointmentType si existe fallback
            variantes: list[tuple[str, Dict]] = [("original", minimal)]
            fb_type = os.getenv("SALUDTOOLS_APPOINTMENT_TYPE_FALLBACK")
            if fb_type and minimal.get("appointmentType") != fb_type:
                alt = dict(minimal); alt['appointmentType'] = fb_type; variantes.append(("fallback_type", alt))
            fb_doc = os.getenv("SALUDTOOLS_FALLBACK_DOCTOR_DOC")
            if fb_doc and minimal.get("doctorDocumentNumber") != fb_doc:
                alt2 = dict(minimal); alt2['doctorDocumentNumber'] = fb_doc; variantes.append(("fallback_doctor", alt2))

            debug_on = self._debug_enabled()
            data = None
            last_variant = None
            for nombre, cuerpo in variantes:
                payload = self._build_event_payload("APPOINTMENT", "UPDATE", cuerpo)
                if debug_on:
                    logger.info("[DEBUG] Intento actualizar cita variante=%s body=%s", nombre, cuerpo)
                data = await self._post_event(payload)
                last_variant = nombre
                if not data:
                    continue
                try:
                    code_val = int(data.get('code')) if isinstance(data, dict) and data.get('code') else None
                except Exception:
                    code_val = None
                if code_val == 412:
                    logger.warning("[saludtools] 412 update variante=%s msg=%s", nombre, data.get('message'))
                    continue
                break
            if debug_on and data is not None:
                logger.info("[DEBUG] Resultado actualizar cita variante_final=%s -> %s", last_variant, data)
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error actualizando cita {id_cita}: {e}")
            return None
    
    @retry_on_failure(max_attempts=3, backoff_factor=1.5, exceptions=(requests.RequestException, ConnectionError))
    async def cancelar_cita(self, id_cita: int) -> bool:
        """
        🔄 BUG #5 FIX: Cancela una cita con reintentos automáticos
        
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
            data = await self._post_event(payload)
            if data is None:
                return False
            logger.info(f"Cita {id_cita} cancelada en Saludtools. Respuesta: {data}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error cancelando cita {id_cita}: {e}")
            return False
    
    async def obtener_cita(self, id_cita: int) -> Optional[Dict]:
        """
        Obtiene los detalles de una cita específica por su ID
        
        Args:
            id_cita: ID de la cita a buscar
            
        Returns:
            Diccionario con los datos de la cita o None si no existe
        """
        if not await self.ensure_authenticated():
            logger.warning("No se pudo autenticar para obtener cita")
            return None
        
        if self.mock_mode:
            return {
                "id": id_cita,
                "patientDocumentType": 1,
                "patientDocumentNumber": "1234567890",
                "doctorDocumentType": 1,
                "doctorDocumentNumber": "11111",
                "startDate": datetime.now().isoformat(),
                "endDate": (datetime.now() + timedelta(hours=1)).isoformat(),
                "appointmentType": "Fisioterapia",
                "appointmentState": "PENDING",
                "modality": "CONVENTIONAL",
                "clinic": 0,
                "comment": "Cita de prueba"
            }
        
        try:
            url = f"{self._get_base_url()}/appointment/{id_cita}"
            headers = self._get_headers()
            
            logger.info(f"Obteniendo cita #{id_cita} de SaludTools")
            
            response = requests.get(
                url,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                cita = response.json()
                logger.info(f"✅ Cita #{id_cita} encontrada")
                incr("saludtools.get_appointment.success")
                return cita
            elif response.status_code == 404:
                logger.warning(f"⚠️ Cita #{id_cita} no encontrada")
                incr("saludtools.get_appointment.not_found")
                return None
            else:
                logger.error(f"❌ Error obteniendo cita #{id_cita}: {response.status_code} - {response.text}")
                incr("saludtools.get_appointment.error", tags={"status_code": str(response.status_code)})
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Timeout obteniendo cita #{id_cita}")
            incr("saludtools.get_appointment.timeout")
            return None
        except Exception as e:
            logger.error(f"❌ Error obteniendo cita #{id_cita}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            incr("saludtools.get_appointment.error", tags={"error_type": "exception"})
            return None

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
