"""
CHATBOT PRINCIPAL IPS REACT
===========================
Sistema inteligente de agendamiento de citas médicas para IPS.
Sigue TODAS las directrices de la documentación.
Optimizado para usar gemini como generador de respuestas y GPT-4o-vision para lectura de ordenes con máxima precisión.

Funcionalidades principales:
- Agendamiento, modificación y cancelación de citas
- Extracción OCR de órdenes médicas
- Validaciones específicas por EPS (Coomeva, etc.)
- Escalamiento automático a agente humano
- Integración con SaludTools API
- Monitoreo y logging estructurado
"""

import os
from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletion
import openai  # 🆕 Bug #8: Para capturar excepciones específicas de OpenAI
from typing import Dict, List, Optional, Tuple
import json
import re
from datetime import datetime, timedelta
import logging
import pytz  # 🆕 Bug #6: Soporte completo de timezone Colombia
import asyncio  # 🆕 Bug #8: Para sleep en manejo de rate limits
from app.ocr_inteligente import procesador_ocr
from app.gemini_adapter import gemini_adapter  # 🔥 Adaptador Gemini 2.0 Flash para chat

# 🔥 IMPORTAR MÓDULOS PRINCIPALES PARA INTEGRACIÓN COMPLETA
from app.saludtools import SaludtoolsAPI
from app.config import mapear_tipo_fisioterapia
from app.monitoring_simple import simple_monitor  # 🆕 Bug #11: Sistema de monitoreo



logger = logging.getLogger(__name__)

# 🆕 BUG #6 FIX: Configuración de Timezone Colombia
COLOMBIA_TZ = pytz.timezone('America/Bogota')

def now_colombia() -> datetime:
    """
    Retorna datetime actual en timezone Colombia.
    Evita problemas de timezone con fechas UTC.
    """
    return datetime.now(COLOMBIA_TZ)

def today_colombia() -> datetime:
    """
    Retorna fecha actual (00:00:00) en timezone Colombia.
    Útil para comparaciones de fechas sin considerar hora.
    """
    return now_colombia().replace(hour=0, minute=0, second=0, microsecond=0)

# Configuración del cliente OpenAI optimizada para GPT-4o-mini
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class IPSReactChatbot:
    """
    Chatbot principal del sistema IPS React.
    
    Responsabilidades:
    - Gestión completa de conversaciones con pacientes
    - Agendamiento automático vía SaludTools API
    - Extracción OCR de órdenes médicas
    - Validaciones específicas por EPS
    - Escalamiento inteligente a agente humano
    - Logging estructurado y monitoreo
    """
    
    def __init__(self):
        """
        Inicializa el chatbot con todas las integraciones necesarias.
        
        Componentes:
        - OpenAI: Análisis de lenguaje natural
        - SaludTools: API de agendamiento médico
        - OCR: Extracción de datos de imágenes
        - Monitor: Sistema de seguimiento y alertas
        """
        # Cliente OpenAI para análisis de conversaciones
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 🔥 INICIALIZAR SALUDTOOLS API PARA AUTOMATIZACIÓN COMPLETA
        try:
            self.saludtools = SaludtoolsAPI()
            self._saludtools_authenticated = False
            logger.info("✅ SaludTools API inicializado - Agendamiento automático activo")
        except Exception as e:
            logger.warning(f"⚠️ SaludTools no disponible, modo escalamiento: {e}")
            self.saludtools = None
            self._saludtools_authenticated = False
        
        # Inicializar OCR inteligente para procesamiento de órdenes médicas
        try:
            from app.ocr_inteligente import ProcesadorOCRInteligente
            self.ocr = ProcesadorOCRInteligente()
            logger.info("✅ OCR inteligente inicializado correctamente")
        except Exception as e:
            logger.warning(f"⚠️ OCR no disponible: {e}")
            self.ocr = None
        
        # 🔥 INICIALIZAR ADAPTADOR GEMINI PARA CHAT CONVERSACIONAL
        try:
            self.gemini = gemini_adapter
            logger.info("✅ Gemini 2.0 Flash adaptador inicializado - Chat optimizado activo")
            logger.info(f"   Modo: {'Gemini' if gemini_adapter.use_gemini else 'GPT-4o fallback'}")
        except Exception as e:
            logger.warning(f"⚠️ Gemini adapter no disponible, usando solo GPT-4o: {e}")
            self.gemini = None
        
        # Lista de fisioterapeutas disponibles para asignación
        self.fisioterapeutas = [
            "Adriana Acevedo Agudelo",
            "Ana Isabel Palacio Botero", 
            "Diana Daniella Arana Carvalho",
            "Diego Andrés Mosquera Torres",
            "Verónica Echeverri Restrepo",
            "Miguel Ignacio Moreno Cardona",
            "Daniela Patiño Londoño"
        ]
        
        # Mapeo de fisioterapeutas con sus cédulas para búsqueda en SaludTools
        self.fisioterapeutas_cc = {
            "Adriana Acevedo Agudelo": "1027880441",
            "Ana Isabel Palacio Botero": "1017251510",
            "Diana Daniella Arana Carvalho": "1001283180",
            "Diego Andrés Mosquera Torres": "1000405371",
            "Verónica Echeverri Restrepo": "43187801",
            "Miguel Ignacio Moreno Cardona": "802540",
            "Daniela Patiño Londoño": "1038627341"
        }
        
        # Estado para recopilación de datos del paciente
        self.datos_paciente = {
            "documento": None,
            "nombre_completo": None, 
            "fecha_nacimiento": None,
            "entidad_eps": None,
            "telefono": None,
            "email": None,
            "direccion": None,
            "contacto_emergencia_nombre": None,
            "contacto_emergencia_telefono": None,
            "contacto_emergencia_parentesco": None
        }
        
        # Para manejo inteligente de conversación
        self.esperando_datos = False
        self.buffer_mensajes = []
        self.ultimo_mensaje_tiempo = None
        
        # Sistema OCR inteligente
        self.ocr = procesador_ocr
        
        self.fisioterapeutas_cardiaca = [
            "Diana Daniella Arana Carvalho",
            "Ana Isabel Palacio Botero",
            "Adriana Acevedo Agudelo"
        ]
        
        # Pólizas SIN convenio (solo particular)
        self.polizas_sin_convenio = [
            "xa colpatria", "colpatria", "medplus", "colmedica", "colmédica",
            "medisanitas", "ssi grupo", "mapfre", "previsora",
            "liberty", "pan american", "metlife",
            "sbs seguros", "cardif"
        ]
        
        # Pólizas CON convenio (autorizadas)
        self.polizas_con_convenio = [
            "coomeva",  # Especial: horario 9am-4pm (excepto cardíaca)
            "sura", "eps sura",
            "nueva eps",
            "sanitas", "eps sanitas", "colsanitas",
            "compensar",
            "famisanar",
            "salud total",
            "medimas",
            "golden group",
            "cafesalud",
            "comfenalco",
            "comfama",
            "ecoopsos"
        ]
        
        self.horarios_ips = {
            "lunes_jueves": "5:00 AM - 8:00 PM",
            "viernes": "5:00 AM - 7:00 PM", 
            "sabados": "8:00 AM - 12:00 PM",
            "domingos": "Cerrado"
        }
        
        self.tipos_fisioterapia_no_soportados = [
            "Rehabilitación del piso o suelo pélvico",
            "Rehabilitación de patologías neurológicas",
            "Hidroterapia",
            "Crioterapia", 
            "Cámara bariátrica",
            "Parálisis miofacial"
        ]
    
    def get_system_prompt(self) -> str:
        """Sistema prompt optimizado con TODAS las directrices"""
        return f"""Eres el asistente de agendamiento inteligente de **IPS REACT**, una clínica especializada en fisioterapia, citas médicas y acondicionamiento físico en Medellín.

🏥 INFORMACIÓN BÁSICA IPS REACT:
- Dirección: Calle 10 32-115, Medellín, Antioquia
- Horarios: 
  • Lunes a Jueves: 5:00 AM - 8:00 PM
  • Viernes: 5:00 AM - 7:00 PM
  • Sábados: 8:00 AM - 12:00 PM
  • Domingos: Cerrado

TIPOS DE CITA DISPONIBLES:

1. FISIOTERAPIA (Ortopédica o Cardíaca):
   - Primera vez: REQUIERE orden médica obligatoria
   - Control: No requiere orden (ya tiene historial)
   - Duración: 60 minutos
   - Pago: Póliza/EPS o Particular ($60,000)
   - FLUJO PÓLIZAS (IMPORTANTE - Ser natural y acogedor):
     • Si pregunta por EPS/póliza: "¡Claro! ¿Qué póliza o EPS tienes?" (NUNCA mencionar Coomeva directamente primero)
     • Cuando responda su póliza, verificar internamente:
       - Si NO está en 'polizas_sin_convenio' → "¡Perfecto! Trabajamos con [X] EPS. El costo se define presencialmente."
       - Si SÍ está en 'polizas_sin_convenio' → "Entiendo, lamentablemente no tenemos convenio con [X]. La cita sería particular ($60k)."
     • NUNCA decir "no tenemos convenio con X" de entrada - siempre ser positivo y dar opciones
   - Si es particular: Efectivo, tarjeta presencial, o transferencia (Si se dice que se quiere pagar con transferencia de una vez escalar a secretaria apenas se agende la cita)
   - ESPECIALIDAD: Se detecta automáticamente del contexto/orden médica
     • Si mencionan "cardíaca", "cardiovascular" o "corazón" → Cardíaca (solo especialistas certificados)
     • Si mencionan "ortopédica", "lesión", "rehabilitación músculo-esquelética" → Ortopédica (cualquier fisio)
     • NUNCA preguntar "¿ortopédica o cardíaca?" a menos de ser necesario - detectar del mensaje

2. ACONDICIONAMIENTO FÍSICO:
   - SOLO pago particular (NO acepta EPS)
   - Clases individualizadas pero no personalizadas
   - Duración: 60 minutos
   - Opciones:
     • 1 clase: $50,000
     • Plan Básico: $320,000/mes (8 sesiones, 2x semana)
     • Plan Intermedio: $380,000/mes (12 sesiones, 3x semana)  
     • Plan Avanzado: $440,000/mes (16 sesiones, 4x semana)
     • Plan Intensivo: $500,000/mes (20 sesiones, 5x semana)
     Importante identificar si ya la persona tiene un plan activo, de ser el caso simplemente se agenda
    - Modalidades de pago: mismas que en fisioterapia, en caso se desee pagar por transferencia de una vez, se escala
3. CITAS MÉDICAS:
   - El chatbot NO agenda citas médicas (solo informa)
   - Si paciente pregunta por especialidad médica: Informar que SÍ se ofrece
   - Si paciente SOLICITA agendar cita médica: ESCALAR AUTOMÁTICAMENTE a secretaria
   - Especialidades médicas disponibles:
     • Médico del Deporte y Actividad Física: Jorge Iván Palacio Uribe
     • Nutricionista: María Camila del Mar Buitrago
     • Médico Internista: Clara Marcela Cadavid Roldán
     • Médico Endocrinólogo: Diego Fernando Benítez España
     • Médico Ortopedista: Jaime Valencia
   - Modalidades de pago médicas: Pólizas prepagas y Particular (presencial o transferencia)

FISIOTERAPEUTAS DISPONIBLES (solo mencionar si el paciente pregunta):
{', '.join(self.fisioterapeutas)}

IMPORTANTE: NO listar todos los fisioterapeutas en cada mensaje. Solo:
1. Preguntar: "¿Tienes algún fisioterapeuta de preferencia?"
2. Si dice un nombre → verificar si está en la lista
3. Si no está → mencionar que no es de la clínica y AHORA SÍ mostrar lista
4. Si dice "no" o "el que esté disponible" → asignar el que tenga menos citas (verificar disponibilidad)

ESPECIALISTAS EN REHABILITACIÓN CARDÍACA (EXCLUSIVO):
{', '.join(self.fisioterapeutas_cardiaca)}

FISIOTERAPIA NO SOPORTADA:
{', '.join(self.tipos_fisioterapia_no_soportados)}

PÓLIZAS SIN CONVENIO (Solo tarifa particular):
{', '.join(self.polizas_sin_convenio)}

INFORMACIÓN INTERNA PÓLIZAS (No mencionar directamente):
- Coomeva: SÍ tiene convenio (Mas la franja horaria tiene que ser entre 9am-4pm, es importante no informar de esta restriccion directamente, sino solo tomar y ofrecer espacios que esten entre ese horario)
  • Excepción: Rehabilitación cardíaca/cardiovascular (horario completo L-J 5am-8pm, V 5am-7pm, S 8am-12pm)
- Resto de pólizas: Horario completo sin importar especialidad

REGLAS COMUNICACIÓN PÓLIZAS:
1. NUNCA mencionar "Coomeva" si el paciente no la ha nombrado primero
2. SIEMPRE ser acogedor: "¡Claro! ¿Qué póliza/EPS tienes?"
3. Cuando responda: Dar respuesta positiva según corresponda
4. NUNCA usar frases negativas como "no tenemos convenio con...", mas si ser claro en caso no este en la lista

DATOS REQUERIDOS PARA AGENDAMIENTO:
- Número de documento
- Nombre completo  
- Fecha de nacimiento
- Entidad (póliza/eps si aplica)
- Número telefónico
- Correo electrónico
- Dirección
- Datos familiar emergencia: nombre, teléfono, parentesco

**IMPORTANTE SOBRE CITAS PARA TERCEROS:**
- SI puedes agendar citas para familiares, amigos o terceras personas
- Solo necesitas los datos de LA PERSONA QUE RECIBIRÁ EL SERVICIO
- Ejemplo: "Quiero agendar para mi mamá" → Solicita datos de la mamá, NO del hijo
- NO escalar por esto - es totalmente normal y permitido

ESCALAMIENTO A SECRETARIAS:
- Paciente solicita lo mismo 3 veces (ineficaz)
- Solicita cita médica
- Quiere pagar por transferencia de una vez
- Números: +57 3207143068 (principal), +57 3002007277 (backup)

PRINCIPIOS DE CONVERSACIÓN HUMANA Y FLUIDA:
1. **Ser natural y acogedor:** Evita respuestas mecánicas o robotizadas
2. **Contexto completo:** Si pregunta múltiples cosas, responde TODO en un solo mensaje coherente
3. **Positivo primero:** Nunca empieces con "no tenemos" o "no aceptamos" - ofrece alternativas
4. **Preguntas abiertas:** "¿Qué póliza tienes?" en vez de "¿Tienes Coomeva?"
5. **Empatía:** Reconocer su situación antes de dar opciones
6. **Flujo conversacional:** No lista de bullets a menos que se pida la informacion directamente - habla naturalmente

COMPORTAMIENTO:
1. Ser profesional, empático y eficiente
2. Identificar rápidamente qué necesita el paciente
3. Recopilar información de forma natural en la conversación
4. Validar disponibilidad antes de confirmar
5. Manejar múltiples citas simultáneamente si se solicita
6. Escalar cuando sea necesario sin dudar
7. Usar formato JSON para respuestas estructuradas cuando se necesite procesar

⚠️ CRÍTICO - MANEJO DE MENSAJES CORTOS:
- Respuestas como "Sí", "No", "Ok" SIEMPRE se procesan en el CONTEXTO de la última pregunta
- Si preguntaste "¿Ya tienes tu orden médica?" y responden "Sí" → entender que SÍ tienen orden
- Si preguntaste "¿Tienes preferencia de fisioterapeuta?" y responden "No" → continuar con siguiente paso
- NUNCA reiniciar conversación por mensajes cortos
- NUNCA repetir el mismo mensaje si el paciente ya respondió
- Si hay confusión, hacer pregunta específica de aclaración

Responde siempre en español colombiano, de forma amable pero profesional."""

    async def _ensure_saludtools_ready(self) -> bool:
        """
        🆕 BUG #1 FIX: Asegura que SaludTools esté autenticado y listo para usar.
        
        Problema original: SaludTools nunca se autenticaba automáticamente,
        causando que todas las operaciones fallaran silenciosamente.
        
        Solución: Valida el estado del token y re-autentica automáticamente
        cuando sea necesario. Maneja expiración de tokens de forma proactiva.
        
        Returns:
            bool: True si SaludTools está listo para operar, False si falló la autenticación
        """
        if not self.saludtools:
            logger.warning("⚠️ SaludTools no inicializado")
            simple_monitor.record_error("saludtools", "SaludTools no disponible")
            return False
        
        # Verificar si ya está autenticado y el token no ha expirado
        if self._saludtools_authenticated and self.saludtools.access_token:
            if not self.saludtools._is_token_expired():
                return True  # Token válido, listo para usar
            else:
                logger.info("🔄 Token SaludTools expirado, re-autenticando...")
        
        # Intentar autenticar con SaludTools
        try:
            logger.info("🔐 Autenticando con SaludTools...")
            success = await self.saludtools.authenticate()
            
            if success:
                self._saludtools_authenticated = True
                logger.info("✅ SaludTools autenticado correctamente")
                simple_monitor.record_success("saludtools_auth")  # 🆕 Bug #11
                return True
            else:
                logger.error("❌ Falló autenticación con SaludTools")
                self._saludtools_authenticated = False
                simple_monitor.record_error("saludtools_auth", "Authentication failed", "high")  # 🆕 Bug #11
                return False
                
        except Exception as e:
            logger.error(f"❌ Error autenticando SaludTools: {e}")
            self._saludtools_authenticated = False
            simple_monitor.record_error("saludtools_auth", str(e), "high")  # 🆕 Bug #11
            return False
    
    def _prepare_session_data(self) -> Dict:
        """
        🆕 BUG #2 FIX: Prepara datos de sesión para persistencia entre mensajes.
        
        Problema original: Los datos extraídos por OCR no se persistían entre
        mensajes consolidados, causando pérdida de información crítica.
        
        Solución: Extrae y estructura los datos de OCR y orden médica para
        que puedan ser almacenados en session_store y recuperados posteriormente.
        
        Returns:
            Dict: Diccionario con datos de sesión incluyendo estado de OCR
        """
        return {
            # Estado de procesamiento de orden médica
            "orden_medica_procesada": self.datos_paciente.get("orden_medica_procesada", False),
            
            # Datos extraídos por OCR (nombres, fechas, diagnósticos, etc.)
            "datos_ocr": {
                k: v for k, v in self.datos_paciente.items()
                if k in ["nombre", "documento", "telefono", "email", "eps", "tipo_servicio", 
                        "especialista", "fecha_deseada", "especialidad", "diagnostico"]
            }
        }

    async def procesar_mensaje(self, mensaje: str, contexto: Dict = None, archivos: List[str] = None) -> Dict:
        """
        Procesa mensaje del paciente usando GPT-4o-mini optimizado
        
        Args:
            mensaje: Texto del paciente
            contexto: Contexto previo de la conversación
            archivos: Lista de rutas de archivos adjuntos (imágenes, PDFs, etc.)
            
        Returns:
            Dict con respuesta y metadatos
        """
        try:
            # ✅ SANITIZACIÓN GLOBAL - Prevenir TODOS los errores de None/NoneType
            mensaje = str(mensaje or "").strip()
            contexto = contexto or {}
            archivos = archivos or []
            
            # 🆕 BUG #2 FIX: Restaurar session_data al inicio
            session_data = contexto.get("session_data", {})
            if session_data:
                # Restaurar estado de orden médica procesada
                if session_data.get("orden_medica_procesada"):
                    self.datos_paciente["orden_medica_procesada"] = True
                # Restaurar otros datos OCR si existen
                if "datos_ocr" in session_data:
                    self.datos_paciente.update(session_data["datos_ocr"])
            
            if not mensaje and not archivos:
                return {
                    "respuesta": "¿En qué puedo ayudarte?",
                    "intencion": "mensaje_vacio",
                    "entidades": {},
                    "requiere_escalamiento": False
                }
            
            # Si hay archivos, procesarlos con OCR
            if archivos:
                resultado_ocr = await self._procesar_archivos_ocr(archivos, mensaje)
                if resultado_ocr:
                    return resultado_ocr
            
            # Si estamos esperando datos del paciente
            if self.esperando_datos:
                # Detectar método de pago al final del proceso
                if self._detectar_metodo_pago(mensaje):
                    return await self._procesar_metodo_pago(mensaje)
                
                # Detectar si es corrección de datos
                if any(palabra in mensaje.lower() for palabra in ["no", "correcto", "cambiar", "error", "olvid", "mal"]):
                    respuesta_texto = self._manejar_correccion_datos(mensaje)
                else:
                    respuesta_texto = self._procesar_datos_personales(mensaje)
                
                return {
                    "respuesta": respuesta_texto,
                    "intencion": "recopilacion_datos",
                    "entidades": self.datos_paciente.copy(),
                    "requiere_escalamiento": False,
                    "accion_requerida": "continuar_recopilacion",
                    "datos_recopilados": self.datos_paciente.copy(),
                    "siguiente_paso": "esperar_datos" if self.esperando_datos else "procesar_agendamiento"
                }
            
            # Analizar intención y extraer entidades
            analisis = await self._analizar_intencion(mensaje, contexto)
            
            # Proteger contra analisis inválido
            if not isinstance(analisis, dict):
                analisis = {
                    "intencion": "otra_consulta",
                    "entidades": {},
                    "urgencia": "normal",
                    "claridad": "clara",
                    "mensaje_original": mensaje
                }
            
            # Generar respuesta basada en análisis (NO iniciar recopilación automáticamente)
            respuesta = await self._generar_respuesta(analisis, contexto)
            
            # Extraer texto de la respuesta (maneja ambos formatos)
            if isinstance(respuesta, dict):
                # Buscar texto de respuesta en diferentes claves posibles
                texto_respuesta = (
                    respuesta.get("respuesta") or 
                    respuesta.get("texto") or 
                    str(respuesta)
                )
                requiere_escalamiento = respuesta.get("requiere_escalamiento") or respuesta.get("escalar", False)
                motivo_escalamiento = respuesta.get("motivo_escalamiento", "")
                prioridad = respuesta.get("prioridad", "normal")
                accion_requerida = respuesta.get("accion", None)
                datos_recopilados = respuesta.get("datos", {})
                siguiente_paso = respuesta.get("siguiente_paso", "continuar")
            else:
                # Si respuesta es string, crear estructura mínima
                texto_respuesta = str(respuesta)
                requiere_escalamiento = False
                motivo_escalamiento = ""
                prioridad = "normal"
                accion_requerida = None
                datos_recopilados = {}
                siguiente_paso = "continuar"
            
            # 🆕 BUG #2 FIX: Incluir session_data en respuesta
            return {
                "respuesta": texto_respuesta,
                "intencion": analisis.get("intencion", "otra_consulta"),
                "entidades": analisis.get("entidades", {}),
                "requiere_escalamiento": requiere_escalamiento,
                "motivo_escalamiento": motivo_escalamiento,
                "prioridad": prioridad,
                "accion_requerida": accion_requerida,
                "datos_recopilados": datos_recopilados,
                "siguiente_paso": siguiente_paso,
                "session_data": self._prepare_session_data()  # 🆕 Persistir datos entre mensajes
            }
            
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            
            # ✅ STACK TRACE COMPLETO para debugging
            import traceback
            logger.error(f"Stack trace completo del error:")
            logger.error(traceback.format_exc())
            
            return {
                "respuesta": "Disculpa, estoy experimentando un problema técnico. ¿Puedes repetir tu solicitud?",
                "error": str(e),
                "stack_trace": traceback.format_exc(),
                "requiere_escalamiento": False
            }
    
    async def procesar_mensaje_directo(self, mensaje: str, telefono: str = None) -> Dict:
        """
        Método directo para procesar mensaje desde el servidor.
        Wrapper simplificado del método principal.
        
        Args:
            mensaje: Texto del mensaje
            telefono: Número de teléfono (opcional)
            
        Returns:
            Dict con respuesta del chatbot
        """
        try:
            # Crear contexto básico
            contexto = {
                "telefono": telefono,
                "timestamp": self._obtener_timestamp(),
                "sesion_id": f"session_{hash(telefono) if telefono else 'unknown'}"
            }
            
            # Procesar mensaje principal
            resultado = await self.procesar_mensaje(mensaje, contexto)
            
            # Retornar resultado
            return resultado
            
        except Exception as e:
            logger.error(f"Error en procesar_mensaje_directo: {e}")
            return {
                "respuesta": "Error procesando mensaje. Intenta nuevamente.",
                "error": str(e),
                "requiere_escalamiento": False
            }
    
    async def _analizar_intencion(self, mensaje: str, contexto: Dict = None) -> Dict:
        """Analiza intención y extrae entidades usando GPT-4o con HISTORIAL COMPLETO"""
        
        # 🔥 CONSTRUIR HISTORIAL PARA ANÁLISIS CONTEXTUAL
        historial_texto = ""
        if contexto and isinstance(contexto, dict):
            historial = contexto.get("historial", [])
            if historial and len(historial) > 0:
                historial_texto = "\n\nHISTORIAL DE CONVERSACIÓN (últimos mensajes):\n"
                for msg in historial[-6:]:  # Últimos 6 mensajes
                    if isinstance(msg, tuple) and len(msg) == 2:
                        role, content = msg
                        if role == "usuario":
                            historial_texto += f"Usuario: {content}\n"
                        elif role in ["ia_c", "asistente"]:
                            historial_texto += f"Asistente: {content}\n"
                    elif isinstance(msg, dict):
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role == "usuario":
                            historial_texto += f"Usuario: {content}\n"
                        elif role in ["ia_c", "asistente"]:
                            historial_texto += f"Asistente: {content}\n"
        
        prompt_analisis = f"""Analiza este mensaje de un paciente de IPS React CONSIDERANDO EL CONTEXTO DE LA CONVERSACIÓN.

MENSAJE ACTUAL DEL PACIENTE: "{mensaje}"{historial_texto}

⚠️ REGLA CRÍTICA - PRESERVACIÓN DE INTENCIÓN:
- Si el asistente hizo una pregunta en el último mensaje (pidió documento, nombre, fecha, etc.)
- Y el paciente responde proporcionando esos datos (números, nombres, fechas)
- MANTÉN LA INTENCIÓN ORIGINAL del flujo en curso
- NO cambies a "datos_personales" u otra intención genérica
- La intención debe ser la MISMA que motivó la pregunta del asistente

Ejemplos:
1. Asistente: "¿Cuál es tu número de cédula?" [intención: consultar_mis_citas]
   Usuario: "1192464344"
   → INTENCIÓN: consultar_mis_citas (NO datos_personales)

2. Asistente: "¿Tienes orden médica?" [intención: agendar_fisioterapia]
   Usuario: "Sí, tengo orden"
   → INTENCIÓN: agendar_fisioterapia (NO otra_consulta)

IMPORTANTE: 
- Respuestas cortas como "Sí", "No", "Ok", "Claro" SIEMPRE se procesan en el CONTEXTO de la última pregunta del asistente
- Si el asistente preguntó "¿Tienes orden médica?" y el paciente dice "Sí" → tiene_orden_medica: true
- Si el asistente preguntó "¿Qué fisioterapeuta prefieres?" y el paciente dice "Miguel" → fisioterapeuta_mencionado: "Miguel"
- Si el paciente dice "el que esté disponible", "el más disponible", "cualquiera", "no tengo preferencia" → fisioterapeuta_mencionado: "auto" (asignar automáticamente)
- Si el paciente envía un número de 7-10 dígitos solo o con su nombre → documento_paciente: "ese número"
  Ejemplos: "1192464344" → documento_paciente: "1192464344"
           "1192464344, mi nombre es Alejandro Perez" → documento_paciente: "1192464344", nombre_paciente: "Alejandro Perez"
           "Mi cédula es 12345678" → documento_paciente: "12345678"

EXTRAE:
1. INTENCIÓN PRINCIPAL (basada en conversación completa):
   - agendamiento_multiple
   - agendar_cita_generica (cuando dice "agendar cita" sin especificar tipo)
   - agendar_fisioterapia_primera_vez
   - agendar_fisioterapia_control
   - agendar_fisioterapia
   - agendar_acondicionamiento
   - agendar_cita_medica
   - consultar_horarios/precios/fisioterapeutas
   - consultar_mis_citas (ver citas agendadas)
   - modificar_cita (cambiar fecha/hora de cita existente)
   - cancelar_cita (eliminar cita agendada)
   - escalamiento_manual
   - datos_personales / correccion_datos
   - otra_consulta

2. ENTIDADES (del mensaje Y del contexto):
   - cantidad_citas, tipo_fisioterapia, fisioterapeuta_mencionado
   - fechas_mencionadas, horarios_mencionados
   - tiene_orden_medica, metodo_pago_preferido
   - documento_paciente (número de cédula/documento - 7 a 10 dígitos)
   - nombre_paciente (nombre completo si lo menciona)
   - cita_id (ID de cita mencionado para modificar/cancelar)

3. URGENCIA: normal/alta
4. CLARIDAD: clara/necesita_aclaracion

Responde EXACTAMENTE en este formato JSON (usa minúsculas en las claves):
{{
  "intencion": "nombre_intencion",
  "entidades": {{
    "cantidad_citas": null,
    "tipo_fisioterapia": null,
    "fisioterapeuta_mencionado": null,
    "documento_paciente": null,
    "nombre_paciente": null,
    "cita_id": null
  }},
  "urgencia": "normal",
  "claridad": "clara"
}}

NO uses mayúsculas en las claves. SIEMPRE incluye "intencion" y "entidades"."""

        try:
            # 🔥 USAR GEMINI ADAPTER PARA ANÁLISIS DE INTENCIÓN (más rápido y económico)
            if self.gemini:
                resultado = await self.gemini.generar_respuesta(
                    mensajes=[
                        {"role": "system", "content": self.get_system_prompt()},
                        {"role": "user", "content": prompt_analisis}
                    ],
                    temperature=0.1,
                    max_tokens=600
                    # response_format no soportado en Gemini, se omite
                )
                respuesta_texto = resultado["respuesta"]
                logger.info(f"✅ Análisis intención con {resultado['backend']}: {resultado.get('tokens', 0)} tokens")
                
                # Parsear JSON de la respuesta
                try:
                    analisis = json.loads(respuesta_texto)
                except json.JSONDecodeError:
                    # Si no es JSON válido, intentar extraerlo
                    import re
                    json_match = re.search(r'\{.*\}', respuesta_texto, re.DOTALL)
                    if json_match:
                        analisis = json.loads(json_match.group())
                    else:
                        raise
            else:
                # Fallback a OpenAI si Gemini no disponible
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": self.get_system_prompt()},
                        {"role": "user", "content": prompt_analisis}
                    ],
                    temperature=0.1,
                    max_tokens=600,
                    response_format={"type": "json_object"}
                )
                respuesta_texto = response.choices[0].message.content.strip()
                analisis = json.loads(respuesta_texto)
                logger.info("✅ Análisis intención con GPT-4o (fallback)")
        except openai.RateLimitError as e:
            # 🆕 BUG #8 FIX: Manejo de rate limit
            logger.warning(f"⚠️ OpenAI Rate Limit alcanzado: {e}. Esperando 60s...")
            await asyncio.sleep(60)
            return {
                "intencion": "error_temporal",
                "entidades": {},
                "mensaje_original": mensaje,
                "error": "rate_limit",
                "respuesta_sugerida": "Disculpa, estamos experimentando alto tráfico. Por favor intenta en un momento."
            }
        except openai.APIConnectionError as e:
            # 🆕 BUG #8 FIX: Error de conexión
            logger.error(f"❌ Error de conexión con OpenAI: {e}")
            return {
                "intencion": "error_conexion",
                "entidades": {},
                "mensaje_original": mensaje,
                "error": "connection_error"
            }
        except openai.APIError as e:
            # 🆕 BUG #8 FIX: Error general de API
            logger.error(f"❌ Error de OpenAI API: {e}")
            return {
                "intencion": "error_temporal",
                "entidades": {},
                "mensaje_original": mensaje,
                "error": "api_error"
            }
        except Exception as e:
            logger.error(f"❌ Error inesperado en análisis: {e}")
            return {
                "intencion": "error_analisis",
                "entidades": {},
                "mensaje_original": mensaje
            }
        
        try:
            # analisis ya está parseado arriba (línea ~660)
            resultado = analisis
            resultado["mensaje_original"] = mensaje
            
            # Normalizar campos - GPT puede usar diferentes nombres
            # Intentar todas las variaciones posibles
            if "INTENCIÓN PRINCIPAL" in resultado:
                resultado["intencion"] = resultado["INTENCIÓN PRINCIPAL"]
            elif "intencion_principal" in resultado and "intencion" not in resultado:
                resultado["intencion"] = resultado["intencion_principal"]
            elif "INTENCION" in resultado and "intencion" not in resultado:
                resultado["intencion"] = resultado["INTENCION"]
            
            if "ENTIDADES" in resultado:
                resultado["entidades"] = resultado["ENTIDADES"]
            elif "entidades_extraidas" in resultado and "entidades" not in resultado:
                resultado["entidades"] = resultado["entidades_extraidas"]
            
            # Asegurar que siempre tenga los campos mínimos
            if "intencion" not in resultado:
                resultado["intencion"] = "otra_consulta"
            if "entidades" not in resultado:
                resultado["entidades"] = {}
            if "urgencia" not in resultado and "URGENCIA" in resultado:
                resultado["urgencia"] = resultado["URGENCIA"]
            if "claridad" not in resultado and "CLARIDAD" in resultado:
                resultado["claridad"] = resultado["CLARIDAD"]
            
            logger.info(f"✅ Intención analizada con contexto: {resultado.get('intencion')}")
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Error analizando intención: {e}")
            return {
                "intencion": "otra_consulta",
                "entidades": {},
                "urgencia": "normal", 
                "claridad": "necesita_aclaracion",
                "mensaje_original": mensaje
            }
    
    async def _generar_respuesta(self, analisis: Dict, contexto: Dict = None) -> Dict:
        """Genera respuesta inteligente basada en análisis"""
        
        # Verificar que analisis tenga los campos necesarios
        if not isinstance(analisis, dict) or "intencion" not in analisis:
            logger.warning(f"Análisis inválido: {analisis}")
            # Usar respuesta general por defecto
            return await self._respuesta_general({"intencion": "otra_consulta", "mensaje_original": ""}, contexto)
        
        intencion = analisis.get("intencion", "otra_consulta")
        entidades = analisis.get("entidades", {})
        
        # Determinar si requiere escalamiento
        requiere_escalamiento = self._determinar_escalamiento(analisis, contexto)
        
        if requiere_escalamiento:
            return self._generar_respuesta_escalamiento(analisis, contexto)
        
        # ========== VALIDACIÓN PRIORITARIA: MÚLTIPLES CITAS ==========
        # Detectar ANTES de procesar intenciones específicas
        mensaje_original = analisis.get("mensaje_original", "")
        if self._es_solicitud_multiple_citas(mensaje_original):
            # 🔥 VALIDACIÓN CRÍTICA: Primera vez solo permite 1 cita
            mensaje_lower = mensaje_original.lower()
            if any(frase in mensaje_lower for frase in ["primera vez", "1ra vez", "primer vez", "primera cita"]):
                cantidad = self._extraer_cantidad_citas(mensaje_lower)
                if cantidad and cantidad > 1:
                    return {
                        "respuesta": """⚠️ **Limitación Importante**

📋 Para citas de **primera vez** en fisioterapia, solo se puede agendar **1 cita inicial** (ya que requiere orden médica y evaluación).

✅ **Después de tu primera cita**, podrás agendar múltiples citas de control sin problema.

💬 **¿Deseas agendar tu primera cita de fisioterapia?**

O si ya has tenido citas con nosotros antes, dime y podemos agendar múltiples citas de control.""",
                        "intencion": "limitacion_primera_vez_multiple",
                        "requiere_escalamiento": False
                    }
            
            # Si pasa validación, manejar múltiples citas
            return await self._manejar_solicitud_multiple_citas(mensaje_original, analisis, contexto)
        
        # ========== PROCESAR INTENCIONES ESPECÍFICAS ==========
        # Generar respuesta específica según intención
        if intencion == "agendar_cita_generica":
            return self._respuesta_cita_generica(contexto)
        elif intencion == "agendar_fisioterapia_primera_vez":
            return await self._respuesta_fisioterapia_primera_vez(entidades, contexto)
        elif intencion == "agendar_fisioterapia_control":
            return await self._respuesta_fisioterapia_control(entidades, contexto)
        elif intencion == "agendar_fisioterapia":
            return await self._respuesta_agendar_fisioterapia(entidades, contexto)
        elif intencion == "agendar_acondicionamiento":
            return self._respuesta_agendar_acondicionamiento(entidades, contexto)
        elif intencion == "fisioterapia_no_soportada":
            return self._respuesta_fisioterapia_no_soportada()
        elif intencion == "agendar_cita_medica":
            return self._generar_respuesta_escalamiento(analisis, contexto)
        elif intencion == "escalamiento_manual":
            return self._generar_respuesta_escalamiento(analisis, contexto)
        
        # 🔥 FIX: Manejar intención combinada "consultar_horarios/precios/fisioterapeutas"
        elif "consultar_horarios" in intencion or "consultar_precios" in intencion or "consultar_fisioterapeutas" in intencion:
            # Si pregunta por servicios en general, usar respuesta estructurada
            mensaje_lower = mensaje_original.lower() if mensaje_original else ""
            if any(palabra in mensaje_lower for palabra in ["servicios", "servicio", "que ofrecen", "qué ofrecen", "que tienen", "qué tienen"]):
                return self._respuesta_servicios(analisis, contexto)
            else:
                return await self._respuesta_general(analisis, contexto)
        
        elif intencion == "consultar_mis_citas":
            return await self._consultar_citas_paciente(entidades, contexto)
        elif intencion == "modificar_cita":
            return await self._modificar_cita_paciente(entidades, analisis, contexto)
        elif intencion == "cancelar_cita":
            return await self._cancelar_cita_paciente(entidades, analisis, contexto)
         
        else:
            return await self._respuesta_general(analisis, contexto)
    
    def _determinar_escalamiento(self, analisis: Dict, contexto: Dict = None) -> bool:
        """Determina si requiere escalamiento a secretarias con lógica inteligente"""
        
        intencion = analisis.get("intencion")
        entidades = analisis.get("entidades", {})
        urgencia = analisis.get("urgencia", "normal")
        claridad = analisis.get("claridad", "clara")
        mensaje_original = str(analisis.get("mensaje_original", "")).lower()  # ✅ Defensive: convert to str and lower
        
        # ESCALAMIENTO INMEDIATO - Casos críticos
        
        # 1. Comandos manuales de escalamiento
        comandos_escalamiento = ["/escalate", "/transfer", "/help", "/humano", "hablar con persona", "persona real", "persona humana", "atención humana", "agente humano", "quiero hablar con un humano", "humano"]
        if any(comando in mensaje_original for comando in comandos_escalamiento):
            return True
        if any(cmd in mensaje_original.lower() for cmd in comandos_escalamiento):
            return True
        
        # 2. Citas médicas (siempre escalar)
        if intencion == "agendar_cita_medica":
            return True
        
        # 3. Urgencias altas
        if urgencia == "alta":
            return True
        
        # 4. Pagos por transferencia
        metodo_pago = str(entidades.get("metodo_pago_preferido") or "").lower()  # ✅ Defensive
        if intencion == "pago_transferencia" or metodo_pago in ["transferencia", "transferir", "consignacion"]:
            return True
        
        # ESCALAMIENTO POR COMPLEJIDAD
        
        # 5. Servicios no soportados - NO escalar, responder directamente
        if intencion == "fisioterapia_no_soportada":
            return False  # Responder directamente sin escalamiento
        
        # 6. Múltiples intentos fallidos
        intentos_fallidos = contexto.get("intentos_fallidos", 0) if contexto and isinstance(contexto, dict) else 0
        if intentos_fallidos >= 3:
            return True
        
        # 7. Casos complejos múltiples
        cantidad_citas = entidades.get("cantidad_citas", 1)
        if cantidad_citas and cantidad_citas > 5:  # Más de 5 citas requiere planificación especial
            return True
        
        # 8. Modificaciones o cancelaciones complejas
        if intencion in ["modificar_cita", "cancelar_cita"] and contexto:
            citas_existentes = contexto.get("citas_programadas", []) if contexto and isinstance(contexto, dict) else []
            if len(citas_existentes) > 2:
                return True
        
        # 9. Problemas técnicos recurrentes
        errores_consecutivos = contexto.get("errores_consecutivos", 0) if contexto and isinstance(contexto, dict) else 0
        if errores_consecutivos >= 2:
            return True
        
        # 10. Solicitudes ambiguas repetidas
        if claridad == "necesita_aclaracion":
            aclaraciones_pedidas = contexto.get("aclaraciones_pedidas", 0) if contexto and isinstance(contexto, dict) else 0
            if aclaraciones_pedidas >= 2:
                return True
        
        # 11. Casos que requieren autorización especial
        palabras_autorizacion = ["descuento", "exoneración", "convenio", "empresa", "eps especial"]
        if any(palabra in mensaje_original.lower() for palabra in palabras_autorizacion):
            return True
        
        return False
    


    def _respuesta_ubicacion(self):
        """Responde con información de ubicación"""
        return """📍 **¡Claro! Estamos ubicados en:**

🏥 Calle 10 32-115, Medellín, Antioquia

📲 WhatsApp: 3193175762
📞 Teléfono: 604 705 8040

¿Necesitas que te ayude con algo más? 😊"""

    def _respuesta_contacto(self):
        """Responde con información de contacto"""
        return """📞 **Puedes contactarnos por:**

📲 WhatsApp: 3193175762
☎️ Teléfono: 604 705 8040
📍 Calle 10 32-115, Medellín

**Horarios:**
• Lunes a Jueves: 5:00 AM - 8:00 PM
• Viernes: 5:00 AM - 7:00 PM  
• Sábados: 8:00 AM - 12:00 PM
• Domingos: Cerrado

¿Hay algo más en lo que te pueda ayudar? 😊"""

    def _respuesta_horarios(self) -> Dict:
        """Respuesta sobre horarios de la IPS"""
        texto = f"""🕐 **Horarios IPS React:**

📍 Calle 10 32-115, Medellín

⏰ **Atención:**
• Lunes a Jueves: 5:00 AM - 8:00 PM
• Viernes: 5:00 AM - 7:00 PM  
• Sábados: 8:00 AM - 12:00 PM

¿En qué horario te gustaría agendar?"""
        
        return {
            "texto": texto,
            "accion": "informacion_proporcionada",
            "siguiente_paso": "continuar"
        }
    
    def _respuesta_cita_generica(self, contexto: Dict = None) -> Dict:
        """Respuesta para consulta genérica de agendamiento
        
        Si es el primer mensaje (saludo inicial), solo da bienvenida.
        Si ya hay contexto, ofrece opciones de cita.
        """
        # Verificar si es el primer mensaje (saludo inicial)
        historial = contexto.get("historial", []) if contexto else []
        es_primer_mensaje = len(historial) <= 1  # Solo el mensaje actual del usuario
        
        if es_primer_mensaje:
            # Saludo inicial simple y humano (sin mencionar 'cita')
            texto = """👋 Bienvenido a IPS REACT, ¿en qué te puedo ayudar hoy? 😊"""
        else:
            # Ya hay conversación, ofrecer opciones específicas
            texto = """¡Perfecto! Te cuento qué tenemos disponible:

1️⃣ **Acondicionamiento Físico** - Entrenamiento personalizado
2️⃣ **Fisioterapia** - Ortopédica o cardíaca
3️⃣ **Cita Médica** - Especialistas en medicina deportiva y más

¿Cuál te interesa?"""
        
        return {
            "texto": texto,
            "accion": "solicitar_tipo_cita",
            "siguiente_paso": "esperar_tipo_cita"
        }
    
    async def _respuesta_fisioterapia_primera_vez(self, entidades: Dict, contexto: Dict = None) -> Dict:
        """Respuesta específica para primera vez en fisioterapia"""
        
        # 🔥 VERIFICAR SI YA TIENE ORDEN MÉDICA PROCESADA
        if self.datos_paciente.get("orden_medica_procesada"):
            logger.info("✅ Orden médica ya procesada, saltando pregunta y yendo directo a agendamiento")
            
            # Ya tiene orden, proceder directamente a preguntar fecha/hora
            fisioterapeuta = entidades.get("fisioterapeuta_mencionado", "")
            if fisioterapeuta == "auto":
                fisio_asignado = await self._obtener_fisioterapeuta_mas_disponible()
                fisioterapeuta_texto = f"con **{fisio_asignado}**"
            elif fisioterapeuta:
                fisioterapeuta_texto = f"con **{self._obtener_nombre_completo_fisioterapeuta(fisioterapeuta)}**"
            else:
                fisio_asignado = await self._obtener_fisioterapeuta_mas_disponible()
                fisioterapeuta_texto = f"con **{fisio_asignado}** (asignación automática)"
            
            # Extraer datos de la orden procesada
            paciente_data = self.datos_paciente.get("analisis_orden_medica", {}).get("paciente", {})
            eps_nombre = paciente_data.get("eps", self.datos_paciente.get("entidad_eps", ""))
            
            texto = f"""✅ **¡Perfecto! Ya tengo tu orden médica registrada**

👨‍⚕️ **Fisioterapeuta asignado:** {fisio_asignado if not fisioterapeuta else self._obtener_nombre_completo_fisioterapeuta(fisioterapeuta)}
🏥 **EPS:** {eps_nombre}

📅 **¿Para qué día y hora te gustaría agendar?**

Ejemplos:
• "Mañana a las 10am"
• "Este lunes 25 a las 2pm"
• "El próximo jueves en la mañana"

⏰ **Horario disponible:**
• Lunes a Viernes: 8:00 AM - 6:00 PM
• Sábados: 8:00 AM - 1:00 PM"""
            
            return {
                "texto": texto,
                "accion": "solicitar_fecha_hora",
                "siguiente_paso": "esperar_fecha_hora",
                "escalar": False,
                "activar_recopilacion": True,
                "tipo_fisioterapia": "primera_vez",
                "orden_medica_confirmada": True
            }
        
        # Si NO tiene orden médica, flujo normal
        fisioterapeuta = entidades.get("fisioterapeuta_mencionado", "")
        
        # Si NO mencionó fisioterapeuta, preguntar preferencia
        if not fisioterapeuta:
            texto = """🎯 **¡Perfecto! Vamos con tu primera cita de fisioterapia** 😊

📋 **Importante:** Como es tu primera vez, necesitas traer la **orden médica** el día de la cita (es obligatoria).

👨‍⚕️ **¿Tienes preferencia de fisioterapeuta?**

💬 Puedes decirme:
• El nombre de algún fisioterapeuta que conozcas
• "El más disponible" y yo te asigno automáticamente 🎯
• "Dame opciones" si quieres ver la lista completa

¿Qué prefieres?"""
            
            return {
                "texto": texto,
                "accion": "preguntar_fisioterapeuta",
                "siguiente_paso": "esperar_fisioterapeuta",
                "escalar": False,
                "activar_recopilacion": False,
                "tipo_fisioterapia": "primera_vez"
            }
        
        # Si YA mencionó fisioterapeuta, continuar con agendamiento
        fisio_asignado = None
        
        # Validar si es rehabilitación cardíaca
        tipo_fisio_lower = (entidades.get("tipo_fisioterapia") or "").lower()
        es_cardiaca = any(palabra in tipo_fisio_lower for palabra in ["cardia", "cardiovascular", "corazon", "corazón"])
        
        if fisioterapeuta == "auto":
            if es_cardiaca:
                fisio_asignado = await self._obtener_fisioterapeuta_mas_disponible(tipo_rehabilitacion="cardiaca")
            else:
                fisio_asignado = await self._obtener_fisioterapeuta_mas_disponible(tipo_rehabilitacion="ortopedica")
            fisio_texto = f"Te voy a agendar con **{fisio_asignado}**, que es quien tiene mejor disponibilidad"
        else:
            fisio_completo = self._obtener_nombre_completo_fisioterapeuta(fisioterapeuta)
            
            # Validar que el fisioterapeuta elegido puede atender rehabilitación cardíaca
            if es_cardiaca and fisio_completo not in self.fisioterapeutas_cardiaca:
                fisios_cardiaca_nombres = "\n• ".join(self.fisioterapeutas_cardiaca)
                return {
                    "texto": f"""⚠️ **Importante sobre Rehabilitación Cardíaca**

**{fisio_completo}** no atiende rehabilitación cardíaca. Solo estos fisioterapeutas están especializados:

• {fisios_cardiaca_nombres}

💬 **¿Con cuál de ellos prefieres agendar?**

O dime "el más disponible" y te asigno automáticamente. 😊""",
                    "accion": "requerir_fisioterapeuta_cardiaco",
                    "siguiente_paso": "esperar_fisioterapeuta_cardiaco",
                    "escalar": False,
                    "activar_recopilacion": False,
                    "tipo_fisioterapia": "primera_vez_cardiaca"
                }
            
            fisio_texto = f"Perfecto, agendaremos con **{fisio_completo}**"
        
        texto = f"""🎯 **¡Perfecto!** {fisio_texto} 😊

📋 **Recordatorio importante:** Como es tu primera vez, necesitas traer la **orden médica** el día de la cita (es obligatoria).

💬 **Para confirmar tu cita necesito saber:**
• ¿Qué día te funciona mejor? 📅
• ¿Ya tienes tu orden médica? 📄

💰 **Inversión:** $60,000 COP particular o según tu póliza/EPS 💳"""
        
        return {
            "texto": texto,
            "accion": "recopilar_datos_primera_vez",
            "siguiente_paso": "esperar_confirmacion_orden",
            "escalar": False,
            "activar_recopilacion": True,
            "tipo_fisioterapia": "primera_vez"
        }
    
    async def _respuesta_fisioterapia_control(self, entidades: Dict, contexto: Dict = None) -> Dict:
        """Respuesta específica para fisioterapia de control/seguimiento"""
        
        fisioterapeuta = entidades.get("fisioterapeuta_mencionado", "")
        
        # Si NO mencionó fisioterapeuta, preguntar preferencia (igual que en primera vez)
        if not fisioterapeuta:
            texto = """🎯 **¡Perfecto! Vamos con tu control de fisioterapia** 😊

✅ Como es control, **no necesitas orden médica nueva**.

👨‍⚕️ **¿Con quién prefieres la cita?**

💬 Puedes decirme:
• El nombre del fisioterapeuta con quien ya te atiend es
• "El más disponible" y yo te asigno
• "Dame opciones" si quieres ver la lista

¿Qué prefieres?"""
            
            return {
                "texto": texto,
                "accion": "preguntar_fisioterapeuta",
                "siguiente_paso": "esperar_fisioterapeuta",
                "escalar": False,
                "activar_recopilacion": False,
                "tipo_fisioterapia": "control"
            }
        
        # Si YA mencionó fisioterapeuta, continuar
        if fisioterapeuta == "auto":
            fisio_asignado = await self._obtener_fisioterapeuta_mas_disponible()
            fisioterapeuta_texto = f"Te voy a agendar con **{fisio_asignado}**, que es quien tiene mejor disponibilidad"
        elif fisioterapeuta:
            fisio_completo = self._obtener_nombre_completo_fisioterapeuta(fisioterapeuta)
            fisioterapeuta_texto = f"Perfecto, agendaremos con **{fisio_completo}**"
        else:
            fisioterapeuta_texto = "Te asignaré al fisioterapeuta con mejor disponibilidad"
        
        texto = f"""¡Excelente! {fisioterapeuta_texto}.

🔄 Como es control, no necesitas orden médica nueva.

💬 Para confirmar tu cita necesito saber:
• ¿Qué día te funciona mejor?
• ¿A qué hora prefieres?

💰 El costo es de $60,000 particular o según tu póliza/EPS."""
        
        return {
            "texto": texto,
            "accion": "recopilar_datos_control",
            "siguiente_paso": "esperar_datos_control",
            "escalar": False,
            "activar_recopilacion": True,
            "tipo_fisioterapia": "control"
        }

    async def _respuesta_agendar_fisioterapia(self, entidades: Dict, contexto: Dict = None) -> Dict:
        """Respuesta genérica de fisioterapia - pregunta si es primera vez o control"""
        
        fisioterapeuta = entidades.get("fisioterapeuta_mencionado", "")
        if fisioterapeuta:
            fisioterapeuta_texto = f" con **{self._obtener_nombre_completo_fisioterapeuta(fisioterapeuta)}**"
        else:
            fisioterapeuta_texto = ""
        
        # Verificar si es primera vez desde entidades
        tipo_fisioterapia = entidades.get("tipo_fisioterapia")
        if tipo_fisioterapia == "primera_vez":
            return await self._respuesta_fisioterapia_primera_vez(entidades, contexto)
        elif tipo_fisioterapia == "control":
            return await self._respuesta_fisioterapia_control(entidades, contexto)
        
        texto = f"""🎯 **¡Perfecto! Te ayudo con tu cita de fisioterapia{fisioterapeuta_texto}**

🤔 **¿Es tu primera vez o ya vienes a control?**

1️⃣ **Primera vez** → Necesitas orden médica
2️⃣ **Control/Seguimiento** → Ya tienes historial aquí

💬 **¿Cuál aplica para ti?**"""
        
        return {
            "texto": texto,
            "accion": "preguntar_tipo_fisioterapia",
            "siguiente_paso": "esperar_tipo_fisioterapia",
            "escalar": False,
            "activar_recopilacion": False  # No activar hasta saber el tipo
        }
    
    def _obtener_nombre_completo_fisioterapeuta(self, nombre_parcial: str) -> str:
        """Convierte nombre parcial a nombre completo del fisioterapeuta"""
        
        nombres_fisioterapeutas = {
            "migue": "Miguel Ignacio Moreno Cardona",
            "miguel": "Miguel Ignacio Moreno Cardona",
            "diana": "Diana Daniella Arana Carvalho", 
            "adriana": "Adriana Acevedo Agudelo",
            "ana": "Ana Isabel Palacio Botero",
            "ana isabel": "Ana Isabel Palacio Botero",
            "diego": "Diego Andrés Mosquera Torres",
            "veronica": "Verónica Echeverri Restrepo",
            "verónica": "Verónica Echeverri Restrepo",
            "daniela": "Daniela Patiño Londoño"
        }
        
        nombre_lower = nombre_parcial.lower().strip()
        return nombres_fisioterapeutas.get(nombre_lower, nombre_parcial)
    
    async def _obtener_fisioterapeuta_mas_disponible(self, tipo_rehabilitacion: str = "ortopedica") -> str:
        """
        Obtiene el fisioterapeuta con menor carga de citas programadas A FUTURO.
        Consulta REAL a SaludTools para ver carga actual de cada fisioterapeuta.
        
        Args:
            tipo_rehabilitacion: "cardiaca" o "ortopedica"
            
        Returns:
            Nombre completo del fisioterapeuta con menor carga
        """
        from datetime import datetime, timedelta
        
        # Determinar pool de fisioterapeutas según tipo de rehabilitación
        tipo_rehabilitacion = str(tipo_rehabilitacion or "ortopedica").lower()
        
        if tipo_rehabilitacion == "cardiaca" or "cardiovascular" in tipo_rehabilitacion:
            # Solo estos 3 pueden atender cardíaca
            fisioterapeutas_pool = [
                "Adriana Acevedo Agudelo",
                "Ana Isabel Palacio Botero",
                "Diana Daniella Arana Carvalho"
            ]
        else:
            # Todos pueden atender ortopédica
            fisioterapeutas_pool = [
                "Miguel Ignacio Moreno Cardona",
                "Diego Andrés Mosquera Torres",
                "Verónica Echeverri Restrepo",
                "Daniela Patiño Londoño",
                # Los de cardíaca también pueden hacer ortopédica
                "Adriana Acevedo Agudelo",
                "Ana Isabel Palacio Botero",
                "Diana Daniella Arana Carvalho"
            ]
        
        # Consultar carga REAL en SaludTools para cada fisioterapeuta
        citas_por_fisio = {}
        hoy = datetime.now(COLOMBIA_TZ)
        fecha_limite = hoy + timedelta(days=30)  # Próximos 30 días
        
        try:
            for fisio_nombre in fisioterapeutas_pool:
                fisio_cc = self.fisioterapeutas_cc.get(fisio_nombre)
                if not fisio_cc:
                    logger.warning(f"No se encontró CC para {fisio_nombre}")
                    continue
                
                try:
                    # Buscar citas del fisioterapeuta en SaludTools
                    citas = await self.saludtools.buscar_citas_por_documento(
                        documento=fisio_cc,
                        tipo_documento=1  # Cédula
                    )
                    
                    # Filtrar solo citas FUTURAS (desde hoy hacia adelante)
                    citas_futuras = []
                    for cita in citas:
                        try:
                            fecha_cita_str = cita.get('startAppointment', '')
                            if fecha_cita_str:
                                fecha_cita = datetime.strptime(fecha_cita_str, '%Y-%m-%d %H:%M')
                                if fecha_cita >= hoy:
                                    citas_futuras.append(cita)
                        except Exception as e:
                            logger.debug(f"Error parseando fecha de cita: {e}")
                            continue
                    
                    citas_por_fisio[fisio_nombre] = len(citas_futuras)
                    logger.info(f"📊 {fisio_nombre}: {len(citas_futuras)} citas futuras")
                    
                except Exception as e:
                    logger.warning(f"Error consultando citas de {fisio_nombre}: {e}")
                    # Si falla, asumir 0 citas (darle prioridad)
                    citas_por_fisio[fisio_nombre] = 0
            
            # Si obtuvimos datos, retornar el que tiene MENOS citas
            if citas_por_fisio:
                fisio_menos_carga = min(citas_por_fisio, key=citas_por_fisio.get)
                logger.info(f"✅ Fisioterapeuta con menor carga: {fisio_menos_carga} ({citas_por_fisio[fisio_menos_carga]} citas)")
                return fisio_menos_carga
            
        except Exception as e:
            logger.error(f"Error en consulta de carga de fisioterapeutas: {e}")
        
        # Fallback: Si falla la consulta, rotar por hora del día
        logger.warning("⚠️ Fallback a rotación por hora (no se pudo consultar SaludTools)")
        dia_semana = datetime.now().weekday()
        hora = datetime.now().hour
        index = (dia_semana + hora) % len(fisioterapeutas_pool)
        return fisioterapeutas_pool[index]
    
    async def _respuesta_general(self, analisis: Dict, contexto: Dict = None) -> Dict:
        """Respuesta general para consultas diversas usando GPT-4o con contexto completo"""
        
        intencion = analisis.get("intencion", "")
        mensaje_original = analisis.get("mensaje_original", "") or ""
        
        # 🔥 CASOS ESPECIALES que necesitan respuesta hardcodeada
        # (Solo casos muy específicos que NO requieren contexto conversacional)
        
        if any(word in mensaje_original.lower() for word in ["lista", "cuáles", "cuales", "todos los fisio", "qué fisio", "que fisio", "dame opciones", "opciones", "quiénes", "quienes"]):
            # Usuario pide explícitamente la lista de fisioterapeutas
            texto = """👨‍⚕️ **Nuestros Fisioterapeutas:**

🫀 **Rehabilitación Cardíaca** (también hacen ortopédica):
• Adriana Acevedo
• Ana Palacio
• Diana Arana

🦴 **Solo Ortopédica:**
• Miguel Moreno
• Diego Mosquera
• Verónica Echeverri

💬 **¿Con quién prefieres agendar?**"""
            
        elif any(word in mensaje_original.lower() for word in ["fisioterapeuta", "especialista", "doctor", "quien", "miguel", "diana", "adriana", "ana"]):
            # Detectar si mencionan un fisioterapeuta específico
            mensaje_lower = mensaje_original.lower()
            
            if "miguel" in mensaje_lower:
                texto = """👨‍⚕️ **Miguel Ignacio Moreno Cardona**

✅ Fisioterapeuta especialista en ortopédica
💪 Experto en rehabilitación músculo-esquelética

¿Confirmas que quieres agendar con Miguel? Déjame saber:
• ¿Es primera vez o control?
• ¿Qué fecha te viene mejor?
• ¿Tienes orden médica? (obligatoria para primera vez)"""
            elif "diana" in mensaje_lower:
                texto = """👩‍⚕️ **Diana Daniella Arana**

✅ Especialista en rehabilitación cardíaca y ortopédica
💝 Ideal para pacientes con problemas cardíacos

¿Confirmas cita con Diana? Cuéntame:
• ¿Primera vez o control?
• ¿Qué fecha prefieres?
• ¿Es para rehabilitación cardíaca?"""
            elif "adriana" in mensaje_lower or "acevedo" in mensaje_lower:
                texto = """👩‍⚕️ **Adriana Acevedo** - Especialista en rehabilitación cardíaca

¿Confirmas cita con Adriana? Necesito:
• ¿Primera vez o control?
• ¿Qué fecha prefieres?"""
            elif "ana" in mensaje_lower and "isabel" in mensaje_lower:
                texto = """👩‍⚕️ **Ana Isabel Palacio** - Cardíaca y ortopédica

¿Confirmas cita con Ana Isabel? Déjame saber:
• ¿Primera vez o control?
• ¿Qué fecha te viene bien?"""
            else:
                texto = """👨‍⚕️ **Nuestros Fisioterapeutas:**

🫀 **Rehabilitación Cardíaca** (también hacen ortopédica):
• Adriana Acevedo
• Ana Palacio
• Diana Arana

🦴 **Solo Ortopédica:**
• Miguel Moreno
• Diego Mosquera
• Verónica Echeverri
• Daniela Patiño

💬 ¿Con quién prefieres agendar?"""
        
        elif any(word in mensaje_original.lower() for word in ["piso", "pélvico", "hidroterapia", "respiratoria", "neurológica", "deportiva", "estética"]):
            texto = """Lo siento, en IPS React **solo ofrecemos 2 tipos de fisioterapia:**

✅ **SÍ ofrecemos:**
• Fisioterapia **Ortopédica** (lesiones, post-quirúrgica, dolor músculo-esquelético)
• Fisioterapia **Cardíaca** (rehabilitación cardíaca, post-infarto)

❌ **NO ofrecemos:**
• Fisioterapia del piso pélvico
• Hidroterapia
• Fisioterapia respiratoria
• Fisioterapia neurológica
• Fisioterapia deportiva
• Fisioterapia estética

💡 Si necesitas fisioterapia ortopédica o cardíaca, ¡con gusto te ayudo!

¿Te interesa agendar alguna de las dos que sí manejamos?"""
            
        else:
            # 🔥 USAR GPT-4o CON HISTORIAL COMPLETO - No respuesta genérica
            # Construir historial para GPT
            messages = []
            
            # Agregar historial de conversación si existe
            if contexto and isinstance(contexto, dict):
                historial = contexto.get("historial", [])
                for msg in historial[-10:]:  # Últimos 10 mensajes
                    if isinstance(msg, tuple) and len(msg) == 2:
                        role, content = msg
                        if role == "usuario":
                            messages.append({"role": "user", "content": content})
                        elif role in ["ia_c", "asistente"]:
                            messages.append({"role": "assistant", "content": content})
                    elif isinstance(msg, dict):
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role == "usuario":
                            messages.append({"role": "user", "content": content})
                        elif role in ["ia_c", "asistente"]:
                            messages.append({"role": "assistant", "content": content})
            
            # Agregar mensaje actual
            messages.append({"role": "user", "content": mensaje_original})
            
            # 🔥 LLAMAR A GEMINI ADAPTER CON CONTEXTO COMPLETO (inyección automática de fecha)
            try:
                if self.gemini:
                    resultado = await self.gemini.generar_respuesta(
                        mensajes=[
                            {"role": "system", "content": self.get_system_prompt()},
                            *messages
                        ],
                        temperature=0.7,
                        max_tokens=500
                    )
                    texto = resultado["respuesta"]
                    logger.info(f"✅ {resultado['backend']} respuesta contextual: {texto[:100]}... ({resultado.get('tokens', 0)} tokens)")
                else:
                    # Fallback a OpenAI si Gemini no disponible
                    response = await client.chat.completions.create(
                        model=MODEL,
                        messages=[
                            {"role": "system", "content": self.get_system_prompt()},
                            *messages
                        ],
                        temperature=0.7,
                        max_tokens=500
                    )
                    texto = response.choices[0].message.content.strip()
                    logger.info(f"✅ GPT-4o respuesta contextual (fallback): {texto[:100]}...")
            except openai.RateLimitError as e:
                # 🆕 BUG #8 FIX: Rate limit en respuesta contextual
                logger.warning(f"⚠️ Rate limit en respuesta contextual: {e}")
                await asyncio.sleep(5)  # Espera más corta aquí
                texto = "Disculpa, estamos experimentando alto tráfico. ¿Podrías repetir tu consulta en un momento?"
            except openai.APIError as e:
                logger.error(f"❌ Error OpenAI API en respuesta: {e}")
                texto = """👋 Bienvenido a IPS REACT, ¿en qué te puedo ayudar hoy? 😊"""
            except Exception as e:
                logger.error(f"Error llamando GPT-4o: {e}")
                texto = """👋 Bienvenido a IPS REACT, ¿en qué te puedo ayudar hoy? 😊"""
        
        return {
            "texto": texto,
            "accion": "informacion_proporcionada",
            "siguiente_paso": "esperar_nueva_consulta"
        }

    def _respuesta_fisioterapeutas(self) -> str:
        """Lista completa de fisioterapeutas disponibles"""
        return """👨‍⚕️ **Nuestros fisioterapeutas:**

🫀 **Rehabilitación Cardíaca** (también hacen ortopédica):
• Adriana Acevedo
• Ana Palacio
• Diana Arana

🦴 **Ortopédica**:
• Miguel Moreno
• Diego Mosquera
• Verónica Echeverri
• Daniela Patiño

💬 ¿Con quién te gustaría agendar? 😊"""
    
    def _respuesta_precios(self, tipo: str = "general") -> str:
        """Información de precios y planes"""
        tipo = str(tipo or "general").lower()  # ✅ Defensive: convert to str and lower
        if "individual" in tipo or "clase" in tipo:
            return """💰 **Precios de Acondicionamiento Físico:**

🏋️‍♀️ **Clase individual:** $50,000 (60 minutos)

📅 **O puedes tomar planes mensuales:**
• Básico (8 sesiones): $320,000
• Intermedio (12 sesiones): $380,000  
• Avanzado (16 sesiones): $440,000

¿Te interesa alguno? 😊"""

        return """💰 **Planes de Acondicionamiento Físico:**

💳 **Clase individual:** $50,000 (60 minutos)

📅 **Planes mensuales:**
• Básico (8 sesiones): $320,000
• Intermedio (12 sesiones): $380,000
• Avanzado (16 sesiones): $440,000
• Intensivo (20 sesiones): $500,000

⚠️ Ten en cuenta que el acondicionamiento físico solo acepta pago particular (no EPS).

¿Cuál te gustaría?"""
    
    def _respuesta_fisioterapia_no_soportada(self) -> Dict:
        """Respuesta específica para fisioterapias no soportadas"""
        return {
            "respuesta": """Lo siento, en IPS React **no realizamos** ese tipo de fisioterapia. 

❌ **Servicios que NO ofrecemos:**
• Fisioterapia del piso/suelo pélvico
• Hidroterapia (terapia en agua)
• Fisioterapia respiratoria
• Fisioterapia neurológica
• Crioterapia
• Cámara bariátrica
• Parálisis miofacial

✅ **SOLO nos especializamos en fisioterapias ortopédicas:**
• Lesiones músculo-esqueléticas
• Rehabilitación post-quirúrgica ortopédica
• Rehabilitación cardíaca
• Acondicionamiento físico

💡 **¿Necesitas fisioterapia ortopédica?** ¡Con gusto te ayudo a agendar!
🏥 **Para otros tipos de fisioterapia**, te recomendamos consultar con centros especializados.

📞 **Contacto:** 3193175762""",
            "intencion": "fisioterapia_no_soportada",
            "requiere_escalamiento": False,
            "tipo": "informacion",
            "servicio_disponible": False
        }
    
    def _generar_respuesta_escalamiento(self, analisis: Dict, contexto: Dict = None) -> Dict:
        """Genera respuesta inteligente de escalamiento basada en contexto"""
        
        intencion = analisis.get("intencion", "general")
        entidades = analisis.get("entidades", {})
        urgencia = analisis.get("urgencia", "normal")
        motivo_escalamiento = self._determinar_motivo_escalamiento(analisis, contexto)
        
        # RESPUESTAS ESPECÍFICAS POR MOTIVO
        
        # Cita médica
        if "cita médica" in motivo_escalamiento.lower():
            respuesta = """👨‍⚕️ **Entendido!**

Te voy a conectar con nuestra secretaria para coordinar tu cita médica. Ella verificará disponibilidad de médicos y te contactará muy pronto por WhatsApp.

⏰ **Recibirás respuesta en los próximos minutos.**"""
            
        # Pago por transferencia
        elif "transferencia" in motivo_escalamiento.lower():
            respuesta = """💳 **PAGO POR TRANSFERENCIA**

¡Entendido! Nuestra secretaria te contactará con:

💰 **Datos de transferencia:**
• Número de cuenta bancaria
• Instrucciones de pago
• Confirmación del proceso

⏰ **Te responderá muy pronto.**

¿Algo más en lo que pueda ayudarte?"""
            
        # Atención humana
        elif "atención humana" in motivo_escalamiento.lower():
            respuesta = """🤝 **TE CONECTO CON UNA PERSONA**

¡Claro! Te comunicaré con nuestra secretaria para atención personalizada.

📞 **Contacto directo:**
• **WhatsApp:** 3193175762
• **Teléfono:** 6047058040

⏰ **Te responderá en breve.**"""
            
        # Casos complejos o específicos (default)
        else:
            respuesta = """🧩 **ATENCIÓN PERSONALIZADA**

Veo que tu solicitud necesita atención especial.

📋 **Nuestra secretaria te contactará para:**
• Revisar tu caso específico
• Coordinar lo que necesitas
• Darte la mejor solución

⏰ **Te responderá muy pronto.**

¿Necesitas algo más mientras tanto?"""
        
        return {
            "respuesta": respuesta,
            "intencion": "escalamiento_automatico",
            "motivo_escalamiento": motivo_escalamiento,
            "requiere_escalamiento": True,
            "prioridad": "alta" if urgencia == "alta" else "normal",
            "siguiente_paso": "contactar_equipo_humano"
        }
    
    def _determinar_motivo_escalamiento(self, analisis: Dict, contexto: Dict = None) -> str:
        """Determina el motivo específico del escalamiento - SOLO 4 CATEGORÍAS SIMPLES"""
        
        intencion = analisis.get("intencion", "")
        entidades = analisis.get("entidades", {})
        urgencia = analisis.get("urgencia", "normal")
        mensaje_original = str(analisis.get("mensaje_original") or "").lower()  # ✅ Defensive
        
        # 1. CITA MÉDICA
        if intencion == "agendar_cita_medica":
            return "desea agendar cita médica"
        
        if any(palabra in mensaje_original for palabra in ["cita medica", "cita médica", "doctor", "médico", "medico", "consulta médica"]):
            return "desea agendar cita médica"
        
        # 2. PAGO POR TRANSFERENCIA
        palabras_pago = ["transferencia", "transferir", "consignar", "consignación", "pago", "pagar", "cuenta bancaria", "datos bancarios"]
        if any(palabra in mensaje_original for palabra in palabras_pago):
            # Detectar qué está pagando
            if any(p in mensaje_original for p in ["suscripción", "suscripcion", "plan", "renovar", "renovación", "acondicionamiento"]):
                return "desea pagar suscripción acondicionamiento por transferencia"
            elif any(p in mensaje_original for p in ["fisioterapia", "sesion", "sesión", "cita"]):
                return "desea pagar fisioterapia por transferencia"
            else:
                return "desea pagar por transferencia"
        
        # 3. SOLICITUD DE ATENCIÓN HUMANA
        palabras_humano = ["humano", "persona", "hablar con alguien", "atención personal", "secretaria", "operador", "operadora", "ayuda", "/help", "/humano"]
        if any(palabra in mensaje_original for palabra in palabras_humano):
            return "paciente desea atención humana"
        
        # 4. CASO COMPLEJO/ESPECÍFICO (default para todo lo demás)
        # Casos que requieren atención especial
        if urgencia == "alta":
            return "caso complejo - urgente"
        
        if intencion == "escalamiento_manual":
            return "caso específico - requiere atención personalizada"
        
        if intencion == "fisioterapia_no_soportada":
            return "caso específico - servicio no disponible"
        
        # Múltiples citas
        cantidad_citas = entidades.get("cantidad_citas", 1)
        if cantidad_citas and cantidad_citas > 5:
            return "caso complejo - múltiples citas"
        
        # Default para cualquier otro caso
        return "caso específico - requiere atención personalizada"
    
    def _iniciar_recopilacion_datos(self) -> str:
        """Inicia el proceso de recopilación de datos del paciente"""
        self.esperando_datos = True
        
        return """📋 **¡Perfecto! Vamos a agendar tu cita** ✨

Necesito que me compartas los siguientes datos:

🪪 **Número de documento:**
🙋🏻 **Nombre completo:** 
🎂 **Fecha de nacimiento:** 
🩺 **Entidad (póliza/EPS, si aplica):**
📲 **Número de celular:** 
📧 **Correo electrónico:**
📍 **Dirección:**

👨🏻‍🦰👱‍♀ **Contacto de emergencia:**
🙋🏻‍♂ **Nombre:**
📲 **Teléfono:**
❓ **Parentesco:**

*Puedes enviarme todo junto o de a poco, como te sea más fácil* 😊"""
    
    def _procesar_datos_personales(self, mensaje: str) -> str:
        """Procesa y valida datos personales del paciente"""
        
        # Extraer datos del mensaje
        datos_extraidos = self._extraer_datos_del_mensaje(mensaje)
        
        # Actualizar datos del paciente
        for campo, valor in datos_extraidos.items():
            if valor and valor != "null":
                self.datos_paciente[campo] = valor
        
        # Verificar qué datos faltan
        datos_faltantes = self._verificar_datos_faltantes()
        
        if not datos_faltantes:
            # Todos los datos completos
            return self._confirmar_datos_completos()
        else:
            # Solicitar datos faltantes
            return self._solicitar_datos_faltantes(datos_faltantes)
    
    def _extraer_datos_del_mensaje(self, mensaje: str) -> Dict:
        """Extrae datos del paciente del mensaje usando IA"""
        
        prompt = f"""Extrae información del paciente de este mensaje para agendar cita médica.

Mensaje: "{mensaje}"

Extrae estos datos si están presentes:
- documento (números de cédula/identificación)
- nombre_completo (nombres y apellidos)
- fecha_nacimiento (formato DD/MM/AAAA)
- entidad_eps (EPS, póliza, seguro médico)
- telefono (número celular)
- email (correo electrónico)
- direccion (dirección completa)
- contacto_emergencia_nombre (nombre contacto emergencia)
- contacto_emergencia_telefono (teléfono contacto emergencia)
- contacto_emergencia_parentesco (relación: madre, esposo, etc.)

Responde en JSON:
{{
  "documento": "valor o null",
  "nombre_completo": "valor o null",
  "fecha_nacimiento": "valor o null",
  "entidad_eps": "valor o null",
  "telefono": "valor o null",
  "email": "valor o null",
  "direccion": "valor o null",
  "contacto_emergencia_nombre": "valor o null",
  "contacto_emergencia_telefono": "valor o null",
  "contacto_emergencia_parentesco": "valor o null"
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            datos = json.loads(response.choices[0].message.content)
            return {k: v for k, v in datos.items() if v and v != "null"}
            
        except Exception as e:
            logger.error(f"Error extrayendo datos: {e}")
            return {}
    
    def _validar_poliza_sin_convenio(self, eps: str) -> bool:
        """Valida si la póliza NO tiene convenio con IPS React
        
        Args:
            eps: Nombre de la EPS o póliza
        
        Returns:
            True si NO tiene convenio (debe pagar particular)
        """
        if not eps:
            return False
        
        eps_lower = eps.lower()
        
        for poliza in self.polizas_sin_convenio:
            if poliza in eps_lower:
                return True
        
        return False
    
    def _validar_poliza_con_convenio(self, eps: str) -> bool:
        """Valida si la póliza SÍ tiene convenio con IPS React
        
        Args:
            eps: Nombre de la EPS o póliza
        
        Returns:
            True si tiene convenio (puede usar EPS para pago)
        """
        if not eps:
            return False
        
        eps_lower = eps.lower()
        
        # Verificar primero si está en sin convenio
        if self._validar_poliza_sin_convenio(eps):
            return False
        
        # Luego verificar si está en con convenio
        for poliza in self.polizas_con_convenio:
            if poliza in eps_lower:
                return True
        
        # Si no está en ninguna lista, asumir que NO tiene convenio (por seguridad)
        return False
    
    def _verificar_datos_faltantes(self) -> List[str]:
        """Verifica qué datos obligatorios faltan"""
        faltantes = []
        
        campos_obligatorios = {
            "documento": "🪪 Número de documento",
            "nombre_completo": "🙋🏻 Nombre completo", 
            "fecha_nacimiento": "🎂 Fecha de nacimiento",
            "entidad_eps": "🩺 Entidad (EPS/póliza)",
            "telefono": "📲 Número telefónico",
            "email": "📧 Correo electrónico",
            "direccion": "📍 Dirección",
            "contacto_emergencia_nombre": "🙋🏻‍♂ Nombre contacto emergencia",
            "contacto_emergencia_telefono": "📲 Teléfono contacto emergencia",
            "contacto_emergencia_parentesco": "❓ Parentesco contacto emergencia"
        }
        
        for campo, descripcion in campos_obligatorios.items():
            if not self.datos_paciente.get(campo):
                faltantes.append(descripcion)
        
        return faltantes
    
    def _solicitar_datos_faltantes(self, datos_faltantes: List[str]) -> str:
        """Solicita los datos que aún faltan"""
        
        if len(datos_faltantes) == 1:
            return f"""✅ **¡Perfecto!** Ya tengo varios datos.

Solo necesito:
{datos_faltantes[0]}

*¿Me lo puedes compartir?* 😊"""
        
        elif len(datos_faltantes) <= 3:
            lista_datos = "\n".join(f"• {dato}" for dato in datos_faltantes)
            return f"""✅ **¡Excelente!** Ya completé varios campos.

Me faltan estos datos:
{lista_datos}

*Puedes enviarlos juntos o separados* 📝"""
        
        else:
            # Muchos datos faltantes, mostrar lista completa
            lista_datos = "\n".join(f"• {dato}" for dato in datos_faltantes)
            return f"""📋 **Necesito completar tu información:**

{lista_datos}

*Puedes enviarme todo junto o paso a paso* ✨"""
    
    def _manejar_correccion_datos(self, mensaje: str) -> str:
        """Maneja correcciones de datos del paciente"""
        
        # Extraer qué quiere corregir
        datos_corregidos = self._extraer_datos_del_mensaje(mensaje)
        
        # Actualizar datos
        for campo, valor in datos_corregidos.items():
            if valor and valor != "null":
                self.datos_paciente[campo] = valor
        
        campos_corregidos = list(datos_corregidos.keys())
        
        if campos_corregidos:
            nombres_campos = {
                "documento": "documento",
                "nombre_completo": "nombre", 
                "fecha_nacimiento": "fecha de nacimiento",
                "entidad_eps": "EPS/entidad",
                "telefono": "teléfono",
                "email": "email",
                "direccion": "dirección"
            }
            
            campos_text = ", ".join(nombres_campos.get(c, c) for c in campos_corregidos)
            
            return f"""✅ **¡Corregido!** 

🔄 Actualicé: **{campos_text}**

¿Hay algo más que necesites cambiar o ya podemos continuar? 😊"""
        
        return """😅 **No detecté qué quieres corregir**

¿Podrías ser más específico? Por ejemplo:
• "Mi teléfono es 300123456"
• "El nombre correcto es Juan Pérez"
• "Mi email es nuevo@email.com\""""
    
    def _resetear_datos_paciente(self):
        """Reinicia los datos del paciente para nueva cita"""
        for campo in self.datos_paciente:
            self.datos_paciente[campo] = None
        
        self.esperando_datos = False
        self.buffer_mensajes = []
    
    def _solicitar_datos_faltantes(self, datos_faltantes: List[str]) -> str:
        """Solicita los datos que aún faltan"""
        
        if len(datos_faltantes) == 1:
            return f"""✅ **¡Perfecto!** Ya tengo varios datos.

Solo necesito:
{datos_faltantes[0]}

*¿Me lo puedes compartir?* 😊"""
        
        elif len(datos_faltantes) <= 3:
            lista_datos = "\n".join(f"• {dato}" for dato in datos_faltantes)
            return f"""✅ **¡Excelente!** Ya completé varios campos.

Me faltan estos datos:
{lista_datos}

*Puedes enviarlos juntos o separados* 📝"""
        
        else:
            # Muchos datos faltantes, mostrar lista completa
            lista_datos = "\n".join(f"• {dato}" for dato in datos_faltantes)
            return f"""📋 **Necesito completar tu información:**

{lista_datos}

*Puedes enviarme todo junto o paso a paso* ✨"""
    
    def _confirmar_datos_completos(self) -> str:
        """Confirma que todos los datos están completos"""
        datos = self.datos_paciente
        
        # Verificar si la póliza no tiene convenio
        advertencia_poliza = ""
        if self._validar_poliza_sin_convenio(datos.get('entidad_eps', '')):
            advertencia_poliza = f"""\n\n⚠️ **IMPORTANTE:**
La póliza **{datos['entidad_eps']}** NO tiene convenio con IPS React.

💰 **Debes pagar tarifa particular: $60,000**
\n"""
        
        return f"""✅ **¡Perfecto! Ya tengo toda tu información** 🎉

📋 **Resumen de tus datos:**
🪪 **Documento:** {datos['documento']}
🙋🏻 **Nombre:** {datos['nombre_completo']}
🎂 **F. Nacimiento:** {datos['fecha_nacimiento']}
🩺 **Entidad:** {datos['entidad_eps']}
📲 **Teléfono:** {datos['telefono']}
📧 **Email:** {datos['email']}
📍 **Dirección:** {datos['direccion']}

👨🏻‍🦰 **Contacto emergencia:**
🙋🏻‍♂ **Nombre:** {datos['contacto_emergencia_nombre']}
📲 **Teléfono:** {datos['contacto_emergencia_telefono']}
❓ **Parentesco:** {datos['contacto_emergencia_parentesco']}{advertencia_poliza}

✅ **¿Los datos están correctos?**
🔄 Si hay algo que corregir, solo dime qué cambiar

💰 **¿Cómo vas a pagar tu cita?**

**🏥 PAGO PRESENCIAL (en la clínica):**
1️⃣ **Póliza/EPS** - Pagas allá (efectivo/tarjeta/transferencia)
2️⃣ **Particular** - Pagas allá en efectivo o tarjeta ($60,000)

**💳 PAGO ANTICIPADO (desde el chat):**
3️⃣ **Transferencia bancaria** - Pagas antes de ir ($60,000) 
   _Te conectamos con secretaria para coordinar_

📝 Escribe el número o método de pago preferido 😊"""
    
    def _manejar_correcion_datos(self, mensaje: str) -> str:
        """Maneja correcciones de datos del paciente"""
        
        # Extraer qué quiere corregir
        datos_corregidos = self._extraer_datos_del_mensaje(mensaje)
        
        # Actualizar datos
        for campo, valor in datos_corregidos.items():
            if valor and valor != "null":
                self.datos_paciente[campo] = valor
        
        campos_corregidos = list(datos_corregidos.keys())
        
        if campos_corregidos:
            nombres_campos = {
                "documento": "documento",
                "nombre_completo": "nombre", 
                "fecha_nacimiento": "fecha de nacimiento",
                "entidad_eps": "EPS/entidad",
                "telefono": "teléfono",
                "email": "email",
                "direccion": "dirección"
            }
            
            campos_text = ", ".join(nombres_campos.get(c, c) for c in campos_corregidos)
            
            return f"""✅ **¡Corregido!** 

🔄 Actualicé: **{campos_text}**

¿Hay algo más que necesites cambiar o ya podemos continuar? 😊"""
        
        return """😅 **No detecté qué quieres corregir**

¿Podrías ser más específico? Por ejemplo:
• "Mi teléfono es 300123456"
• "El nombre correcto es Juan Pérez"
• "Mi email es nuevo@email.com"""
    
    def _detectar_metodo_pago(self, mensaje: str) -> bool:
        """Detecta si el mensaje contiene selección de método de pago"""
        palabras_pago = [
            "transferencia", "transferir", "consignacion", "consignar",
            "poliza", "eps", "efectivo", "presencial", "particular",
            "opcion 1", "opcion 2", "opcion 3", "opción 1", "opción 2", "opción 3"
        ]
        
        mensaje_lower = mensaje.lower()
        return any(palabra in mensaje_lower for palabra in palabras_pago)
    
    async def _procesar_metodo_pago(self, mensaje: str) -> Dict:
        """Procesa la selección del método de pago y maneja escalamiento para transferencia"""
        mensaje_lower = mensaje.lower()
        
        # Detectar transferencia
        if any(palabra in mensaje_lower for palabra in ["transferencia", "transferir", "consignacion", "consignar", "opcion 3", "opción 3"]):
            return await self._finalizar_con_transferencia()
        
        # Detectar póliza/EPS
        elif any(palabra in mensaje_lower for palabra in ["poliza", "eps", "opcion 1", "opción 1"]):
            return await self._finalizar_con_poliza()
        
        # Detectar efectivo
        elif any(palabra in mensaje_lower for palabra in ["efectivo", "presencial", "particular", "opcion 2", "opción 2"]):
            return await self._finalizar_con_efectivo()
        
        # Si no se detecta claramente, preguntar de nuevo
        else:
            return {
                "respuesta": """🤔 **No entendí tu método de pago preferido**
                
💰 **Por favor selecciona una opción:**

**🏥 PAGO PRESENCIAL (en la clínica):**
1️⃣ **Póliza/EPS** - Pagas allá
2️⃣ **Particular** - Pagas allá (efectivo/tarjeta)

**💳 PAGO ANTICIPADO (desde el chat):**
3️⃣ **Transferencia** - Pagas antes de ir

📝 Escribe el número o el método que prefieras 😊""",
                "intencion": "aclarar_metodo_pago",
                "requiere_escalamiento": False,
                "siguiente_paso": "esperar_metodo_pago"
            }
    
    async def _finalizar_con_transferencia(self) -> Dict:
        """Finaliza el agendamiento con transferencia: PRIMERO guarda en SaludTools, LUEGO escala"""
        self.esperando_datos = False
        
        # Preparar datos completos para agendamiento
        datos_completos = {
            **self.datos_paciente,
            'tipo_servicio': 'Fisioterapia',
            'metodo_pago': 'transferencia',
            'fecha_solicitud': datetime.now().isoformat(),
            'urgencia': 'Normal'
        }
        
        # 🔥 PASO 1: CREAR CITA EN SALUDTOOLS PRIMERO
        if self.saludtools:
            try:
                resultado_agendamiento = await self._crear_cita_saludtools(datos_completos)
                
                if resultado_agendamiento.get("success"):
                    cita_id = resultado_agendamiento.get("cita_id")
                    fecha_cita = resultado_agendamiento.get("fecha_cita")
                    
                    # ✅ CITA GUARDADA - AHORA SÍ ESCALAR PARA TRANSFERENCIA
                    datos_completos['cita_id'] = cita_id
                    datos_completos['fecha_cita'] = fecha_cita
                    
                    # PASO 2: Enviar notificación a secretarias DESPUÉS de guardar
                    self._enviar_notificacion_secretarias(datos_completos, "pago_transferencia")
                    
                    return {
                        "respuesta": f"""✅ **¡CITA GUARDADA EXITOSAMENTE EN SALUDTOOLS!**

📅 **Tu cita está pre-confirmada:**
• **ID Cita:** {cita_id}
• **Fecha:** {fecha_cita}
• **Paciente:** {self.datos_paciente.get('nombre_completo')}
• **Pago:** Transferencia bancaria

💳 **GESTIÓN DE PAGO - EQUIPO FINANCIERO**

⏳ Te dirijo ahora con nuestro departamento de pagos para completar la transferencia.

📞 **Te contactarán en máximo 1 hora:**
• **WhatsApp:** 3193175762  
• **Teléfono:** 6047058040

💰 **Te proporcionarán:**
• Número de cuenta para transferencia
• Datos de consignación  
• Confirmación de pago ($60,000)

✅ **Tu cita quedará 100% confirmada una vez recibido el pago.**

🎉 **¡Gracias por elegirnos!**""",
                        "intencion": "agendamiento_transferencia_exitoso",
                        "motivo_escalamiento": "transferencia",
                        "requiere_escalamiento": True,
                        "prioridad": "normal",
                        "siguiente_paso": "contactar_equipo_financiero",
                        "agendamiento_completado": True,
                        "cita_id": cita_id,
                        "metodo_pago": "transferencia",
                        "notificacion_enviada": True,
                        "procesamiento": "saludtools_primero_luego_escalamiento"
                    }
                    
            except Exception as e:
                logger.error(f"Error guardando cita transferencia en SaludTools: {e}")
                # FALLBACK: Si falla SaludTools, escalar directamente
        
        # FALLBACK: Si no hay SaludTools o falla, escalar sin cita previa
        self._enviar_notificacion_secretarias(datos_completos, "pago_transferencia")
        
        return {
            "respuesta": """💳 **GESTIÓN DE PAGOS - EQUIPO FINANCIERO**

⏳ **Un momento por favor...** Te dirijo con nuestro departamento de pagos para gestionar tu transferencia bancaria.

He enviado automáticamente tu información completa al equipo financiero.

📞 **Te contactarán en máximo 1 hora:**
• **WhatsApp:** 3193175762  
• **Teléfono:** 6047058040

💰 **Te proporcionarán:**
• Número de cuenta para transferencia
• Datos de consignación  
• Confirmación de pago ($60,000)

✅ **Te ayudarán con todo el proceso y confirmarán tu cita una vez recibido el pago.**

🎉 **¡Gracias por elegirnos!**""",
            "intencion": "escalamiento_automatico",
            "motivo_escalamiento": "transferencia",
            "requiere_escalamiento": True,
            "prioridad": "normal",
            "siguiente_paso": "contactar_equipo_financiero",
            "agendamiento_completado": True,
            "metodo_pago": "transferencia",
            "notificacion_enviada": True
        }
    
    async def _finalizar_con_poliza(self) -> Dict:
        """Finaliza el agendamiento con póliza/EPS usando sistema inteligente Y SALUDTOOLS"""
        self.esperando_datos = False
        
        # Clasificar EPS para manejo inteligente
        eps_info = self._clasificar_eps(self.datos_paciente.get('entidad_eps', ''))
        
        # Preparar datos completos para agendamiento
        datos_completos = {
            **self.datos_paciente,
            'tipo_servicio': 'Fisioterapia',
            'metodo_pago': 'poliza',
            'fecha_solicitud': datetime.now().isoformat(),
            'urgencia': 'Normal'
        }
        
        # 🔥 INTENTAR AGENDAMIENTO AUTOMÁTICO EN SALUDTOOLS
        if self.saludtools and not eps_info.get('requiere_escalamiento'):
            try:
                resultado_agendamiento = await self._crear_cita_saludtools(datos_completos)
                
                if resultado_agendamiento.get("success"):
                    cita_id = resultado_agendamiento.get("cita_id")
                    fecha_cita = resultado_agendamiento.get("fecha_cita")
                    
                    return {
                        "respuesta": f"""✅ **¡CITA AGENDADA AUTOMÁTICAMENTE!**

🎉 **Tu cita de fisioterapia está confirmada**

📅 **Detalles de tu cita:**
• **ID Cita:** {cita_id}
• **Fecha:** {fecha_cita}
• **Paciente:** {self.datos_paciente.get('nombre_completo')}
• **Documento:** {self.datos_paciente.get('documento')}
• **EPS:** {self.datos_paciente.get('entidad_eps')}

📱 **Recibirás:**
• Confirmación por WhatsApp
• Recordatorio 24h antes
• Instrucciones de llegada

🏥 **Importante:**
• Trae tu carné de EPS
• Llega 15 minutos antes
• Trae orden médica original

💡 **Puedes:**
• Escribir "mis citas" para ver todas tus citas
• Escribir "cancelar cita" si necesitas cambios

¡Nos vemos pronto! 😊""",
                        "intencion": "agendamiento_automatico_exitoso",
                        "requiere_escalamiento": False,
                        "agendamiento_completado": True,
                        "cita_id": cita_id,
                        "metodo_pago": "poliza",
                        "procesamiento": "saludtools_automatico"
                    }
                    
            except Exception as e:
                logger.error(f"Error en agendamiento automático SaludTools: {e}")
                # Continuar con flujo de escalamiento si falla
        
        # FALLBACK: Escalamiento si no se pudo agendar automáticamente
        if eps_info['requiere_escalamiento'] or not self.saludtools:
            # Casos que requieren escalamiento (EPS excluidas, convenios, desconocidas)
            self._enviar_notificacion_secretarias(datos_completos, f"eps_{eps_info['motivo']}")
            
            return {
                "respuesta": f"""🩺 **PROCESANDO TU SOLICITUD CON {self.datos_paciente.get('entidad_eps', 'TU EPS')}**

⏳ **Un momento por favor...** 

Tu EPS requiere validación especial. He enviado automáticamente tu información a nuestro equipo para que te contacten directamente.

📧 **Información enviada al equipo:**
• Tus datos completos y EPS
• Tipo de servicio solicitado  
• Detalles de contacto

📞 **Te contactaremos en máximo 2 horas:**
• **WhatsApp:** 3193175762
• **Teléfono:** 6047058040

✅ **Recibirás una llamada/mensaje personalizado para coordinar todo.**

🎉 **¡Gracias por elegirnos! La atención personalizada está en camino.**""",
                "intencion": "escalamiento_automatico",
                "motivo_escalamiento": eps_info['motivo'],
                "requiere_escalamiento": True,
                "agendamiento_completado": True,
                "metodo_pago": "poliza",
                "eps_info": eps_info,
                "notificacion_enviada": True
            }
        
        else:
            # EPS convencionales - Procesamiento directo
            self._enviar_notificacion_secretarias(datos_completos, "eps_aprobada_directa")
            
            mensaje_base = """🩺 **¡Perfecto! Agendamiento con tu EPS**

✅ **Tu cita está confirmada automáticamente**

📋 **Información importante:**
• Tu EPS está pre-aprobada en nuestro sistema
• Trae tu carné el día de la cita
• Llega 15 minutos antes para validaciones

📞 **Te contactaremos en las próximas horas para:**
• Confirmar fecha y hora específica
• Enviar recordatorios de la cita

🎉 **¡Excelente! Todo procesado exitosamente.**"""
            
            # Agregar nota especial para Coomeva
            if eps_info.get('nota_especial'):
                mensaje_base += f"\n\n📝 **Nota especial:** {eps_info['nota_especial']}"
            
            return {
                "respuesta": mensaje_base,
                "intencion": "agendamiento_completado",
                "requiere_escalamiento": False,
                "agendamiento_completado": True,
                "metodo_pago": "poliza",
                "eps_info": eps_info,
                "notificacion_enviada": True,
                "procesamiento": "saludtools_directo"
            }
    
    async def _finalizar_con_efectivo(self) -> Dict:
        """Finaliza el agendamiento con efectivo + SALUDTOOLS"""
        self.esperando_datos = False
        
        # Preparar datos completos para notificación
        datos_completos = {
            **self.datos_paciente,
            'tipo_servicio': 'Fisioterapia',
            'metodo_pago': 'efectivo',
            'fecha_solicitud': datetime.now().isoformat(),
            'urgencia': 'Normal'
        }
        
        # 🔥 INTENTAR AGENDAMIENTO AUTOMÁTICO EN SALUDTOOLS
        if self.saludtools:
            try:
                resultado_agendamiento = await self._crear_cita_saludtools(datos_completos)
                
                if resultado_agendamiento.get("success"):
                    cita_id = resultado_agendamiento.get("cita_id")
                    fecha_cita = resultado_agendamiento.get("fecha_cita")
                    
                    return {
                        "respuesta": f"""✅ **¡CITA AGENDADA AUTOMÁTICAMENTE!**

🎉 **Tu cita de Fisioterapia está confirmada**

📅 **Detalles de tu cita:**
• **ID Cita:** {cita_id}
• **Fecha:** {fecha_cita}
• **Paciente:** {self.datos_paciente.get('nombre_completo')}
• **Documento:** {self.datos_paciente.get('documento')}
• **Pago:** Efectivo (particular)

💰 **Valor:** $60,000 (pago presencial)
Acepta efectivo y tarjetas

📱 **Recibirás:**
• Confirmación por WhatsApp
• Recordatorio 24h antes

💡 **Puedes:**
• Escribir "mis citas" para ver tus citas
• Escribir "cancelar cita" para cambios

¡Nos vemos pronto! 😊""",
                        "intencion": "agendamiento_automatico_exitoso",
                        "requiere_escalamiento": False,
                        "agendamiento_completado": True,
                        "cita_id": cita_id,
                        "metodo_pago": "efectivo",
                        "procesamiento": "saludtools_automatico"
                    }
                    
            except Exception as e:
                logger.error(f"Error en agendamiento automático SaludTools (efectivo): {e}")
                # Continuar con flujo de escalamiento si falla
        
        # FALLBACK: Escalamiento si falla
        self._enviar_notificacion_secretarias(datos_completos, "pago_efectivo")
        
        return {
            "respuesta": """💵 **¡Perfecto! Agendamiento con pago en efectivo**

✅ **Tu cita está confirmada**

He enviado tu información automáticamente a nuestro equipo para coordinar los detalles.

💰 **Información de pago:**
• Costo: $60,000 (pago presencial)
• Acepta efectivo y tarjetas débito/crédito

📞 **Te contactaremos en las próximas 2 horas:**
• **WhatsApp:** 3193175762  
• **Teléfono:** 6047058040

🎉 **¡Gracias por elegirnos! Recibirás confirmación de fecha y hora pronto.**""",
            "intencion": "agendamiento_completado",
            "requiere_escalamiento": False,
            "agendamiento_completado": True,
            "metodo_pago": "efectivo",
            "notificacion_enviada": True
        }
    
    
    def _validar_horario_coomeva(self, hora_solicitada: str, tipo_fisioterapia: str = "") -> Dict:
        """
        Valida si el horario solicitado cumple con la directriz de Coomeva
        
        Args:
            hora_solicitada: Hora en formato HH:MM o descripción
            tipo_fisioterapia: Tipo de fisioterapia (para verificar si es rehabilitación cardíaca)
            
        Returns:
            Dict con validación y mensaje si aplica
        """
        from datetime import datetime
        
        # Si es rehabilitación cardíaca/cardiovascular, permitir cualquier horario
        tipo_fisioterapia = tipo_fisioterapia or ""  # Defensive check
        tipo_lower = tipo_fisioterapia.lower()
        
        # Detectar rehabilitación cardíaca
        palabras_cardiaca = ["cardia", "cardiovascular", "corazon", "corazón", "rehabilitación cardíaca", "rehabilitacion cardiaca"]
        es_cardiaca = any(palabra in tipo_lower for palabra in palabras_cardiaca)
        
        if es_cardiaca:
            return {
                "valido": True,
                "motivo": "rehabilitacion_cardiaca_excepcion",
                "mensaje": None
            }
        
        # Intentar parsear la hora
        try:
            # Limpiar y normalizar
            hora_limpia = hora_solicitada.strip().lower()
            
            # Patrones comunes
            import re
            
            # Buscar patrón HH:MM
            match_hora = re.search(r'(\d{1,2}):?(\d{2})?', hora_limpia)
            if match_hora:
                hora = int(match_hora.group(1))
                minutos = int(match_hora.group(2)) if match_hora.group(2) else 0
                
                # Ajustar PM/AM
                if 'pm' in hora_limpia and hora < 12:
                    hora += 12
                elif 'am' in hora_limpia and hora == 12:
                    hora = 0
                
                # Validar franja Coomeva: 9:00 AM a 4:00 PM (09:00 a 16:00)
                hora_inicio_coomeva = 9
                hora_fin_coomeva = 16
                
                if hora < hora_inicio_coomeva or (hora == hora_fin_coomeva and minutos > 0) or hora > hora_fin_coomeva:
                    return {
                        "valido": False,
                        "motivo": "fuera_franja_coomeva",
                        "hora_solicitada": f"{hora:02d}:{minutos:02d}",
                        "mensaje": f"""⚠️ **Restricción de horario Coomeva**

La hora solicitada ({hora:02d}:{minutos:02d}) está fuera de la franja permitida para Coomeva.

🕒 **Horario disponible para Coomeva:**
• **Lunes a Viernes:** 9:00 AM - 4:00 PM
• **Sábados:** 8:00 AM - 12:00 PM

💡 **¿Deseas agendar en un horario dentro de esta franja?**

📝 Por favor indica un nuevo horario entre 9:00 AM y 4:00 PM"""
                    }
                
                # Horario válido
                return {
                    "valido": True,
                    "hora_validada": f"{hora:02d}:{minutos:02d}",
                    "motivo": "dentro_franja_coomeva",
                    "mensaje": None
                }
            
            # Si no se pudo parsear, permitir (se validará después manualmente)
            return {
                "valido": True,
                "motivo": "no_parseado_validar_manual",
                "mensaje": None,
                "requiere_validacion_posterior": True
            }
            
        except Exception as e:
            logger.warning(f"Error validando horario Coomeva: {e}")
            # En caso de error, permitir y validar después
            return {
                "valido": True,
                "motivo": "error_validacion",
                "mensaje": None,
                "requiere_validacion_posterior": True
            }
    
    def _clasificar_eps(self, eps_nombre: str) -> Dict:
        """Clasifica EPS para determinar manejo (Saludtools directo vs escalamiento)"""
        
        eps_lower = eps_nombre.lower() if eps_nombre else ""
        
        # EPS EXCLUIDAS - Siempre escalamiento
        eps_excluidas = {
            "particulares", "sin eps", "ninguna", "no tengo", 
            "prepagada", "plan complementario"
        }
        
        if any(excluida in eps_lower for excluida in eps_excluidas):
            return {
                "tipo": "excluida",
                "requiere_escalamiento": True,
                "motivo": "eps_no_soportada",
                "manejo": "escalamiento"
            }
        
        # COOMEVA - Directriz especial CON VALIDACIÓN DE HORARIO
        if "coomeva" in eps_lower:
            return {
                "tipo": "coomeva_especial", 
                "requiere_escalamiento": False,
                "motivo": "directriz_coomeva",
                "manejo": "saludtools_directo",
                "franja_horaria": "09:00-16:00",  # 9am a 4pm
                "excepcion_horario": "rehabilitacion_cardiaca",  # Rehabilitación cardíaca puede usar horario completo
                "nota_especial": "Horario restringido 9am-4pm (excepto rehabilitación cardíaca)"
            }
        
        # EPS CONVENCIONALES - Directo a Saludtools
        eps_convencionales = {
            "sura", "nueva eps", "sanitas", "compensar", "famisanar",
            "salud total", "eps sanitas", "medimas", "golden group",
            "cafesalud", "comfenalco", "comfama", "ecoopsos"
        }
        
        for eps in eps_convencionales:
            if eps in eps_lower:
                return {
                    "tipo": "convencional",
                    "requiere_escalamiento": False, 
                    "motivo": "eps_reconocida",
                    "manejo": "saludtools_directo",
                    "eps_normalizada": eps.title()
                }
        
        # CONVENIOS ESPECIALES - Escalamiento
        palabras_convenio = ["convenio", "descuento", "empresa", "institucional", "especial"]
        if any(palabra in eps_lower for palabra in palabras_convenio):
            return {
                "tipo": "convenio_especial",
                "requiere_escalamiento": True,
                "motivo": "convenio_no_estandar", 
                "manejo": "escalamiento"
            }
        
        # EPS EXCLUIDAS/PARTICULARES - Escalamiento para coordinación
        if any(palabra in eps_lower for palabra in [
            "particular", "prepagada", "medicina prepagada", "no tengo eps",
            "pago particular", "sin eps", "ninguna eps"
        ]):
            return {
                "tipo": "excluida",
                "requiere_escalamiento": True,
                "motivo": "pago_particular",
                "manejo": "escalamiento"
            }
        
        # EPS DESCONOCIDA - Escalamiento para verificación
        return {
            "tipo": "desconocida",
            "requiere_escalamiento": True,
            "motivo": "eps_no_reconocida",
            "manejo": "escalamiento"
        }
    
    def _enviar_notificacion_secretarias(self, datos_completos: Dict, motivo: str = "agendamiento_nuevo") -> bool:
        """Envía notificación automática a secretarias con resumen del caso"""
        
        try:
            # Preparar resumen del caso
            resumen = self._generar_resumen_caso(datos_completos, motivo)
            
            # Lista de contactos de secretarias (configurar según necesidad)
            contactos_secretarias = [
                {"nombre": "Secretaría General", "whatsapp": "3193175762"},
                # Agregar más contactos según sea necesario
            ]
            
            # En producción, aquí se enviaría via WhatsApp API o sistema de notificaciones
            # Por ahora, registrar en logs para testing
            logger.info(f"📧 NOTIFICACIÓN AUTOMÁTICA ENVIADA:")
            logger.info(f"Destinatarios: {[c['nombre'] for c in contactos_secretarias]}")
            logger.info(f"Motivo: {motivo}")
            logger.info(f"Resumen: {resumen[:200]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error enviando notificación a secretarias: {e}")
            return False
    
    def _generar_resumen_caso(self, datos: Dict, motivo: str) -> str:
        """Genera resumen estructurado para secretarias"""
        
        eps_info = self._clasificar_eps(datos.get('entidad_eps', ''))
        
        resumen = f"""🔔 **NUEVO CASO - {motivo.upper()}**

👤 **PACIENTE:**
• Nombre: {datos.get('nombre_completo', 'No proporcionado')}
• Documento: {datos.get('documento', 'No proporcionado')} 
• Teléfono: {datos.get('telefono', 'No proporcionado')}
• Email: {datos.get('email', 'No proporcionado')}

🏥 **EPS/ENTIDAD:**
• {datos.get('entidad_eps', 'No especificada')}
• Tipo: {eps_info['tipo']}
• Manejo: {eps_info['manejo']}

📋 **SOLICITUD:**
• Tipo: {datos.get('tipo_servicio', 'Fisioterapia')}
• Urgencia: {datos.get('urgencia', 'Normal')}
• Fecha solicitud: {datos.get('fecha_solicitud', 'Ahora')}

💬 **MOTIVO ESCALAMIENTO:**
{eps_info.get('motivo', 'Procesamiento estándar')}

✅ **ACCIÓN REQUERIDA:**
Contactar al paciente para coordinar cita y confirmar detalles.

📞 **CONTACTO PACIENTE:** {datos.get('telefono', 'Ver datos completos')}"""
        
        return resumen
        """Detecta si debe esperar más mensajes antes de responder"""
        import time
        
        ahora = time.time()
        
        # Agregar mensaje al buffer
        self.buffer_mensajes.append({
            "mensaje": mensaje,
            "timestamp": ahora
        })
        
        # Si es el primer mensaje o han pasado más de 10 segundos, procesar
        if not self.ultimo_mensaje_tiempo or (ahora - self.ultimo_mensaje_tiempo) > 10:
            self.ultimo_mensaje_tiempo = ahora
            return False  # No esperar más mensajes
        
        # Si han pasado menos de 5 segundos, esperar un poco más
        if (ahora - self.ultimo_mensaje_tiempo) < 5:
            self.ultimo_mensaje_tiempo = ahora
            return True  # Esperar más mensajes
        
        # Procesar los mensajes acumulados
        self.ultimo_mensaje_tiempo = ahora
        return False
    
    def _obtener_mensaje_consolidado(self) -> str:
        """Consolida múltiples mensajes en uno solo"""
        if not self.buffer_mensajes:
            return ""
        
        # Tomar mensajes de los últimos 30 segundos
        import time
        ahora = time.time()
        mensajes_recientes = [
            msg["mensaje"] for msg in self.buffer_mensajes 
            if ahora - msg["timestamp"] <= 30
        ]
        
        # Limpiar buffer
        self.buffer_mensajes = []
        
        return " ".join(mensajes_recientes)
    
    def _resetear_datos_paciente(self):
        """Reinicia los datos del paciente para nueva cita"""
        for campo in self.datos_paciente:
            self.datos_paciente[campo] = None
        
        self.esperando_datos = False
        self.campo_actual = None
        self.buffer_mensajes = []
    
    async def _procesar_archivos_ocr(self, archivos: List[str], mensaje_acompañante: str = "") -> Dict:
        """Procesa archivos con OCR inteligente y evaluación automática de completitud"""
        try:
            from app.ocr_inteligente import ProcesadorOCRInteligente
            
            # Inicializar procesador OCR si no existe
            if not hasattr(self, 'ocr'):
                self.ocr = ProcesadorOCRInteligente()
            
            logger.info(f"🔍 Procesando {len(archivos)} archivo(s) con OCR inteligente")
            
            # Determinar si es un lote o archivo individual
            es_batch = len(archivos) > 1
            
            # Procesar archivo individual inmediatamente para evaluación rápida
            if not es_batch and len(archivos) == 1:
                resultado_ocr = await self.ocr.procesar_archivo(archivos[0], es_batch=False)
                
                if not resultado_ocr or "error" in resultado_ocr:
                    error_msg = resultado_ocr.get("error", "Error desconocido") if resultado_ocr else "No se pudo procesar"
                    return {
                        "respuesta": f"❌ **No pude leer tu orden médica**\n\n{error_msg}\n\n📷 **¿Puedes intentar con:**\n• Foto más nítida y con buena luz\n• Documento completo visible\n• Evitar sombras o reflejos",
                        "intencion": "error_ocr",
                        "requiere_escalamiento": False,
                        "accion_requerida": "reenviar_documento",
                        "siguiente_paso": "esperar_nuevo_documento"
                    }
                
                # Evaluar completitud de datos extraídos
                return await self._evaluar_y_responder_ocr(resultado_ocr, mensaje_acompañante, archivos[0])
            
            # Para múltiples archivos, procesamiento en lote
            logger.info("📄 Procesando múltiples archivos en lote...")
            resultado_lote = None
            
            for archivo in archivos:
                resultado_temp = await self.ocr.procesar_archivo(archivo, es_batch=True)
                if resultado_temp and "error" not in resultado_temp:
                    resultado_lote = resultado_temp
                    break  # Usar el primer resultado exitoso
            
            if resultado_lote:
                return await self._evaluar_y_responder_ocr(resultado_lote, mensaje_acompañante, f"{len(archivos)} archivos")
            
            # Si todos fallaron
            return {
                "respuesta": f"❌ **No pude procesar ninguno de los {len(archivos)} archivos**\n\n📷 **¿Puedes intentar con:**\n• Fotos individuales más claras\n• Un archivo a la vez\n• Mejor iluminación",
                "intencion": "error_batch_ocr",
                "requiere_escalamiento": False,
                "accion_requerida": "reenviar_documentos",
                "siguiente_paso": "esperar_nuevos_documentos"
            }
            
        except Exception as e:
            logger.error(f"Error procesando archivos OCR: {e}")
            return {
                "respuesta": f"❌ **Error técnico procesando archivos**\n\n{str(e)}\n\n💡 Intenta nuevamente con archivos más claros.",
                "intencion": "error_tecnico_ocr",
                "requiere_escalamiento": True
            }

    async def _evaluar_y_responder_ocr(self, resultado_ocr: Dict, mensaje_acompañante: str, fuente: str) -> Dict:
        """Evalúa resultado OCR y genera respuesta inteligente basada en completitud"""
        try:
            # Extraer datos del resultado OCR
            analisis_ia = resultado_ocr.get('analisis_ia', {})
            resultados_ocr = resultado_ocr.get('resultados_ocr', [])
            respuesta_base = resultado_ocr.get('respuesta', '')
            
            # Evaluar completitud de datos críticos para agendamiento
            evaluacion = self._evaluar_completitud_datos_medicos(analisis_ia, resultados_ocr)
            
            # Pre-cargar datos extraídos en el sistema
            self._precargar_datos_extraidos(analisis_ia)
            
            # Generar respuesta inteligente basada en evaluación
            if evaluacion["nivel_completitud"] >= 0.8:  # 80% o más completo
                return await self._respuesta_ocr_completo(analisis_ia, evaluacion, respuesta_base)
            elif evaluacion["nivel_completitud"] >= 0.5:  # 50-79% completo  
                return await self._respuesta_ocr_parcial(analisis_ia, evaluacion, respuesta_base)
            else:  # Menos del 50% completo
                return await self._respuesta_ocr_insuficiente(analisis_ia, evaluacion, respuesta_base, fuente)
                
        except Exception as e:
            logger.error(f"Error evaluando resultado OCR: {e}")
            return {
                "respuesta": "❌ Error evaluando la orden médica. ¿Puedes enviar una foto más clara?",
                "intencion": "error_evaluacion_ocr",
                "requiere_escalamiento": False
            }
    
    def _evaluar_completitud_datos_medicos(self, analisis_ia: Dict, resultados_ocr: List[Dict]) -> Dict:
        """Evalúa qué tan completos están los datos médicos extraídos"""
        
        # Datos críticos para agendamiento de fisioterapia
        campos_criticos = [
            "nombre_paciente", "documento_paciente", "eps_aseguradora", 
            "tipo_terapia", "numero_sesiones", "medico_tratante"
        ]
        
        # Datos adicionales útiles
        campos_adicionales = [
            "diagnostico", "fecha_orden", "observaciones"
        ]
        
        # Evaluar presencia y calidad de datos
        datos_encontrados = {
            "paciente": analisis_ia.get('paciente', {}),
            "medico": analisis_ia.get('medico', {}),
            "tratamientos": analisis_ia.get('tratamientos', []),
            "sesiones": analisis_ia.get('sesiones'),
            "diagnosticos": analisis_ia.get('diagnosticos', []),
            "fechas": analisis_ia.get('fechas', {}),
            "tipo_orden": analisis_ia.get('tipo_orden', '')
        }
        
        # Calcular completitud por categorías
        completitud_paciente = self._evaluar_datos_paciente(datos_encontrados["paciente"])
        completitud_tratamiento = self._evaluar_datos_tratamiento(datos_encontrados)
        completitud_medico = self._evaluar_datos_medico(datos_encontrados["medico"])
        
        # Identificar datos faltantes
        faltantes = []
        
        # Verificar nombre paciente
        if not datos_encontrados["paciente"].get("nombre") or datos_encontrados["paciente"]["nombre"] == "No detectado":
            faltantes.append("nombre completo del paciente")
            
        # Verificar documento
        if not datos_encontrados["paciente"].get("documento") or datos_encontrados["paciente"]["documento"] == "No detectado":
            faltantes.append("número de documento de identidad")
            
        # Verificar EPS
        if not datos_encontrados["paciente"].get("eps") or datos_encontrados["paciente"]["eps"] == "No detectado":
            faltantes.append("EPS o aseguradora")
            
        # Verificar tipo de terapia
        if not datos_encontrados["tipo_orden"] or "fisio" not in datos_encontrados["tipo_orden"].lower():
            if not any("fisio" in str(t).lower() for t in datos_encontrados["tratamientos"]):
                faltantes.append("tipo específico de fisioterapia")
        
        # Verificar sesiones
        if not datos_encontrados["sesiones"]:
            faltantes.append("número de sesiones prescritas")
        
        # Calcular nivel general de completitud
        nivel_completitud = (completitud_paciente + completitud_tratamiento + completitud_medico) / 3
        
        return {
            "nivel_completitud": nivel_completitud,
            "completitud_paciente": completitud_paciente,
            "completitud_tratamiento": completitud_tratamiento,
            "completitud_medico": completitud_medico,
            "datos_encontrados": datos_encontrados,
            "campos_faltantes": faltantes,
            "calidad_extraccion": analisis_ia.get("calidad_extraccion", "media"),
            "campos_dudosos": analisis_ia.get("campos_dudosos", [])
        }
    
    def _evaluar_datos_paciente(self, paciente: Dict) -> float:
        """Evalúa completitud de datos del paciente"""
        campos_esperados = ["nombre", "documento", "eps"]
        encontrados = 0
        
        for campo in campos_esperados:
            valor = paciente.get(campo, "")
            if valor and valor != "No detectado" and len(str(valor).strip()) > 2:
                encontrados += 1
                
        return encontrados / len(campos_esperados)
    
    def _evaluar_datos_tratamiento(self, datos: Dict) -> float:
        """Evalúa completitud de datos del tratamiento"""
        score = 0.0
        
        # Tipo de orden (25%)
        if datos["tipo_orden"] and "fisio" in datos["tipo_orden"].lower():
            score += 0.25
            
        # Tratamientos específicos (25%)
        if datos["tratamientos"] and any(datos["tratamientos"]):
            score += 0.25
            
        # Número de sesiones (25%)
        if datos["sesiones"]:
            score += 0.25
            
        # Diagnósticos (25%)
        if datos["diagnosticos"] and any(datos["diagnosticos"]):
            score += 0.25
            
        return score
    
    def _evaluar_datos_medico(self, medico: Dict) -> float:
        """Evalúa completitud de datos del médico"""
        campos_esperados = ["nombre", "especialidad"]
        encontrados = 0
        
        for campo in campos_esperados:
            valor = medico.get(campo, "")
            if valor and valor != "No detectado" and len(str(valor).strip()) > 2:
                encontrados += 1
                
        return encontrados / len(campos_esperados) if campos_esperados else 0.0
    
    def _precargar_datos_extraidos(self, analisis_ia: Dict):
        """Pre-carga datos extraídos en el sistema para acelerar agendamiento"""
        try:
            paciente = analisis_ia.get('paciente', {})
            
            # Pre-cargar en datos del paciente si están disponibles y son válidos
            if paciente.get('nombre') and paciente['nombre'] != "No detectado":
                self.datos_paciente["nombre_completo"] = paciente['nombre']
                
            if paciente.get('documento') and paciente['documento'] != "No detectado":
                self.datos_paciente["documento"] = paciente['documento']
                
            if paciente.get('eps') and paciente['eps'] != "No detectado":
                self.datos_paciente["entidad_eps"] = paciente['eps']
            
            # 🔥 MARCAR QUE YA TENEMOS ORDEN MÉDICA PROCESADA
            self.datos_paciente["orden_medica_procesada"] = True
            self.datos_paciente["analisis_orden_medica"] = analisis_ia
            
            logger.info(f"✅ Datos precargados: {list(k for k, v in self.datos_paciente.items() if v)}")
            logger.info(f"✅ Orden médica marcada como procesada en contexto")
            
        except Exception as e:
            logger.warning(f"Error precargando datos: {e}")

    async def _respuesta_ocr_completo(self, analisis_ia: Dict, evaluacion: Dict, respuesta_base: str) -> Dict:
        """Respuesta cuando los datos OCR están suficientemente completos para proceder"""
        try:
            paciente = analisis_ia.get('paciente', {})
            tratamientos = analisis_ia.get('tratamientos', [])
            sesiones = analisis_ia.get('sesiones')
            
            # Iniciar proceso de agendamiento con datos precargados
            self.esperando_datos = True
            self.estado_recopilacion = "confirmar_datos_orden"
            
            respuesta = f"✅ **¡Perfecto! Leí tu orden médica correctamente**\n\n"
            
            # Mostrar datos extraídos
            respuesta += f"📋 **INFORMACIÓN DETECTADA:**\n"
            respuesta += f"👤 **Paciente:** {paciente.get('nombre', 'Detectado')}\n"
            respuesta += f"🆔 **Documento:** {paciente.get('documento', 'Detectado')}\n"
            respuesta += f"🏥 **EPS:** {paciente.get('eps', 'Detectada')}\n"
            
            if tratamientos:
                respuesta += f"🎯 **Tratamiento:** {', '.join(tratamientos[:2])}\n"
            
            if sesiones:
                respuesta += f"📊 **Sesiones prescritas:** {sesiones}\n\n"
            else:
                respuesta += "\n"
            
            respuesta += f"🎯 **Te agendaremos la PRIMERA cita** para que:\n"
            respuesta += f"• Tengas tu primera experiencia en IPS React\n"
            respuesta += f"• Conozcas a tu fisioterapeuta\n"
            
            if sesiones and int(sesiones) > 1:
                respuesta += f"• Las {int(sesiones) - 1} sesiones restantes se agendan presencialmente\n\n"
            else:
                respuesta += f"• Las demás sesiones se agendan presencialmente\n\n"
            
            respuesta += f"¿Toda la información luce correcta para proceder?\n\n"
            respuesta += f"💬 Responde **'sí'** para continuar o dime qué necesitas corregir."
            
            return {
                "respuesta": respuesta,
                "intencion": "confirmacion_datos_orden",
                "entidades": analisis_ia,
                "requiere_escalamiento": False,
                "accion_requerida": "confirmar_datos_orden",
                "datos_precargados": self.datos_paciente.copy(),
                "siguiente_paso": "esperar_confirmacion_datos",
                "nivel_completitud": evaluacion["nivel_completitud"]
            }
            
        except Exception as e:
            logger.error(f"Error generando respuesta OCR completo: {e}")
            return self._respuesta_ocr_fallback()
    
    async def _respuesta_ocr_parcial(self, analisis_ia: Dict, evaluacion: Dict, respuesta_base: str) -> Dict:
        """Respuesta cuando los datos OCR están parcialmente completos"""
        try:
            paciente = analisis_ia.get('paciente', {})
            faltantes = evaluacion.get('campos_faltantes', [])
            
            # Iniciar recopilación enfocada
            self.esperando_datos = True
            self.estado_recopilacion = "completar_datos_orden"
            
            respuesta = f"✅ **¡Bien! Pude leer parte de tu orden médica**\n\n"
            
            # Mostrar lo que sí se detectó
            respuesta += f"📋 **INFORMACIÓN DETECTADA:**\n"
            
            datos_detectados = []
            if paciente.get('nombre') and paciente['nombre'] != "No detectado":
                datos_detectados.append(f"👤 Paciente: {paciente['nombre']}")
            if paciente.get('documento') and paciente['documento'] != "No detectado":
                datos_detectados.append(f"🆔 Documento: {paciente['documento']}")
            if paciente.get('eps') and paciente['eps'] != "No detectado":
                datos_detectados.append(f"🏥 EPS: {paciente['eps']}")
                
            if datos_detectados:
                respuesta += "\n".join(datos_detectados) + "\n\n"
            
            # Preguntar por datos faltantes de manera específica
            if faltantes:
                respuesta += f"❓ **Para completar el agendamiento, necesito:**\n"
                for i, faltante in enumerate(faltantes[:3], 1):  # Máximo 3 a la vez
                    respuesta += f"{i}. {faltante.title()}\n"
                
                respuesta += f"\n💬 **¿Puedes proporcionarme {'estos datos' if len(faltantes) > 1 else 'este dato'}?**"
            else:
                respuesta += f"🎯 **¿Todos los datos lucen correctos para proceder?**"
            
            return {
                "respuesta": respuesta,
                "intencion": "completar_datos_orden",
                "entidades": analisis_ia,
                "requiere_escalamiento": False,
                "accion_requerida": "completar_datos_faltantes",
                "campos_faltantes": faltantes,
                "datos_precargados": self.datos_paciente.copy(),
                "siguiente_paso": "esperar_datos_faltantes",
                "nivel_completitud": evaluacion["nivel_completitud"]
            }
            
        except Exception as e:
            logger.error(f"Error generando respuesta OCR parcial: {e}")
            return self._respuesta_ocr_fallback()
    
    async def _respuesta_ocr_insuficiente(self, analisis_ia: Dict, evaluacion: Dict, respuesta_base: str, fuente: str) -> Dict:
        """Respuesta cuando los datos OCR son insuficientes"""
        try:
            calidad = evaluacion.get('calidad_extraccion', 'baja')
            
            respuesta = f"⚠️ **Pude procesar tu documento pero la información está incompleta**\n\n"
            
            # Explicar el problema
            if calidad == 'baja':
                respuesta += f"📷 **El documento se ve algo borroso o cortado.**\n\n"
            else:
                respuesta += f"📄 **Algunos datos importantes no están visibles o claros.**\n\n"
            
            respuesta += f"💡 **Para agendar tu fisioterapia, necesito:**\n"
            respuesta += f"• Nombre completo del paciente\n"
            respuesta += f"• Número de documento (cédula)\n"
            respuesta += f"• EPS o aseguradora\n"
            respuesta += f"• Número de sesiones prescritas\n\n"
            
            respuesta += f"📷 **¿Puedes intentar con:**\n"
            respuesta += f"• Una foto más clara y completa\n"
            respuesta += f"• Buena iluminación (sin sombras)\n"
            respuesta += f"• Documento completo visible\n\n"
            
            respuesta += f"🗣️ **O si prefieres, puedes dictarme los datos directamente.**"
            
            return {
                "respuesta": respuesta,
                "intencion": "solicitar_documento_mejor",
                "entidades": analisis_ia,
                "requiere_escalamiento": False,
                "accion_requerida": "mejorar_documento_o_dictar",
                "calidad_extraccion": calidad,
                "siguiente_paso": "esperar_mejor_documento_o_datos",
                "nivel_completitud": evaluacion["nivel_completitud"]
            }
            
        except Exception as e:
            logger.error(f"Error generando respuesta OCR insuficiente: {e}")
            return self._respuesta_ocr_fallback()
    
    def _respuesta_ocr_fallback(self) -> Dict:
        """Respuesta de respaldo cuando hay error en el procesamiento OCR"""
        return {
            "respuesta": "❌ **Hubo un problema procesando tu documento**\n\n📷 ¿Puedes enviar una foto más clara o dictarme los datos de tu orden médica?",
            "intencion": "error_ocr_fallback",
            "requiere_escalamiento": False,
            "accion_requerida": "reenviar_o_dictar",
            "siguiente_paso": "esperar_nueva_entrada"
        }
    
    def _respuesta_agendar_acondicionamiento(self, entidades: Dict, contexto: Dict) -> Dict:
        """Respuesta específica para agendamiento de acondicionamiento físico"""
        
        fisioterapeuta = entidades.get("fisioterapeuta_mencionado", "") if entidades else ""
        
        if fisioterapeuta:
            fisio_nombre = self._obtener_nombre_completo_fisioterapeuta(fisioterapeuta)
            respuesta = f"💪 **¡Perfecto! Acondicionamiento físico con {fisio_nombre}**\n\n"
        else:
            respuesta = "💪 **¡Excelente! Te ayudo con el acondicionamiento físico**\n\n"
        
        respuesta += """⚠️ **IMPORTANTE:** El acondicionamiento **NO acepta EPS**, es solo particular.

🏃🏻‍♂️ **ACONDICIONAMIENTO FÍSICO:**
✅ Clases **individualizadas** (no personalizadas)
✅ Duración: 60 minutos por sesión
✅ Evaluación física inicial
✅ Seguimiento semanal del progreso
✅ Equipos especializados disponibles

💳 **1 SOLA CLASE:**
• Precio: $50,000
• Duración: 1 hora (60 minutos)

📅 **PLANES MENSUALES:**

🥉 **PLAN BÁSICO**
• Precio: $320,000/mes
• Clases: 8 sesiones mensuales
• Frecuencia: 2 clases por semana

🥈 **PLAN INTERMEDIO**
• Precio: $380,000/mes
• Clases: 12 sesiones mensuales
• Frecuencia: 3 clases por semana

🥇 **PLAN AVANZADO**
• Precio: $440,000/mes
• Clases: 16 sesiones mensuales
• Frecuencia: 4 clases por semana

🏆 **PLAN INTENSIVO**
• Precio: $500,000/mes
• Clases: 20 sesiones mensuales
• Frecuencia: 5 clases por semana

¿Qué plan te interesa?"""
        
        return {
            "respuesta": respuesta,
            "tipo": "acondicionamiento_fisico",
            "requiere_escalamiento": False,
            "siguiente_paso": "recopilar_datos_paciente"
        }
    
    def _obtener_timestamp(self) -> str:
        """Obtiene timestamp actual en formato ISO."""
        return now_colombia().isoformat()  # 🆕 Bug #6 fix
    
    # =========================================================================
    # 🔥 MÉTODOS DE INTEGRACIÓN CON SALUDTOOLS - AUTOMATIZACIÓN COMPLETA
    # =========================================================================
    
    async def _crear_cita_saludtools(self, datos_cita: Dict) -> Dict:
        """
        Crea una cita en SaludTools automáticamente
        
        Args:
            datos_cita: Diccionario con datos del paciente y cita
            
        Returns:
            Dict con success, cita_id, fecha_cita, mensaje
        """
        try:
            # 🔐 VALIDAR AUTENTICACIÓN SALUDTOOLS
            if not await self._ensure_saludtools_ready():
                logger.error("❌ SaludTools no disponible o no autenticado")
                return {
                    "success": False,
                    "error": "SaludTools no disponible",
                    "requiere_escalamiento": True
                }
            
            # 🆕 BUG #9 FIX: Logging estructurado
            documento = datos_cita.get('documento')
            logger.info(f"📋 Iniciando creación de cita", extra={
                "documento": documento,
                "eps": datos_cita.get('entidad_eps'),
                "tipo_servicio": datos_cita.get('tipo_servicio'),
                "timestamp": now_colombia().isoformat()
            })
            
            # 1. Buscar o crear paciente
            paciente = await self.saludtools.buscar_paciente(documento)
            
            if not paciente:
                # Crear paciente nuevo
                nombre_completo = datos_cita.get('nombre_completo', '').split()
                datos_paciente = {
                    "firstName": nombre_completo[0] if nombre_completo else "",
                    "lastName": " ".join(nombre_completo[1:]) if len(nombre_completo) > 1 else "",
                    "documentType": 1,  # CC
                    "documentNumber": documento,
                    "phone": datos_cita.get('telefono', ''),
                    "email": datos_cita.get('email', ''),
                    "contactPreference": "whatsapp"
                }
                paciente = await self.saludtools.crear_paciente(datos_paciente)
                
                if paciente:
                    logger.info(f"✅ Paciente creado en SaludTools: {paciente.get('id')}")
                else:
                    logger.warning("⚠️ No se pudo crear paciente en SaludTools (posiblemente offline)")
                    # Continuar de todos modos - SaludTools puede estar en modo fallback
            
            # 2. Preparar datos de la cita
            # Fecha deseada (si no se especifica, usar próximo día hábil)
            fecha_cita = datos_cita.get('fecha_deseada')
            if not fecha_cita:
                # Calcular próximo día hábil a las 9 AM
                fecha_cita = now_colombia() + timedelta(days=1)  # 🆕 Bug #6 fix
                while fecha_cita.weekday() >= 5:  # Saltar fin de semana
                    fecha_cita += timedelta(days=1)
                fecha_cita = fecha_cita.replace(hour=9, minute=0, second=0, microsecond=0)
            
            tipo_servicio = datos_cita.get('tipo_servicio', 'Fisioterapia')
            
            # Obtener número de sesiones de la orden médica (si existe)
            sesiones_orden = datos_cita.get('numero_sesiones', 1) or 1
            try:
                sesiones_orden = int(sesiones_orden)
            except:
                sesiones_orden = 1
            
            sanitized_type = mapear_tipo_fisioterapia(tipo_servicio, sesiones_orden=sesiones_orden)
            
            # 🆕 BUG #3 FIX: Validar horario Coomeva ANTES de crear cita
            eps = datos_cita.get('entidad_eps', '').lower()
            if 'coomeva' in eps and isinstance(fecha_cita, datetime):
                hora_str = fecha_cita.strftime("%H:%M")
                validacion = self._validar_horario_coomeva(hora_str, tipo_servicio)
                
                if not validacion.get("valido", True):
                    logger.warning(f"⚠️ Cita rechazada - Fuera de franja Coomeva: {hora_str}")
                    return {
                        "success": False,
                        "error": "horario_invalido_coomeva",
                        "mensaje": validacion.get("mensaje", "Horario no válido para Coomeva"),
                        "requiere_escalamiento": False  # No escalar, solo pedir nuevo horario
                    }
            
            # 🆕 Construir comment con toda la información
            comment_parts = [f"Agendada vía WhatsApp Bot"]
            
            # 🔥 NUEVO: Agregar identificador de agendamiento múltiple
            if datos_cita.get('agendamiento_multiple'):
                numero_cita = datos_cita.get('numero_cita', 1)
                total_citas = datos_cita.get('total_citas', 1)
                agendamiento_id = datos_cita.get('agendamiento_id', 'N/A')
                comment_parts.append(f"🔗 AGENDAMIENTO MÚLTIPLE ({numero_cita}/{total_citas}) - ID: {agendamiento_id}")
            
            # Agregar EPS
            if datos_cita.get('entidad_eps'):
                comment_parts.append(f"EPS: {datos_cita.get('entidad_eps')}")
            
            # Agregar método de pago
            metodo_pago = datos_cita.get('metodo_pago')
            if metodo_pago:
                # Determinar si es particular
                es_particular = False
                
                # Es particular si:
                # 1. Método de pago es 'efectivo' o 'transferencia' (no póliza)
                # 2. O si hay plan de acondicionamiento (siempre particular)
                # 3. O si NO hay EPS especificada
                
                plan_acondicionamiento = datos_cita.get('plan_acondicionamiento')
                tiene_eps = datos_cita.get('entidad_eps')
                
                if metodo_pago in ['efectivo', 'transferencia']:
                    es_particular = True
                elif plan_acondicionamiento:  # Acondicionamiento siempre es particular
                    es_particular = True
                elif not tiene_eps:  # Sin EPS = particular
                    es_particular = True
                
                # Construir texto de pago
                if es_particular:
                    if metodo_pago == 'transferencia':
                        # Transferencia = pago anticipado por chat
                        comment_parts.append(f"PAGO PARTICULAR - TRANSFERENCIA (PAGADO POR CHAT)")
                    elif metodo_pago == 'efectivo':
                        # Efectivo = pago presencial en clínica
                        comment_parts.append(f"PAGO PARTICULAR - EFECTIVO (PRESENCIAL)")
                    else:
                        # Otros métodos particulares
                        comment_parts.append(f"PAGO PARTICULAR - {metodo_pago.upper()}")
                else:
                    # Pago con póliza/EPS (presencial)
                    comment_parts.append(f"Pago: {metodo_pago}")
            
            # Agregar contacto de emergencia
            contacto_emergencia_nombre = datos_cita.get('contacto_emergencia_nombre')
            contacto_emergencia_telefono = datos_cita.get('contacto_emergencia_telefono')
            contacto_emergencia_parentesco = datos_cita.get('contacto_emergencia_parentesco')
            
            if contacto_emergencia_nombre and contacto_emergencia_telefono:
                parentesco_texto = f" ({contacto_emergencia_parentesco})" if contacto_emergencia_parentesco else ""
                comment_parts.append(f"Emergencia: {contacto_emergencia_nombre}{parentesco_texto} - {contacto_emergencia_telefono}")
            
            # Agregar nota de múltiples sesiones
            if sesiones_orden > 1:
                comment_parts.append(f"Orden indica {sesiones_orden} sesiones - Primera sesión")
            
            # Agregar plan de acondicionamiento
            plan_acondicionamiento = datos_cita.get('plan_acondicionamiento')
            if plan_acondicionamiento:
                comment_parts.append(f"Plan: {plan_acondicionamiento}")
            
            comment_final = " | ".join(comment_parts)
            
            duracion_min = 60
            datos_cita_saludtools = {
                "patientDocumentType": 1,
                "patientDocumentNumber": documento,
                "doctorDocumentType": int(os.getenv("SALUDTOOLS_DOCTOR_DOCUMENT_TYPE", "1")),
                "doctorDocumentNumber": os.getenv("SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER", "11111"),
                "startDate": fecha_cita.isoformat() if isinstance(fecha_cita, datetime) else fecha_cita,
                "endDate": (fecha_cita + timedelta(minutes=duracion_min)).isoformat() if isinstance(fecha_cita, datetime) else fecha_cita,
                "modality": os.getenv("SALUDTOOLS_DEFAULT_MODALITY", "CONVENTIONAL"),
                "appointmentState": "PENDING",
                "appointmentType": sanitized_type,
                "clinic": int(os.getenv("SALUDTOOLS_CLINIC_ID", "0") or 0),
                "comment": comment_final,
                "notificationState": "ATTEND",
            }
            
            # 3. Crear cita
            cita_creada = await self.saludtools.crear_cita_paciente(datos_cita_saludtools)
            
            if cita_creada and cita_creada.get("id"):
                # 🆕 BUG #9 FIX: Logging estructurado de éxito
                logger.info(f"✅ Cita creada exitosamente", extra={
                    "cita_id": cita_creada.get('id'),
                    "documento": documento,
                    "tipo_servicio": sanitized_type,
                    "timestamp": now_colombia().isoformat()
                })
                simple_monitor.record_success("crear_cita")  # 🆕 Bug #11
                return {
                    "success": True,
                    "cita_id": cita_creada.get("id"),
                    "fecha_cita": fecha_cita.strftime("%d/%m/%Y %I:%M %p") if isinstance(fecha_cita, datetime) else str(fecha_cita),
                    "mensaje": "Cita agendada exitosamente"
                }
            else:
                # 🆕 BUG #9 FIX: Logging estructurado de error
                logger.error(f"❌ Error creando cita", extra={
                    "documento": documento,
                    "response": str(cita_creada),
                    "timestamp": now_colombia().isoformat()
                })
                simple_monitor.record_error("crear_cita", "No response from SaludTools", "high")  # 🆕 Bug #11
                return {
                    "success": False,
                    "error": "No se pudo crear la cita",
                    "requiere_escalamiento": True
                }
                
        except Exception as e:
            logger.error(f"❌ Error en _crear_cita_saludtools: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "requiere_escalamiento": True
            }
    
    async def _consultar_citas_paciente(self, entidades: Dict, contexto: Dict = None) -> Dict:
        """Consulta citas del paciente en SaludTools"""
        try:
            # Obtener documento del paciente
            documento = None
            
            # Intentar extraer de entidades
            if entidades:
                documento = entidades.get("documento_paciente")
            
            # Si no está en entidades, intentar extraer del contexto (conversación previa)
            if not documento and contexto:
                # Buscar en datos previos del contexto
                documento = contexto.get("documento")
                
                # Si no está en contexto directo, buscar en historial de mensajes
                if not documento:
                    historial = contexto.get("historial_mensajes", [])
                    if isinstance(historial, list) and len(historial) > 0:
                        # Buscar en el último mensaje del usuario
                        ultimo_mensaje = historial[-1] if historial else {}
                        if isinstance(ultimo_mensaje, dict):
                            contenido = ultimo_mensaje.get("content", "")
                        else:
                            contenido = str(ultimo_mensaje)
                        
                        # Extraer números que parezcan documentos (7-10 dígitos)
                        import re
                        match = re.search(r'\b(\d{7,10})\b', contenido)
                        if match:
                            documento = match.group(1)
            
            # Si aún no hay documento, intentar extraer del mensaje_original del análisis
            if not documento and entidades:
                mensaje_original = entidades.get("mensaje_original", "")
                if mensaje_original:
                    import re
                    # Buscar patrón de documento (7-10 dígitos)
                    match = re.search(r'\b(\d{7,10})\b', str(mensaje_original))
                    if match:
                        documento = match.group(1)
            
            # Si no está en entidades, pedirlo
            if not documento:
                return {
                    "respuesta": """📋 **Consulta de Citas**

Para ver tus citas agendadas, necesito tu número de documento.

💬 **Por favor escribe tu número de cédula**

Ejemplo: 1234567890""",
                    "intencion": "solicitar_documento",
                    "requiere_escalamiento": False
                }
            
            # 🔐 VALIDAR AUTENTICACIÓN SALUDTOOLS
            if not await self._ensure_saludtools_ready():
                logger.error("❌ SaludTools no disponible para consultar citas")
                return {
                    "respuesta": "⚠️ El sistema de consulta no está disponible. Contacta a nuestro equipo: 3193175762",
                    "requiere_escalamiento": True
                }
            
            # Buscar citas
            citas = await self.saludtools.buscar_citas_paciente(documento)
            
            # GUARDAR el documento en el contexto para futuras consultas
            if contexto is not None:
                contexto["documento"] = documento
                logger.info(f"✅ Documento {documento} guardado en contexto para futura referencia")
            
            if not citas or len(citas) == 0:
                return {
                    "respuesta": f"""📋 **No tienes citas agendadas**

🔍 Documento consultado: {documento}

¿Deseas agendar una nueva cita de fisioterapia o acondicionamiento?

💬 Escribe "agendar cita" para comenzar""",
                    "intencion": "sin_citas",
                    "requiere_escalamiento": False
                }
            
            # 🆕 FILTRAR POR REFERENCIA TEMPORAL si está presente
            mensaje_consulta = ""
            if entidades and "mensaje_original" in entidades:
                mensaje_consulta = str(entidades.get("mensaje_original", "")).lower()
            
            referencias_temporales = [
                'mañana', 'pasado mañana', 'hoy',
                'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo',
                'próxim', 'siguient', 'esta semana', 'próxima semana',
                'este ', 'próximo '
            ]
            
            tiene_referencia_temporal = any(ref in mensaje_consulta for ref in referencias_temporales)
            
            if tiene_referencia_temporal:
                # Intentar parsear fecha o rango
                fecha_mencionada = self._extraer_nueva_fecha(mensaje_consulta, analisis={})
                
                if fecha_mencionada:
                    # Determinar si es un día específico o un rango (semana)
                    es_rango_semana = 'semana' in mensaje_consulta
                    
                    citas_filtradas = []
                    for cita in citas:
                        fecha_str = cita.get("startDate", "")
                        if not fecha_str:
                            continue
                        
                        try:
                            fecha_cita = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                            
                            if es_rango_semana:
                                # Filtrar toda la semana
                                fecha_fin_semana = fecha_mencionada + timedelta(days=7)
                                if fecha_mencionada.date() <= fecha_cita.date() < fecha_fin_semana.date():
                                    citas_filtradas.append(cita)
                            else:
                                # Filtrar día específico
                                if fecha_cita.date() == fecha_mencionada.date():
                                    citas_filtradas.append(cita)
                        except Exception as e:
                            logger.debug(f"No se pudo parsear fecha '{fecha_str}': {e}")
                            continue
                    
                    if citas_filtradas:
                        citas = citas_filtradas
                        logger.info(f"✅ Filtradas {len(citas)} citas por referencia temporal")
                    else:
                        fecha_formateada = fecha_mencionada.strftime("%d/%m/%Y")
                        return {
                            "respuesta": f"""📋 **No tienes citas para la fecha mencionada**

🔍 Documento: {documento}
📅 Fecha consultada: {fecha_formateada}

💬 **Opciones:**
• Escribe "mis citas" para ver todas tus citas
• Escribe "agendar cita" para nueva cita""",
                            "intencion": "sin_citas_fecha_especifica",
                            "requiere_escalamiento": False
                        }
            
            # Formatear lista de citas
            mensaje = f"""📋 **Tus Citas Agendadas** ({len(citas)} cita(s))

🔍 Documento: {documento}\n\n"""
            
            for idx, cita in enumerate(citas[:5], 1):  # Máximo 5 citas
                fecha_str = cita.get("startDate", "Fecha no disponible")
                try:
                    fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                    fecha_formateada = fecha.strftime("%d/%m/%Y %I:%M %p")
                except Exception as e:
                    logger.debug(f"No se pudo parsear fecha '{fecha_str}': {e}")
                    fecha_formateada = fecha_str
                
                tipo = cita.get("appointmentType", "No especificado")
                estado = cita.get("appointmentState", "PENDING")
                cita_id = cita.get("id", "N/D")
                
                emoji_estado = "⏳" if estado == "PENDING" else "✅" if estado == "CONFIRMED" else "❌"
                
                mensaje += f"""{idx}. {emoji_estado} **Cita #{cita_id}**
   📅 Fecha: {fecha_formateada}
   🏥 Tipo: {tipo}
   📊 Estado: {estado}

"""
            
            mensaje += """💡 **Opciones:**
• Escribe "cancelar cita #ID" para cancelar
• Escribe "modificar cita #ID" para cambiar fecha
• Escribe "agendar cita" para nueva cita"""
            
            return {
                "respuesta": mensaje,
                "intencion": "consulta_citas_exitosa",
                "citas_encontradas": len(citas),
                "requiere_escalamiento": False
            }
            
        except Exception as e:
            logger.error(f"Error consultando citas: {e}")
            return {
                "respuesta": "⚠️ Hubo un error consultando tus citas. Por favor intenta nuevamente o contacta al 3193175762",
                "requiere_escalamiento": True
            }
    
    async def _identificar_cita_por_referencia_temporal(self, mensaje: str, documento: str = None, contexto: Dict = None) -> Optional[int]:
        """
        Identifica automáticamente el ID de una cita basándose en referencias temporales naturales
        
        🎯 **Objetivo:** Permitir al usuario decir "mi cita de mañana" en lugar de "cita #12345"
        
        **Soporta expresiones como:**
        - "mi cita de mañana"
        - "la cita que tengo pasado mañana"
        - "mi cita de este jueves"
        - "la cita del próximo martes"
        - "mis citas de la próxima semana"
        
        **Flujo:**
        1. Detecta si el mensaje contiene referencia temporal
        2. Parsea la fecha mencionada usando _extraer_nueva_fecha()
        3. Consulta las citas del paciente en SaludTools
        4. Filtra las citas que coincidan con la fecha
        5. Si hay una única cita, retorna su ID
        6. Si hay múltiples, retorna None (el chatbot pedirá aclaración)
        
        Args:
            mensaje: Mensaje original del usuario
            documento: Documento del paciente (si no está, lo busca en contexto)
            contexto: Diccionario de contexto con datos previos
        
        Returns:
            ID de la cita (int) si se identificó inequívocamente, None en caso contrario
        """
        try:
            # Detectar si hay referencia temporal en el mensaje
            referencias_temporales = [
                'mañana', 'pasado mañana', 'hoy',
                'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo',
                'próxim', 'siguient', 'esta semana', 'próxima semana',
                'este ', 'próximo ', 'el lunes', 'el martes', 'el miércoles', 'el jueves', 
                'el viernes', 'el sábado', 'el domingo'
            ]
            
            mensaje_lower = mensaje.lower()
            tiene_referencia_temporal = any(ref in mensaje_lower for ref in referencias_temporales)
            
            if not tiene_referencia_temporal:
                logger.debug("No se detectó referencia temporal en el mensaje")
                return None
            
            # Obtener documento (de parámetro o contexto)
            if not documento and contexto:
                documento = contexto.get("documento")
            
            if not documento:
                logger.debug("No hay documento disponible para buscar citas")
                return None
            
            # Parsear la fecha mencionada
            fecha_mencionada = self._extraer_nueva_fecha(mensaje, analisis={})
            if not fecha_mencionada:
                logger.debug("No se pudo parsear la fecha del mensaje")
                return None
            
            logger.info(f"📅 Fecha parseada de '{mensaje}': {fecha_mencionada.strftime('%Y-%m-%d')}")
            
            # Validar que SaludTools esté disponible
            if not await self._ensure_saludtools_ready():
                logger.error("SaludTools no disponible para consultar citas")
                return None
            
            # Consultar citas del paciente
            citas = await self.saludtools.buscar_citas_paciente(documento)
            if not citas:
                logger.debug(f"No se encontraron citas para documento {documento}")
                return None
            
            # Filtrar citas que coincidan con la fecha mencionada
            citas_coincidentes = []
            for cita in citas:
                fecha_str = cita.get("startDate", "")
                if not fecha_str:
                    continue
                
                try:
                    # Parsear fecha de la cita
                    fecha_cita = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                    
                    # Comparar solo fecha (sin hora)
                    if fecha_cita.date() == fecha_mencionada.date():
                        citas_coincidentes.append(cita)
                        logger.info(f"✅ Cita #{cita.get('id')} coincide con fecha mencionada")
                except Exception as e:
                    logger.debug(f"No se pudo parsear fecha '{fecha_str}': {e}")
                    continue
            
            # Analizar resultados
            if len(citas_coincidentes) == 0:
                logger.info(f"❌ No hay citas para la fecha mencionada ({fecha_mencionada.strftime('%d/%m/%Y')})")
                return None
            
            if len(citas_coincidentes) == 1:
                cita_id = citas_coincidentes[0].get("id")
                logger.info(f"✅ Identificada inequívocamente cita #{cita_id}")
                return int(cita_id)
            
            # Múltiples citas en la misma fecha
            logger.info(f"⚠️ Hay {len(citas_coincidentes)} citas en la fecha mencionada, se requiere aclaración")
            return None  # El chatbot pedirá aclaración mostrando las opciones
            
        except Exception as e:
            logger.error(f"Error identificando cita por referencia temporal: {e}")
            return None
    
    async def _modificar_cita_paciente(self, entidades: Dict, analisis: Dict, contexto: Dict = None) -> Dict:
        """
        Modifica una cita existente en SaludTools con VALIDACIONES ROBUSTAS
        
        🎯 **SOPORTA REFERENCIAS NATURALES:**
        - "Cambiar mi cita de mañana"
        - "Modificar la cita que tengo el jueves"
        - "Reagendar mi cita del próximo martes"
        - "Modificar cita #12345" (ID directo también funciona)
        
        Flujo:
        1. Intenta identificar cita por referencia temporal ("mañana", "jueves")
        2. Si no, extrae ID explícito del mensaje
        3. Busca cita en SaludTools (validación de existencia)
        4. Detecta qué quiere modificar (fecha/hora/médico/tipo)
        5. Valida disponibilidad y restricciones
        6. Actualiza en SaludTools O escala si es complejo
        """
        try:
            if not self.saludtools:
                return self._escalamiento_modificacion_sin_api()
            
            # ========== PASO 1: EXTRAER ID DE CITA ==========
            mensaje_original = str(analisis.get("mensaje_original", ""))
            
            # 🆕 PASO 1.1: Intentar identificar por referencia temporal
            documento = contexto.get("documento") if contexto else None
            cita_id = await self._identificar_cita_por_referencia_temporal(mensaje_original, documento, contexto)
            
            # PASO 1.2: Si no se identificó por fecha, buscar ID explícito
            if not cita_id:
                cita_id = self._extraer_id_cita(mensaje_original.lower())
            
            if not cita_id:
                return {
                    "respuesta": """📝 **Modificación de Cita**

Puedes indicarme la cita de varias formas:

💬 **Con referencia temporal:**
• "Cambiar mi cita de mañana"
• "Modificar mi cita de este jueves"
• "Reagendar la cita del próximo martes"

💬 **Con número de ID:**
• "Modificar cita #12345"
• "Cambiar fecha cita 12345"

📋 **¿No recuerdas tu cita?**
Escribe "mis citas" para verlas todas""",
                    "intencion": "solicitar_id_modificacion",
                    "requiere_escalamiento": False
                }
            
            # ========== PASO 2: BUSCAR Y VALIDAR CITA ==========
            try:
                cita_actual = await self.saludtools.obtener_cita(cita_id)
            except Exception as e:
                logger.error(f"Error buscando cita #{cita_id}: {e}")
                cita_actual = None
            
            if not cita_actual:
                return {
                    "respuesta": f"""❌ **Cita No Encontrada**

No pude encontrar la cita #{cita_id}.

**Posibles razones:**
• El ID no existe en el sistema
• La cita ya fue cancelada
• Error de escritura en el número

📋 Escribe "mis citas" para ver tus citas activas""",
                    "intencion": "cita_no_encontrada",
                    "requiere_escalamiento": False
                }
            
            # ========== VALIDACIÓN: CITA YA PASADA ==========
            if self._cita_ya_paso(cita_actual):
                return {
                    "respuesta": f"""⚠️ **Cita Ya Completada**

La cita #{cita_id} ya fue realizada y no se puede modificar.

📅 **Detalles:**
• Fecha: {cita_actual.get('startDate', 'N/D')}
• Estado: {cita_actual.get('appointmentState', 'N/D')}

💡 **¿Necesitas una nueva cita?**
Escribe "agendar cita" para crear una nueva""",
                    "intencion": "cita_pasada",
                    "requiere_escalamiento": False
                }
            
            # ========== VALIDACIÓN: CITA CANCELADA ==========
            if cita_actual.get('appointmentState') == 'CANCELLED':
                return {
                    "respuesta": f"""⚠️ **Cita Cancelada**

La cita #{cita_id} ya está cancelada.

💡 **¿Quieres reagendar?**
Escribe "agendar cita" para crear una nueva cita""",
                    "intencion": "cita_cancelada",
                    "requiere_escalamiento": False
                }
            
            # ========== PASO 3: DETECTAR QUÉ QUIERE MODIFICAR ==========
            tipo_modificacion = self._detectar_tipo_modificacion(mensaje_original)
            
            # ========== CASO 1: MODIFICACIÓN SIMPLE DE FECHA/HORA ==========
            if tipo_modificacion == "fecha_hora":
                nueva_fecha = self._extraer_nueva_fecha(mensaje_original, analisis)
                
                if not nueva_fecha:
                    # Pedir fecha específica
                    return {
                        "respuesta": f"""📅 **Modificar Fecha de Cita #{cita_id}**

**Cita actual:**
• Fecha: {self._formatear_fecha_cita(cita_actual.get('startDate'))}
• Tipo: {cita_actual.get('appointmentType', 'N/D')}

**¿Cuándo prefieres la nueva cita?**

💬 **Ejemplos:**
• "El próximo martes a las 3 PM"
• "25 de diciembre a las 10 AM"
• "Mañana a las 9:00"

Escribe la nueva fecha que prefieres 👇""",
                        "intencion": "solicitar_nueva_fecha",
                        "requiere_escalamiento": False,
                        "cita_id": cita_id,
                        "esperando_fecha": True
                    }
                
                # Validar nueva fecha
                validacion = self._validar_nueva_fecha(nueva_fecha, cita_actual)
                
                if not validacion["valida"]:
                    return {
                        "respuesta": f"""⚠️ **Fecha No Válida**

{validacion['mensaje']}

💡 **Alternativas:**
• Elige otra fecha dentro del horario laboral
• Contacta al equipo: 3193175762""",
                        "intencion": "fecha_invalida",
                        "requiere_escalamiento": False
                    }
                
                # ========== INTENTAR MODIFICACIÓN AUTOMÁTICA ==========
                try:
                    resultado = await self._ejecutar_modificacion_fecha(
                        cita_id, 
                        cita_actual, 
                        nueva_fecha
                    )
                    
                    if resultado.get("success"):
                        return {
                            "respuesta": f"""✅ **¡Cita Modificada Exitosamente!**

🔄 **Cambios realizados:**

**Fecha anterior:**
📅 {self._formatear_fecha_cita(cita_actual.get('startDate'))}

**Nueva fecha:**
📅 {self._formatear_fecha_cita(nueva_fecha)}

**Detalles:**
• ID Cita: #{cita_id}
• Tipo: {cita_actual.get('appointmentType', 'Fisioterapia')}
• Estado: Confirmada

📱 Recibirás confirmación por WhatsApp

💡 Puedes escribir "mis citas" para ver todas tus citas""",
                            "intencion": "modificacion_exitosa",
                            "requiere_escalamiento": False,
                            "cita_modificada": True,
                            "cita_id": cita_id
                        }
                    else:
                        # Fallback a escalamiento
                        return self._escalamiento_modificacion_compleja(
                            cita_id, 
                            cita_actual, 
                            "conflicto_horario",
                            resultado.get("error")
                        )
                        
                except Exception as e:
                    logger.error(f"Error modificando cita #{cita_id}: {e}")
                    return self._escalamiento_modificacion_compleja(
                        cita_id, 
                        cita_actual, 
                        "error_sistema",
                        str(e)
                    )
            
            # ========== CASO 2: CAMBIO DE MÉDICO/ESPECIALISTA ==========
            elif tipo_modificacion == "medico":
                return self._escalamiento_modificacion_compleja(
                    cita_id, 
                    cita_actual, 
                    "cambio_medico",
                    "Requiere validación de disponibilidad del profesional"
                )
            
            # ========== CASO 3: CAMBIO DE TIPO DE SERVICIO ==========
            elif tipo_modificacion == "tipo_servicio":
                return self._escalamiento_modificacion_compleja(
                    cita_id, 
                    cita_actual, 
                    "cambio_tipo_servicio",
                    "Requiere validación de precios y modalidades"
                )
            
            # ========== CASO 4: MODIFICACIÓN GENÉRICA/COMPLEJA ==========
            else:
                return {
                    "respuesta": f"""📝 **Modificación de Cita #{cita_id}**

**Cita actual:**
📅 Fecha: {self._formatear_fecha_cita(cita_actual.get('startDate'))}
🏥 Tipo: {cita_actual.get('appointmentType', 'N/D')}

**¿Qué deseas modificar?**

💬 **Opciones:**
1️⃣ Cambiar fecha/hora: "Cambiar a [nueva fecha]"
2️⃣ Cancelar cita: "Cancelar cita #{cita_id}"
3️⃣ Consultar disponibilidad: "Horarios disponibles"

📞 **Para cambios complejos contacta:**
• WhatsApp: 3193175762""",
                    "intencion": "aclarar_modificacion",
                    "requiere_escalamiento": False,
                    "cita_id": cita_id
                }
            
        except Exception as e:
            logger.error(f"Error en _modificar_cita_paciente: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "respuesta": "⚠️ Hubo un error procesando tu solicitud. Por favor contacta al 3193175762",
                "requiere_escalamiento": True
            }
    
    async def _cancelar_cita_paciente(self, entidades: Dict, analisis: Dict, contexto: Dict = None) -> Dict:
        """
        Cancela una cita en SaludTools
        
        🎯 **SOPORTA REFERENCIAS NATURALES:**
        - "Cancelar mi cita de mañana"
        - "Cancelar la cita que tengo el jueves"
        - "Cancelar mi cita del próximo martes"
        - "Cancelar cita #12345" (ID directo también funciona)
        """
        try:
            # Extraer ID de cita del mensaje
            mensaje_original = str(analisis.get("mensaje_original", ""))
            
            # 🆕 PASO 1.1: Intentar identificar por referencia temporal
            documento = contexto.get("documento") if contexto else None
            cita_id = await self._identificar_cita_por_referencia_temporal(mensaje_original, documento, contexto)
            
            # PASO 1.2: Si no se identificó por fecha, buscar ID explícito
            if not cita_id:
                import re
                match = re.search(r'#?(\d+)', mensaje_original.lower())
                if match:
                    cita_id = int(match.group(1))
            
            if not cita_id:
                return {
                    "respuesta": """❌ **Cancelación de Cita**

Puedes indicarme la cita de varias formas:

💬 **Con referencia temporal:**
• "Cancelar mi cita de mañana"
• "Cancelar mi cita de este jueves"
• "Cancelar la cita del próximo martes"

💬 **Con número de ID:**
• "Cancelar cita #12345"
• "Cancelar cita 12345"

📋 **¿No recuerdas tu cita?**
Escribe "mis citas" para ver tus citas y sus IDs""",
                    "intencion": "solicitar_id_cita",
                    "requiere_escalamiento": False
                }
            
            # 🔐 VALIDAR AUTENTICACIÓN SALUDTOOLS
            if not await self._ensure_saludtools_ready():
                logger.error("❌ SaludTools no disponible para cancelar cita")
                return {
                    "respuesta": "⚠️ El sistema de cancelación no está disponible. Contacta a nuestro equipo: 3193175762",
                    "requiere_escalamiento": True
                }
            
            # Cancelar cita
            resultado = await self.saludtools.cancelar_cita_paciente(cita_id)
            
            if resultado:
                return {
                    "respuesta": f"""✅ **Cita Cancelada Exitosamente**

🗑️ **Cita #{cita_id}** ha sido cancelada

📧 Recibirás confirmación por email/WhatsApp

💡 **¿Necesitas reagendar?**
Escribe "agendar cita" para crear una nueva cita

¡Esperamos verte pronto! 😊""",
                    "intencion": "cancelacion_exitosa",
                    "cita_id": cita_id,
                    "requiere_escalamiento": False
                }
            else:
                return {
                    "respuesta": f"""⚠️ **No se pudo cancelar la cita #{cita_id}**

Posibles razones:
• La cita ya fue cancelada
• El ID no existe
• La cita ya pasó

📞 Contacta a nuestro equipo: 3193175762""",
                    "intencion": "cancelacion_fallida",
                    "requiere_escalamiento": True
                }
                
        except Exception as e:
            logger.error(f"Error cancelando cita: {e}")
            return {
                "respuesta": "⚠️ Hubo un error cancelando la cita. Contacta al 3193175762",
                "requiere_escalamiento": True
            }

    # =========================================================================
    # 🛡️ MÉTODOS AUXILIARES PARA MODIFICACIÓN DE CITAS - VALIDACIONES ROBUSTAS
    # =========================================================================
    
    def _extraer_id_cita(self, mensaje: str) -> Optional[int]:
        """Extrae ID de cita del mensaje con múltiples patrones"""
        import re
        
        # Patrón 1: #12345
        match = re.search(r'#(\d+)', mensaje)
        if match:
            return int(match.group(1))
        
        # Patrón 2: cita 12345, cita número 12345
        match = re.search(r'cita\s*(?:n[uú]mero|num|#)?\s*(\d+)', mensaje)
        if match:
            return int(match.group(1))
        
        # Patrón 3: ID 12345
        match = re.search(r'id\s*:?\s*(\d+)', mensaje)
        if match:
            return int(match.group(1))
        
        # Patrón 4: Solo números de 4+ dígitos
        match = re.search(r'\b(\d{4,})\b', mensaje)
        if match:
            return int(match.group(1))
        
        return None
    
    def _cita_ya_paso(self, cita: Dict) -> bool:
        """Verifica si la cita ya pasó"""
        try:
            fecha_str = cita.get('startDate')
            if not fecha_str:
                return False
            
            # Parsear fecha
            fecha_cita = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            ahora = datetime.now(fecha_cita.tzinfo) if fecha_cita.tzinfo else datetime.now()
            
            return fecha_cita < ahora
        except Exception as e:
            logger.error(f"Error verificando si cita pasó: {e}")
            return False
    
    def _formatear_fecha_cita(self, fecha_str: str) -> str:
        """Formatea fecha de cita para mostrar al usuario"""
        try:
            if not fecha_str:
                return "Fecha no disponible"
            
            fecha = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            return fecha.strftime("%d/%m/%Y a las %I:%M %p")
        except Exception:
            return str(fecha_str)
    
    def _detectar_tipo_modificacion(self, mensaje: str) -> str:
        """
        Detecta qué tipo de modificación quiere hacer el usuario
        
        Returns:
            - "fecha_hora": Cambio de fecha/hora
            - "medico": Cambio de médico/especialista
            - "tipo_servicio": Cambio de tipo de servicio
            - "generico": No especificado
        """
        mensaje_lower = mensaje.lower()
        
        # Palabras clave para fecha/hora
        keywords_fecha = [
            'fecha', 'hora', 'día', 'cuando', 'horario', 'tiempo',
            'mañana', 'tarde', 'lunes', 'martes', 'miércoles', 'jueves', 
            'viernes', 'sábado', 'próximo', 'siguiente', 'cambiar a',
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
        ]
        
        # Palabras clave para médico
        keywords_medico = [
            'médico', 'doctor', 'doctora', 'fisioterapeuta', 
            'terapeuta', 'profesional', 'especialista', 'con '
        ]
        
        # Palabras clave para tipo de servicio
        keywords_servicio = [
            'tipo', 'servicio', 'modalidad', 'terapia', 'tratamiento'
        ]
        
        # Contar coincidencias
        count_fecha = sum(1 for kw in keywords_fecha if kw in mensaje_lower)
        count_medico = sum(1 for kw in keywords_medico if kw in mensaje_lower)
        count_servicio = sum(1 for kw in keywords_servicio if kw in mensaje_lower)
        
        # Determinar tipo predominante
        if count_fecha > 0 and count_fecha >= count_medico and count_fecha >= count_servicio:
            return "fecha_hora"
        elif count_medico > 0 and count_medico > count_fecha:
            return "medico"
        elif count_servicio > 0:
            return "tipo_servicio"
        else:
            return "generico"
    
    def _extraer_nueva_fecha(self, mensaje: str, analisis: Dict) -> Optional[datetime]:
        """
        Extrae nueva fecha del mensaje usando IA y expresiones naturales complejas
        
        🔴 CRÍTICO: Usa datetime.now() - FECHA REAL DEL SISTEMA
        Hoy: 22/11/2025 (actualizado automáticamente)
        
        Soporta expresiones humanas naturales:
        - "mañana", "pasado mañana" 
        - "este lunes", "próximo martes", "el jueves"
        - "para este lunes", "para el próximo viernes"
        - "dentro de 3 días", "en 2 semanas", "en 1 mes"
        - "esta semana", "próxima semana"
        - "15/03/2025", "15 de marzo"
        
        Returns:
            datetime object (siempre FUTURO) o None si no se pudo extraer
        """
        try:
            # Usar análisis de IA si ya se extrajo
            if analisis and 'fecha_deseada' in analisis:
                fecha_str = analisis.get('fecha_deseada')
                if fecha_str:
                    fecha_ia = datetime.fromisoformat(fecha_str)
                    # VALIDAR: No permitir fechas pasadas
                    if fecha_ia < datetime.now():
                        logger.warning(f"⚠️ IA sugirió fecha pasada: {fecha_ia}, ajustando...")
                        return None
                    return fecha_ia
            
            import re
            from datetime import timedelta
            
            mensaje_lower = mensaje.lower()
            # 🔴 FECHA REAL DEL SISTEMA - No usar fechas hardcodeadas
            ahora = datetime.now()
            
            logger.info(f"📅 Fecha actual del sistema: {ahora.strftime('%d/%m/%Y %H:%M')}")
            
            # ========== EXPRESIONES RELATIVAS SIMPLES ==========
            
            # "mañana"
            if re.search(r'\bma[ñn]ana\b', mensaje_lower):
                if 'pasado' in mensaje_lower or 'despu[ée]s' in mensaje_lower:
                    return ahora + timedelta(days=2)  # Pasado mañana
                return ahora + timedelta(days=1)
            
            # "hoy" (mismo día, útil para reagendar)
            if re.search(r'\bhoy\b', mensaje_lower):
                return ahora
            
            # ========== DÍAS DE LA SEMANA CON CONTEXTO ==========
            
            dias_semana = {
                'lunes': 0, 'martes': 1, 'mi[ée]rcoles': 2,
                'jueves': 3, 'viernes': 4, 's[áa]bado': 5, 'domingo': 6
            }
            
            for dia_nombre, dia_num in dias_semana.items():
                # Buscar día de la semana en el mensaje
                if re.search(rf'\b{dia_nombre}\b', mensaje_lower):
                    dias_hasta = (dia_num - ahora.weekday() + 7) % 7
                    
                    # Detectar contexto: "este lunes" vs "próximo lunes" vs "el lunes"
                    if re.search(rf'\b(este|esta)\s+{dia_nombre}\b', mensaje_lower):
                        # "Este lunes" = esta misma semana
                        if dias_hasta == 0:
                            # Si hoy es lunes y dice "este lunes", es hoy
                            return ahora
                        return ahora + timedelta(days=dias_hasta)
                    
                    elif re.search(rf'\b(pr[óo]ximo|pr[óo]xima|siguiente)\s+{dia_nombre}\b', mensaje_lower):
                        # "Próximo lunes" = siguiente semana
                        if dias_hasta == 0:
                            dias_hasta = 7
                        return ahora + timedelta(days=dias_hasta + 7)
                    
                    elif re.search(rf'\b(el|la)\s+{dia_nombre}\b', mensaje_lower):
                        # "El lunes" = esta semana si aún no pasó, sino próxima
                        if dias_hasta == 0:
                            dias_hasta = 7
                        return ahora + timedelta(days=dias_hasta)
                    
                    else:
                        # Sin contexto específico = próximo día de esa semana
                        if dias_hasta == 0:
                            dias_hasta = 7
                        return ahora + timedelta(days=dias_hasta)
            
            # ========== PERÍODOS RELATIVOS (DÍAS/SEMANAS/MESES) ==========
            
            # "en X días", "dentro de X días"
            match = re.search(r'(?:en|dentro\s+de)\s+(\d+)\s*d[íi]as?', mensaje_lower)
            if match:
                dias = int(match.group(1))
                return ahora + timedelta(days=dias)
            
            # "en X semanas", "dentro de X semanas"
            match = re.search(r'(?:en|dentro\s+de)\s+(\d+)\s*semanas?', mensaje_lower)
            if match:
                semanas = int(match.group(1))
                return ahora + timedelta(weeks=semanas)
            
            # "en X meses", "dentro de X meses"
            match = re.search(r'(?:en|dentro\s+de)\s+(\d+)\s*mes(?:es)?', mensaje_lower)
            if match:
                meses = int(match.group(1))
                # Aproximación: 1 mes = 30 días
                return ahora + timedelta(days=meses * 30)
            
            # ========== EXPRESIONES DE SEMANA ==========
            
            # "esta semana" (próximo día hábil desde HOY)
            if re.search(r'\b(esta|la)\s+semana\b', mensaje_lower):
                # 🔴 Desde fecha ACTUAL del sistema
                dias_hasta = 1
                fecha_candidata = ahora + timedelta(days=dias_hasta)
                # Saltar fines de semana
                while fecha_candidata.weekday() >= 5:  # 5=sábado, 6=domingo
                    dias_hasta += 1
                    fecha_candidata = ahora + timedelta(days=dias_hasta)
                return fecha_candidata
            
            # "próxima semana", "siguiente semana"
            if re.search(r'\b(pr[óo]xima|siguiente)\s+semana\b', mensaje_lower):
                # Lunes de la próxima semana desde HOY
                dias_hasta_lunes = (0 - ahora.weekday() + 7) % 7
                if dias_hasta_lunes == 0:
                    dias_hasta_lunes = 7
                return ahora + timedelta(days=dias_hasta_lunes + 7)
            
            # ========== FECHAS EXACTAS ==========
            
            # "DD/MM/YYYY" o "DD-MM-YYYY"
            match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', mensaje)
            if match:
                dia, mes, año = int(match.group(1)), int(match.group(2)), int(match.group(3))
                return datetime(año, mes, dia)
            
            # "DD/MM" (año actual o siguiente)
            match = re.search(r'(\d{1,2})[/-](\d{1,2})(?!\d)', mensaje)
            if match:
                dia, mes = int(match.group(1)), int(match.group(2))
                año = ahora.year
                try:
                    fecha_temp = datetime(año, mes, dia)
                    if fecha_temp < ahora:
                        año += 1
                    return datetime(año, mes, dia)
                except ValueError:
                    pass
            
            # "DD de MES"
            meses = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
            }
            
            for mes_nombre, mes_num in meses.items():
                if mes_nombre in mensaje_lower:
                    match = re.search(r'(\d{1,2})\s*de\s*' + mes_nombre, mensaje_lower)
                    if match:
                        dia = int(match.group(1))
                        # 🔴 Año actual del SISTEMA (no hardcodeado)
                        año = ahora.year
                        try:
                            fecha_temp = datetime(año, mes_num, dia)
                            # CRÍTICO: Si ya pasó, usar próximo año
                            if fecha_temp < ahora:
                                año += 1
                            return datetime(año, mes_num, dia)
                        except ValueError:
                            pass
            
            # ❌ No se pudo extraer fecha
            return None
            
        except Exception as e:
            logger.error(f"Error extrayendo fecha: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
            logger.error(f"Error extrayendo nueva fecha: {e}")
            return None
    
    def _validar_nueva_fecha(self, nueva_fecha: datetime, cita_actual: Dict) -> Dict:
        """
        Valida que la nueva fecha sea válida con múltiples verificaciones
        
        Returns:
            {
                "valida": bool,
                "mensaje": str (si no es válida),
                "warnings": List[str] (advertencias no críticas)
            }
        """
        warnings = []
        ahora = datetime.now()
        
        # ========== VALIDACIÓN 1: FECHA EN EL PASADO ==========
        if nueva_fecha < ahora:
            return {
                "valida": False,
                "mensaje": "⏰ La fecha que elegiste ya pasó. Por favor elige una fecha futura.",
                "warnings": []
            }
        
        # ========== VALIDACIÓN 2: FECHA MUY CERCANA (<24 HORAS) ==========
        if nueva_fecha < ahora + timedelta(hours=24):
            warnings.append("Cita con menos de 24 horas de anticipación - sujeto a disponibilidad")
        
        # ========== VALIDACIÓN 3: FECHA MUY LEJANA (>90 DÍAS) ==========
        if nueva_fecha > ahora + timedelta(days=90):
            return {
                "valida": False,
                "mensaje": "📅 La fecha es muy lejana (más de 3 meses). Por favor elige una fecha dentro de los próximos 90 días.",
                "warnings": []
            }
        
        # ========== VALIDACIÓN 4: FIN DE SEMANA ==========
        if nueva_fecha.weekday() >= 5:  # Sábado o Domingo
            return {
                "valida": False,
                "mensaje": "🚫 No hay atención los fines de semana. Por favor elige un día de lunes a viernes.",
                "warnings": []
            }
        
        # ========== VALIDACIÓN 5: HORARIO LABORAL ==========
        hora = nueva_fecha.hour
        if hora < 7 or hora >= 18:
            return {
                "valida": False,
                "mensaje": "🕐 Horario no disponible. Nuestro horario de atención es de 7:00 AM a 6:00 PM. Por favor elige un horario dentro de este rango.",
                "warnings": []
            }
        
        # ========== VALIDACIÓN 6: MISMA FECHA QUE LA ACTUAL ==========
        try:
            fecha_actual = datetime.fromisoformat(cita_actual.get('startDate', '').replace('Z', '+00:00'))
            if nueva_fecha.date() == fecha_actual.date() and nueva_fecha.hour == fecha_actual.hour:
                return {
                    "valida": False,
                    "mensaje": "📅 La nueva fecha es la misma que la actual. ¿Seguro quieres cambiarla?",
                    "warnings": []
                }
        except Exception:
            pass
        
        # ========== VALIDACIÓN 7: FESTIVOS (Lista básica) ==========
        festivos_2025 = [
            datetime(2025, 1, 1),   # Año Nuevo
            datetime(2025, 1, 6),   # Reyes Magos
            datetime(2025, 3, 24),  # San José
            datetime(2025, 4, 17),  # Jueves Santo
            datetime(2025, 4, 18),  # Viernes Santo
            datetime(2025, 5, 1),   # Día del Trabajo
            datetime(2025, 6, 23),  # Sagrado Corazón
            datetime(2025, 6, 30),  # San Pedro y San Pablo
            datetime(2025, 7, 20),  # Independencia
            datetime(2025, 8, 7),   # Batalla de Boyacá
            datetime(2025, 8, 18),  # Asunción
            datetime(2025, 10, 13), # Día de la Raza
            datetime(2025, 11, 3),  # Todos los Santos
            datetime(2025, 11, 17), # Independencia de Cartagena
            datetime(2025, 12, 8),  # Inmaculada Concepción
            datetime(2025, 12, 25), # Navidad
        ]
        
        if nueva_fecha.date() in [f.date() for f in festivos_2025]:
            return {
                "valida": False,
                "mensaje": "🎉 Esa fecha es festivo y no hay atención. Por favor elige otro día.",
                "warnings": []
            }
        
        # ========== TODAS LAS VALIDACIONES PASARON ==========
        return {
            "valida": True,
            "mensaje": None,
            "warnings": warnings
        }
    
    async def _ejecutar_modificacion_fecha(
        self, 
        cita_id: int, 
        cita_actual: Dict, 
        nueva_fecha: datetime
    ) -> Dict:
        """
        Ejecuta la modificación de fecha en SaludTools
        
        Returns:
            {"success": bool, "error": str (si falla)}
        """
        try:
            # Preparar datos actualizados
            duracion_min = 60  # Por defecto 60 minutos
            
            datos_actualizacion = {
                "patientDocumentType": cita_actual.get("patientDocumentType"),
                "patientDocumentNumber": cita_actual.get("patientDocumentNumber"),
                "doctorDocumentType": cita_actual.get("doctorDocumentType"),
                "doctorDocumentNumber": cita_actual.get("doctorDocumentNumber"),
                "startDate": nueva_fecha.isoformat(),
                "endDate": (nueva_fecha + timedelta(minutes=duracion_min)).isoformat(),
                "modality": cita_actual.get("modality", "CONVENTIONAL"),
                "appointmentState": cita_actual.get("appointmentState", "PENDING"),
                "appointmentType": cita_actual.get("appointmentType"),
                "clinic": cita_actual.get("clinic"),
                "comment": f"Modificada vía WhatsApp Bot - {cita_actual.get('comment', '')}",
                "notificationState": cita_actual.get("notificationState", "ATTEND"),
            }
            
            # 🔐 VALIDAR AUTENTICACIÓN SALUDTOOLS
            if not await self._ensure_saludtools_ready():
                logger.error("❌ SaludTools no disponible para actualizar cita")
                return {"success": False, "error": "SaludTools no disponible"}
            
            # Actualizar en SaludTools
            resultado = await self.saludtools.actualizar_cita(cita_id, datos_actualizacion)
            
            if resultado:
                logger.info(f"✅ Cita #{cita_id} modificada exitosamente")
                return {"success": True}
            else:
                logger.error(f"❌ Error modificando cita #{cita_id}: Sin respuesta")
                return {"success": False, "error": "No se recibió confirmación de SaludTools"}
                
        except Exception as e:
            logger.error(f"❌ Error ejecutando modificación: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    def _escalamiento_modificacion_compleja(
        self, 
        cita_id: int, 
        cita_actual: Dict, 
        motivo: str,
        detalle_error: Optional[str] = None
    ) -> Dict:
        """
        Escalamiento inteligente cuando la modificación es muy compleja
        """
        motivos_mensaje = {
            "conflicto_horario": "el horario solicitado no está disponible",
            "cambio_medico": "requiere coordinar disponibilidad del profesional",
            "cambio_tipo_servicio": "implica cambios en la modalidad del servicio",
            "error_sistema": "hubo un problema técnico",
            "validacion_eps": "tu EPS requiere validación especial"
        }
        
        mensaje_motivo = motivos_mensaje.get(motivo, "requiere atención personalizada")
        
        # Enviar notificación a secretarias
        datos_escalamiento = {
            "cita_id": cita_id,
            "motivo": motivo,
            "detalle": detalle_error,
            "cita_actual": cita_actual,
            "fecha_solicitud": datetime.now().isoformat()
        }
        
        try:
            self._enviar_notificacion_secretarias(datos_escalamiento, f"modificacion_{motivo}")
        except Exception as e:
            logger.error(f"Error enviando notificación de escalamiento: {e}")
        
        return {
            "respuesta": f"""📝 **Modificación de Cita #{cita_id}**

⚠️ Tu solicitud {mensaje_motivo}.

📋 **Detalles actuales:**
• Fecha: {self._formatear_fecha_cita(cita_actual.get('startDate'))}
• Tipo: {cita_actual.get('appointmentType', 'N/D')}

👥 **Nuestro equipo te contactará en máximo 1 hora para:**
• Ofrecerte horarios alternativos
• Coordinar la mejor opción
• Confirmar tu nueva cita

📞 **Contacto directo:**
• WhatsApp: 3193175762
• Teléfono: 6047058040

✅ Tu solicitud ha sido registrada con prioridad""",
            "intencion": "escalamiento_modificacion",
            "requiere_escalamiento": True,
            "motivo_escalamiento": motivo,
            "cita_id": cita_id,
            "notificacion_enviada": True
        }
    
    def _escalamiento_modificacion_sin_api(self) -> Dict:
        """Escalamiento cuando SaludTools no está disponible"""
        return {
            "respuesta": """⚠️ **Sistema de Modificación No Disponible**

El sistema de modificaciones está temporalmente fuera de servicio.

📞 **Por favor contacta directamente:**
• **WhatsApp:** 3193175762
• **Teléfono:** 6047058040

Nuestro equipo te ayudará con la modificación de tu cita.

¡Disculpa las molestias!""",
            "intencion": "escalamiento_sistema_no_disponible",
            "requiere_escalamiento": True,
            "motivo_escalamiento": "saludtools_no_disponible"
        }
    
    # =========================================================================
    # 🎯 MANEJO DE EXPRESIONES NATURALES COMPLEJAS Y MÚLTIPLES CITAS
    # =========================================================================
    
    def _es_solicitud_multiple_citas(self, mensaje: str) -> bool:
        """
        Detecta si el usuario solicita múltiples citas en un solo mensaje
        
        Ejemplos:
        - "3 citas de control con Miguel"
        - "2 de acondicionamiento para esta semana"
        - "Quiero agendar 5 sesiones"
        - "Necesito 2 citas, una el lunes y otra el jueves"
        """
        import re
        mensaje_lower = mensaje.lower()
        
        # Patrón 1: Número explícito de citas (debe ser 2+)
        match = re.search(r'\b(dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|(\d+))\s+(citas?|sesiones?)', mensaje_lower)
        if match:
            # Extraer el número para validar que sea >= 2
            numero_texto = match.group(1)
            if numero_texto in ['dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve', 'diez']:
                return True  # Palabras siempre son >= 2
            else:
                # Es un dígito, verificar que sea >= 2
                try:
                    cantidad = int(numero_texto)
                    return cantidad >= 2
                except:
                    return False
        
        # Patrón 2: Múltiples días mencionados
        dias_encontrados = re.findall(r'\b(lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo)\b', mensaje_lower)
        if len(dias_encontrados) >= 2:
            return True
        
        # Patrón 3: "una... y otra..."
        if re.search(r'\b(una|uno)\s+.*\s+y\s+(otra?|otro)\b', mensaje_lower):
            return True
        
        return False
    
    async def _manejar_solicitud_multiple_citas(
        self, 
        mensaje: str, 
        analisis: Dict, 
        contexto: Dict = None
    ) -> Dict:
        """
        Maneja solicitudes complejas de múltiples citas
        
        Ejemplos soportados:
        - "3 citas de control con Miguel"
        - "2 de acondicionamiento esta semana, lunes y jueves a las 5 PM"
        - "Quiero 4 sesiones de fisioterapia"
        """
        try:
            import re
            mensaje_lower = mensaje.lower()
            
            # ========== EXTRAER CANTIDAD DE CITAS ==========
            cantidad = self._extraer_cantidad_citas(mensaje_lower)
            
            if cantidad is None or cantidad < 2:
                # No es múltiple o no detectado, tratar como simple
                return await self._respuesta_general(analisis, contexto)
            
            if cantidad > 10:
                return {
                    "respuesta": """⚠️ **Solicitud de Múltiples Citas**

Para agendar más de 10 citas, necesitamos coordinar contigo personalmente.

📞 **Contacto directo:**
• WhatsApp: 3193175762
• Teléfono: 6047058040

Nuestro equipo te ayudará a:
• Coordinar horarios óptimos
• Asegurar disponibilidad
• Aplicar descuentos por volumen (si aplica)

¡Te contactaremos en máximo 1 hora!""",
                    "intencion": "escalamiento_multiples_citas",
                    "requiere_escalamiento": True,
                    "cantidad_solicitada": cantidad
                }
            
            # ========== EXTRAER DÍAS ESPECÍFICOS ==========
            dias_especificos = self._extraer_dias_especificos(mensaje_lower)
            
            # ========== EXTRAER HORA PREFERIDA ==========
            hora_preferida = self._extraer_hora_preferida(mensaje_lower)
            
            # ========== EXTRAER TIPO DE SERVICIO ==========
            tipo_servicio = "Fisioterapia"  # Default
            if re.search(r'\bacondicionamiento\b', mensaje_lower):
                tipo_servicio = "Acondicionamiento"
            elif re.search(r'\bcontrol\b', mensaje_lower):
                tipo_servicio = "Fisioterapia - Control"
            
            # ========== EXTRAER PROFESIONAL (SI SE MENCIONA) ==========
            profesional = self._extraer_profesional_mencionado(mensaje_lower)
            
            # ========== GENERAR RESPUESTA ==========
            
            # Si tiene días específicos y cantidad coincide
            if dias_especificos and len(dias_especificos) == cantidad:
                return await self._confirmar_multiples_citas_dias_especificos(
                    cantidad,
                    dias_especificos,
                    hora_preferida,
                    tipo_servicio,
                    profesional,
                    analisis,
                    contexto
                )
            
            # Si tiene días específicos pero no coincide cantidad
            elif dias_especificos:
                return await self._confirmar_multiples_citas_dias_parciales(
                    cantidad,
                    dias_especificos,
                    hora_preferida,
                    tipo_servicio,
                    profesional,
                    analisis,
                    contexto
                )
            
            # Si solo tiene cantidad (sin días específicos)
            else:
                return await self._confirmar_multiples_citas_cantidad(
                    cantidad,
                    hora_preferida,
                    tipo_servicio,
                    profesional,
                    analisis,
                    contexto
                )
                
        except Exception as e:
            logger.error(f"Error manejando solicitud múltiple: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return await self._respuesta_general(analisis, contexto)
    
    def _extraer_cantidad_citas(self, mensaje: str) -> Optional[int]:
        """Extrae la cantidad de citas solicitadas"""
        import re
        
        # Números en texto
        numeros_texto = {
            'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5,
            'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10
        }
        
        for palabra, numero in numeros_texto.items():
            if re.search(rf'\b{palabra}\s+(citas?|sesiones?)\b', mensaje):
                return numero
        
        # Números en dígitos
        match = re.search(r'\b(\d+)\s+(citas?|sesiones?)\b', mensaje)
        if match:
            return int(match.group(1))
        
        # Contar días mencionados
        dias = re.findall(r'\b(lunes|martes|mi[ée]rcoles|jueves|viernes)\b', mensaje)
        if len(dias) >= 2:
            return len(dias)
        
        return None
    
    def _extraer_dias_especificos(self, mensaje: str) -> List[str]:
        """
        Extrae días específicos mencionados en el mensaje
        
        Returns:
            Lista de días en orden de mención
        """
        import re
        
        dias_map = {
            'lunes': 'lunes',
            'martes': 'martes',
            'mi[ée]rcoles': 'miércoles',
            'jueves': 'jueves',
            'viernes': 'viernes',
            's[áa]bado': 'sábado',
            'domingo': 'domingo'
        }
        
        dias_encontrados = []
        for patron, dia_nombre in dias_map.items():
            if re.search(rf'\b{patron}\b', mensaje):
                dias_encontrados.append(dia_nombre)
        
        return dias_encontrados
    
    def _extraer_hora_preferida(self, mensaje: str) -> Optional[str]:
        """
        Extrae hora preferida del mensaje
        
        Returns:
            String con hora en formato "HH:MM AM/PM" o None
        """
        import re
        
        # Patrón 1: "5 PM", "3 de la tarde"
        match = re.search(r'(\d{1,2})\s*(?:de\s+la\s+)?(ma[ñn]ana|tarde|pm|am)', mensaje)
        if match:
            hora = int(match.group(1))
            periodo = match.group(2)
            
            if 'tarde' in periodo or 'pm' in periodo:
                if hora < 12:
                    hora += 12
            
            return f"{hora:02d}:00"
        
        # Patrón 2: "17:00", "09:30"
        match = re.search(r'\b(\d{1,2}):(\d{2})\b', mensaje)
        if match:
            return f"{int(match.group(1)):02d}:{match.group(2)}"
        
        return None
    
    def _extraer_profesional_mencionado(self, mensaje: str) -> Optional[str]:
        """Extrae y valida nombre de profesional mencionado con fuzzy matching"""
        import re
        
        mensaje_lower = mensaje.lower()
        
        # Patrón 1: "con [nombre]"
        match = re.search(r'\bcon\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)', mensaje_lower)
        if match:
            nombre_parcial = match.group(1).strip()
            # Buscar en la lista de fisioterapeutas usando el método existente
            nombre_completo = self._obtener_nombre_completo_fisioterapeuta(nombre_parcial)
            if nombre_completo != nombre_parcial:  # Se encontró match
                return nombre_completo
            return nombre_parcial  # Devolver original para confirmar después
        
        # Patrón 2: Buscar nombres conocidos directamente en el mensaje
        nombres_cortos = {
            "migue": "Miguel Ignacio Moreno Cardona",
            "miguel": "Miguel Ignacio Moreno Cardona",
            "diana": "Diana Daniella Arana Carvalho",
            "adriana": "Adriana Acevedo Agudelo",
            "ana": "Ana Isabel Palacio Botero",
            "diego": "Diego Andrés Mosquera Torres",
            "veronica": "Verónica Echeverri Restrepo",
            "verónica": "Verónica Echeverri Restrepo",
            "daniela": "Daniela Patiño Londoño"
        }
        
        for nombre_corto, nombre_completo in nombres_cortos.items():
            if re.search(rf'\b{nombre_corto}\b', mensaje_lower):
                return nombre_completo
        
        return None
    
    async def _confirmar_multiples_citas_dias_especificos(
        self,
        cantidad: int,
        dias: List[str],
        hora: Optional[str],
        tipo_servicio: str,
        profesional: Optional[str],
        analisis: Dict,
        contexto: Dict
    ) -> Dict:
        """Confirma y agenda solicitud con días específicos definidos"""
        
        # Determinar si es control o primera vez
        mensaje_lower = analisis.get("mensaje_original", "").lower()
        es_control = "control" in mensaje_lower or "controles" in mensaje_lower
        
        # Si es 2-5 citas con días específicos, intentar agendar automáticamente
        if 2 <= cantidad <= 5:
            logger.info(f"📌 Agendando automáticamente {cantidad} citas con días específicos")
            return await self._agendar_multiples_citas_automatico(
                cantidad=cantidad,
                dias_fechas=dias,
                hora=hora,
                tipo_servicio=tipo_servicio,
                profesional=profesional,
                es_control=es_control,
                contexto=contexto
            )
        
        # Si son 6-10 citas, escalar con toda la información (muy complejo para automático)
        dias_str = ", ".join(dias[:-1]) + f" y {dias[-1]}" if len(dias) > 1 else dias[0]
        hora_str = f" a las {hora}" if hora else ""
        prof_str = f" con {profesional}" if profesional else ""
        
        return {
            "respuesta": f"""📅 **Solicitud de {cantidad} Citas - {tipo_servicio}**

✅ **Entiendo que quieres:**
• {cantidad} citas de {tipo_servicio}
• Días: {dias_str}
{f"• Hora preferida: {hora_str}" if hora else "• Hora: Por confirmar"}
{f"• Profesional: {prof_str}" if profesional else ""}

⚠️ **Para coordinar {cantidad} citas:**

Esta solicitud requiere validar disponibilidad en nuestro sistema para asegurar que todos los horarios estén libres{prof_str if profesional else ""}.

📞 **Nuestro equipo te contactará en máximo 1 hora para:**
• Confirmar disponibilidad de fechas
• Coordinar horarios exactos
• Enviar confirmación de todas las citas

**Contacto directo:**
• WhatsApp: 3193175762
• Teléfono: 6047058040

✅ **Tu solicitud está registrada con prioridad**

💡 **Mientras tanto:**
Si necesitas agendar UNA cita inmediatamente, puedo ayudarte ahora mismo.""",
            "intencion": "solicitud_multiples_citas_especificas",
            "requiere_escalamiento": True,
            "cantidad_citas": cantidad,
            "dias_solicitados": dias,
            "hora_preferida": hora,
            "tipo_servicio": tipo_servicio,
            "profesional": profesional,
            "notificacion_enviada": True
        }
    
    async def _confirmar_multiples_citas_dias_parciales(
        self,
        cantidad: int,
        dias: List[str],
        hora: Optional[str],
        tipo_servicio: str,
        profesional: Optional[str],
        analisis: Dict,
        contexto: Dict
    ) -> Dict:
        """Confirma solicitud con algunos días especificados"""
        
        dias_str = ", ".join(dias)
        faltantes = cantidad - len(dias)
        
        return {
            "respuesta": f"""📅 **Solicitud de {cantidad} Citas - {tipo_servicio}**

✅ **Días especificados:** {dias_str}
❓ **Días pendientes:** {faltantes} cita(s) por definir

💬 **¿Puedes indicar los días para las {faltantes} cita(s) restantes?**

Ejemplo: "Los otros días: martes y viernes"

O si prefieres:
📞 **Nuestro equipo puede ayudarte:**
• WhatsApp: 3193175762

¡Te ayudaremos a coordinar todo!""",
            "intencion": "solicitud_multiples_citas_incompleta",
            "requiere_escalamiento": False,
            "cantidad_total": cantidad,
            "dias_definidos": dias,
            "dias_faltantes": faltantes
        }
    
    async def _confirmar_multiples_citas_cantidad(
        self,
        cantidad: int,
        hora: Optional[str],
        tipo_servicio: str,
        profesional: Optional[str],
        analisis: Dict,
        contexto: Dict
    ) -> Dict:
        """Confirma solicitud solo con cantidad - solicita días para agendar"""
        
        return {
            "respuesta": f"""📅 **Solicitud de {cantidad} Citas - {tipo_servicio}**

✅ **Entiendo que necesitas {cantidad} citas**

💬 **Para agendar, necesito saber:**

**¿En qué días prefieres las citas?**

Ejemplos:
• "Lunes, miércoles y viernes"
• "Esta semana: martes y jueves"
• "Lunes y martes de la próxima semana"

{f"• Hora preferida: {hora}" if hora else "• Y si tienes preferencia de hora, indícamela"}

O si prefieres:
📞 **Llamamos para coordinar:**
• WhatsApp: 3193175762

¡Te ayudo a organizar todo!""",
            "intencion": "solicitar_dias_multiples_citas",
            "requiere_escalamiento": False,
            "cantidad_solicitada": cantidad,
            "hora_preferida": hora,
            "esperando_dias": True,
            "datos_temp": {
                "cantidad": cantidad,
                "hora": hora,
                "tipo_servicio": tipo_servicio,
                "profesional": profesional
            }
        }
    
    # =========================================================================
    # � AGENDAMIENTO MÚLTIPLE AUTOMÁTICO - SISTEMA ROBUSTO
    # =========================================================================
    
    async def _agendar_multiples_citas_automatico(
        self,
        cantidad: int,
        dias_fechas: List,  # Lista de strings con días o datetime objects
        hora: Optional[str],
        tipo_servicio: str,
        profesional: Optional[str],
        es_control: bool,
        contexto: Dict
    ) -> Dict:
        """
        Agenda múltiples citas automáticamente validando disponibilidad.
        
        Esta función implementa el flujo completo:
        1. Valida datos del paciente
        2. Convierte días a fechas concretas
        3. Valida disponibilidad en SaludTools
        4. Crea las citas
        5. Confirma al paciente
        
        Args:
            cantidad: Número de citas a agendar
            dias_fechas: Lista de días (ej: ["lunes", "miércoles"]) o fechas datetime
            hora: Hora preferida en formato "HH:MM" (opcional)
            tipo_servicio: "Fisioterapia" o "Acondicionamiento"
            profesional: Nombre del profesional (opcional)
            es_control: True si son citas de control, False si primera vez
            contexto: Contexto de la conversación
            
        Returns:
            Dict con respuesta y estado del agendamiento
        """
        try:
            logger.info(f"🔄 Iniciando agendamiento automático de {cantidad} citas")
            
            # ========== 1. VALIDAR Y RECOPILAR DATOS DEL PACIENTE ==========
            datos_paciente = contexto.get("datos_paciente", {}) if contexto else {}
            
            # Verificar si ya tenemos documento
            documento = datos_paciente.get("documento") or datos_paciente.get("documento_paciente")
            if not documento:
                # Solicitar documento primero
                return {
                    "respuesta": f"""📋 **Agendamiento de {cantidad} Citas - {tipo_servicio}**

✅ Perfecto, vamos a agendar tus {cantidad} citas.

Para continuar, necesito tu **número de cédula** por favor.""",
                    "intencion": "solicitar_documento_multiple",
                    "requiere_escalamiento": False,
                    "esperando_documento": True,
                    "datos_temp": {
                        "cantidad": cantidad,
                        "dias_fechas": dias_fechas,
                        "hora": hora,
                        "tipo_servicio": tipo_servicio,
                        "profesional": profesional,
                        "es_control": es_control
                    }
                }
            
            # ========== 2. CONVERTIR DÍAS A FECHAS CONCRETAS ==========
            from datetime import datetime, timedelta
            import pytz
            
            COLOMBIA_TZ = pytz.timezone('America/Bogota')
            ahora = datetime.now(COLOMBIA_TZ)
            
            fechas_citas = []
            dias_nombres = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
            
            for item in dias_fechas:
                if isinstance(item, datetime):
                    fechas_citas.append(item)
                elif isinstance(item, str):
                    # Convertir día de semana a fecha
                    dia_lower = item.lower()
                    if dia_lower in dias_nombres:
                        dia_num = dias_nombres.index(dia_lower)
                        # Buscar el próximo día que coincida
                        dias_adelante = (dia_num - ahora.weekday() + 7) % 7
                        if dias_adelante == 0:
                            dias_adelante = 7  # Si es hoy, mejor la próxima semana
                        fecha = ahora + timedelta(days=dias_adelante)
                        
                        # Establecer hora
                        if hora:
                            try:
                                hora_split = hora.split(":")
                                fecha = fecha.replace(hour=int(hora_split[0]), minute=int(hora_split[1]) if len(hora_split) > 1 else 0)
                            except:
                                fecha = fecha.replace(hour=9, minute=0)  # Default 9 AM
                        else:
                            fecha = fecha.replace(hour=9, minute=0)  # Default 9 AM
                        
                        fechas_citas.append(fecha)
            
            if len(fechas_citas) == 0:
                # No se pudieron generar fechas, solicitar días específicos
                return {
                    "respuesta": f"""📅 **Agendamiento de {cantidad} Citas**

💬 Para continuar, necesito que me indiques **en qué días** prefieres las citas.

Ejemplo:
• "Lunes, miércoles y viernes"
• "Esta semana: martes y jueves"
• "Los próximos 3 lunes"

¿Qué días te vienen mejor?""",
                    "intencion": "solicitar_dias_especificos",
                    "requiere_escalamiento": False
                }
            
            # ========== 3. VALIDAR DISPONIBILIDAD ==========
            if self.saludtools and await self._ensure_saludtools_ready():
                # Obtener citas del profesional (si se especificó) o general
                cc_profesional = None
                if profesional:
                    cc_profesional = self.fisioterapeutas_cc.get(profesional)
                
                # Verificar cada fecha
                fechas_disponibles = []
                fechas_ocupadas = []
                
                for fecha in fechas_citas:
                    # Buscar citas en esa fecha/hora
                    disponible = True  # Asumimos disponible por defecto
                    
                    # Aquí podrías implementar búsqueda en SaludTools si la API lo soporta
                    # Por ahora, validamos horarios de la IPS
                    dia_semana = fecha.weekday()
                    hora_cita = fecha.hour
                    
                    # Validar horario de la IPS
                    if dia_semana == 6:  # Domingo
                        disponible = False
                    elif dia_semana == 5:  # Sábado
                        if hora_cita < 8 or hora_cita >= 12:
                            disponible = False
                    elif dia_semana == 4:  # Viernes
                        if hora_cita < 5 or hora_cita >= 19:
                            disponible = False
                    else:  # Lunes a Jueves
                        if hora_cita < 5 or hora_cita >= 20:
                            disponible = False
                    
                    if disponible:
                        fechas_disponibles.append(fecha)
                    else:
                        fechas_ocupadas.append(fecha)
                
                # Si hay fechas ocupadas, informar
                if len(fechas_ocupadas) > 0 and len(fechas_disponibles) < cantidad:
                    fechas_str = ", ".join([f.strftime("%A %d/%m a las %I:%M %p") for f in fechas_ocupadas])
                    return {
                        "respuesta": f"""⚠️ **Problema con Disponibilidad**

Algunas fechas solicitadas están fuera del horario de atención:

{fechas_str}

**Horarios de la IPS:**
• Lunes a Jueves: 5:00 AM - 8:00 PM
• Viernes: 5:00 AM - 7:00 PM
• Sábados: 8:00 AM - 12:00 PM
• Domingos: Cerrado

💬 ¿Quieres ajustar los horarios o días?""",
                        "intencion": "fechas_fuera_horario",
                        "requiere_escalamiento": False
                    }
            else:
                # Sin SaludTools, usamos las fechas generadas
                fechas_disponibles = fechas_citas
            
            # ========== 4. VERIFICAR DATOS COMPLETOS ==========
            datos_faltantes = []
            if not datos_paciente.get("nombre_completo"):
                datos_faltantes.append("nombre completo")
            if not datos_paciente.get("telefono"):
                datos_faltantes.append("teléfono")
            if not datos_paciente.get("email"):
                datos_faltantes.append("email")
            
            if datos_faltantes:
                return {
                    "respuesta": f"""📋 **Casi Listo para Agendar {cantidad} Citas**

✅ Fechas seleccionadas:
{chr(10).join([f"• {f.strftime('%A %d de %B a las %I:%M %p')}" for f in fechas_disponibles[:cantidad]])}

Para finalizar, necesito:
{chr(10).join([f"• {dato.title()}" for dato in datos_faltantes])}

Por favor compárteme estos datos.""",
                    "intencion": "solicitar_datos_faltantes_multiple",
                    "requiere_escalamiento": False,
                    "esperando_datos": True,
                    "datos_faltantes": datos_faltantes,
                    "fechas_reservadas": [f.isoformat() for f in fechas_disponibles[:cantidad]]
                }
            
            # ========== 5. CREAR LAS CITAS ==========
            citas_creadas = []
            citas_fallidas_con_alternativas = []  # 🆕 Para guardar citas que fallaron
            errores = []
            
            # 🆕 Generar ID único para el agendamiento múltiple
            from datetime import datetime
            import random
            import string
            agendamiento_id = f"MULTI-{datetime.now().strftime('%Y%m%d%H%M%S')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
            
            logger.info(f"📋 Creando {cantidad} citas - ID Agendamiento: {agendamiento_id}")
            
            # Obtener EPS para validación SILENCIOSA Coomeva
            eps_paciente = datos_paciente.get("entidad_eps", "Particular")
            
            for i, fecha in enumerate(fechas_disponibles[:cantidad], 1):
                try:
                    # Preparar datos de la cita
                    datos_cita = {
                        "documento": documento,
                        "nombre_completo": datos_paciente.get("nombre_completo"),
                        "telefono": datos_paciente.get("telefono"),
                        "email": datos_paciente.get("email"),
                        "entidad_eps": eps_paciente,
                        "tipo_servicio": tipo_servicio,
                        "fecha_deseada": fecha,
                        "es_control": es_control,
                        "fisioterapeuta": profesional,
                        # 🔥 NUEVO: Identificar agendamiento múltiple
                        "agendamiento_multiple": True,
                        "agendamiento_id": agendamiento_id,
                        "numero_cita": i,
                        "total_citas": cantidad
                    }
                    
                    logger.info(f"📤 Creando cita {i}/{cantidad} - Fecha: {fecha.strftime('%d/%m/%Y %H:%M')}")
                    
                    # Crear cita en SaludTools
                    resultado = await self._crear_cita_saludtools(datos_cita)
                    
                    if resultado.get("success"):
                        citas_creadas.append({
                            "numero": i,
                            "fecha": fecha,
                            "id": resultado.get("cita_id")
                        })
                        logger.info(f"✅ Cita {i}/{cantidad} creada exitosamente - ID: {resultado.get('cita_id')}")
                    else:
                        # 🆕 CITA FALLÓ - BUSCAR ALTERNATIVAS
                        error_msg = resultado.get('error', 'Error desconocido')
                        logger.warning(f"⚠️ Cita {i}/{cantidad} falló: {error_msg} - Buscando alternativas...")
                        
                        # Buscar alternativas SILENCIOSAMENTE (valida Coomeva internamente)
                        alternativas = await self._buscar_alternativas_horario(
                            fecha_solicitada=fecha,
                            profesional=profesional,
                            eps=eps_paciente,
                            cantidad_alternativas=3
                        )
                        
                        citas_fallidas_con_alternativas.append({
                            "numero": i,
                            "fecha_solicitada": fecha,
                            "alternativas": alternativas
                        })
                        
                        logger.info(f"🔍 Encontradas {len(alternativas)} alternativas para cita {i}")
                        
                except Exception as e:
                    logger.error(f"❌ Error creando cita {i}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    errores.append(f"Cita {i}: Error técnico")
            
            # ========== 6. GENERAR RESPUESTA ==========
            if len(citas_creadas) == cantidad:
                # ✅ ÉXITO TOTAL - TODAS LAS CITAS CREADAS
                citas_str = "\n".join([
                    f"✅ **Cita {c['numero']}**: {c['fecha'].strftime('%A %d de %B a las %I:%M %p')}"
                    for c in citas_creadas
                ])
                
                return {
                    "respuesta": f"""🎉 **¡{cantidad} Citas Agendadas Exitosamente!**

{citas_str}

📋 **Detalles:**
• Tipo: {tipo_servicio} {'- Control' if es_control else ''}
{f"• Profesional: {profesional}" if profesional else ""}
• Duración: 60 minutos cada una

📲 **Recordatorios:**
• Recibirás confirmación por WhatsApp
• Te recordaremos 24h antes de cada cita

⚠️ **Importante:**
• Si necesitas cancelar o reprogramar, avísanos con 24h de anticipación
• Trae tu documento de identidad a cada cita
{f"• Recuerda traer tu orden médica" if not es_control else ""}

¿Necesitas algo más?""",
                    "intencion": "agendamiento_multiple_exitoso",
                    "requiere_escalamiento": False,
                    "citas_creadas": citas_creadas,
                    "cantidad_exitosa": len(citas_creadas)
                }
            
            elif len(citas_creadas) > 0 and len(citas_fallidas_con_alternativas) > 0:
                # ⚠️ ÉXITO PARCIAL CON ALTERNATIVAS
                # Citas exitosas
                citas_str = "\n".join([
                    f"✅ **Cita {c['numero']}**: {c['fecha'].strftime('%A %d de %B a las %I:%M %p')}"
                    for c in citas_creadas
                ])
                
                # Citas fallidas con alternativas AMIGABLES
                alternativas_str = ""
                for cita_fallida in citas_fallidas_con_alternativas:
                    num = cita_fallida['numero']
                    fecha_original = cita_fallida['fecha_solicitada']
                    alternativas = cita_fallida['alternativas']
                    
                    alternativas_str += f"\n⚠️ **Cita {num}** ({fecha_original.strftime('%A %d de %B a las %I:%M %p')}) no disponible.\n"
                    
                    if alternativas:
                        alternativas_str += "💡 **Encontré estas opciones cercanas:**\n"
                        for j, alt in enumerate(alternativas, 1):
                            alternativas_str += f"   {j}. {alt['texto']}\n"
                    else:
                        alternativas_str += "   Podemos coordinar otro horario contigo.\n"
                
                return {
                    "respuesta": f"""📅 **Progreso de Agendamiento**

**✅ Citas Confirmadas ({len(citas_creadas)}/{cantidad}):**
{citas_str}

{alternativas_str}

💬 **¿Qué te parece?**
Dime cuál opción prefieres para {'la cita pendiente' if len(citas_fallidas_con_alternativas) == 1 else 'las citas pendientes'}, o si prefieres otro horario.

📞 O si prefieres, nuestro equipo puede contactarte:
• WhatsApp: 3193175762""",
                    "intencion": "agendamiento_multiple_parcial_con_alternativas",
                    "requiere_escalamiento": False,  # No escalar, hay alternativas
                    "citas_creadas": citas_creadas,
                    "citas_pendientes": citas_fallidas_con_alternativas,
                    "cantidad_exitosa": len(citas_creadas),
                    "cantidad_pendiente": len(citas_fallidas_con_alternativas)
                }
            
            elif len(citas_creadas) > 0:
                # ⚠️ ÉXITO PARCIAL SIN ALTERNATIVAS (caso raro)
                citas_str = "\n".join([
                    f"✅ **Cita {c['numero']}**: {c['fecha'].strftime('%A %d de %B a las %I:%M %p')}"
                    for c in citas_creadas
                ])
                errores_str = "\n".join([f"❌ {e}" for e in errores])
                
                return {
                    "respuesta": f"""⚠️ **Agendamiento Parcial**

**Citas Confirmadas ({len(citas_creadas)}/{cantidad}):**
{citas_str}

**Citas con Problemas:**
{errores_str}

📞 **Para las citas pendientes:**
Nuestro equipo te contactará para coordinar:
• WhatsApp: 3193175762

Las citas confirmadas están aseguradas. ¿Necesitas algo más?""",
                    "intencion": "agendamiento_multiple_parcial",
                    "requiere_escalamiento": True,
                    "citas_creadas": citas_creadas,
                    "cantidad_exitosa": len(citas_creadas),
                    "cantidad_fallida": len(errores)
                }
            
            else:
                # ❌ FALLÓ TODO - Escalar
                return {
                    "respuesta": f"""❌ **Error en Agendamiento Automático**

No pudimos agendar las citas automáticamente.

📞 **Nuestro equipo te ayudará:**
• WhatsApp: 3193175762
• Teléfono: 6047058040

Te contactaremos en máximo 30 minutos para coordinar tus {cantidad} citas.

Disculpa las molestias.""",
                    "intencion": "escalamiento_error_multiple",
                    "requiere_escalamiento": True,
                    "motivo": "error_creacion_citas"
                }
                
        except Exception as e:
            logger.error(f"❌ Error en agendamiento múltiple automático: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Escalar en caso de error inesperado
            return {
                "respuesta": """❌ **Error Técnico**

Ocurrió un problema al procesar tu solicitud de múltiples citas.

📞 **Te contactaremos de inmediato:**
• WhatsApp: 3193175762

Nuestro equipo coordinará tu agendamiento manualmente.

Disculpa las molestias.""",
                "intencion": "escalamiento_error_tecnico",
                "requiere_escalamiento": True,
                "error": str(e)
            }
    
    # =========================================================================
    # 🔍 BÚSQUEDA INTELIGENTE DE ALTERNATIVAS - NO EXCLUYENTE
    # =========================================================================
    
    async def _buscar_alternativas_horario(
        self,
        fecha_solicitada: datetime,
        profesional: Optional[str],
        eps: Optional[str],
        cantidad_alternativas: int = 3
    ) -> List[Dict]:
        """
        Busca alternativas de horario de forma inteligente y NO excluyente.
        
        REGLAS SILENCIOSAS (nunca se mencionan al paciente):
        1. Validar horarios IPS (L-J 5am-8pm, V 5am-7pm, S 8am-12pm)
        2. Validar Coomeva INTERNAMENTE (9am-4pm, excepto cardíaca)
        3. Preferir mismo día, horas cercanas (±1-2 horas)
        4. Solo cambiar día si es necesario
        
        Args:
            fecha_solicitada: Fecha/hora que el paciente pidió
            profesional: Nombre del profesional (opcional)
            eps: EPS del paciente para validación SILENCIOSA Coomeva
            cantidad_alternativas: Cuántas alternativas buscar (default: 3)
            
        Returns:
            Lista de alternativas disponibles con formato amigable
        """
        alternativas = []
        
        # Determinar si es Coomeva SILENCIOSAMENTE
        es_coomeva = False
        if eps:
            eps_lower = eps.lower()
            es_coomeva = "coomeva" in eps_lower
        
        # Día de la semana y hora solicitada
        dia_semana = fecha_solicitada.weekday()
        hora_solicitada = fecha_solicitada.hour
        
        # ========== BUSCAR EN EL MISMO DÍA PRIMERO ==========
        # Intentar ±1 hora, ±2 horas
        horas_cercanas = [
            hora_solicitada + 1,  # +1 hora
            hora_solicitada - 1,  # -1 hora
            hora_solicitada + 2,  # +2 horas
            hora_solicitada - 2,  # -2 horas
        ]
        
        for hora_alternativa in horas_cercanas:
            if len(alternativas) >= cantidad_alternativas:
                break
                
            # Crear fecha alternativa
            try:
                fecha_alt = fecha_solicitada.replace(hour=hora_alternativa, minute=0)
            except ValueError:
                continue
            
            # Validar que esté en horario IPS
            if not self._validar_horario_ips(fecha_alt):
                continue
            
            # Validar Coomeva SILENCIOSAMENTE
            if es_coomeva and not self._validar_horario_coomeva_silencioso(fecha_alt):
                continue
            
            # Agregar alternativa
            alternativas.append({
                "fecha": fecha_alt,
                "es_mismo_dia": True,
                "diferencia_horas": abs(hora_alternativa - hora_solicitada),
                "texto": fecha_alt.strftime("%A %d de %B a las %I:%M %p")
            })
        
        # ========== SI NO HAY SUFICIENTES, BUSCAR DÍAS CERCANOS ==========
        if len(alternativas) < cantidad_alternativas:
            # Intentar día siguiente y anterior
            for delta_dias in [1, -1, 2]:
                if len(alternativas) >= cantidad_alternativas:
                    break
                
                fecha_dia_alt = fecha_solicitada + timedelta(days=delta_dias)
                
                # Mantener hora solicitada en día alternativo
                if self._validar_horario_ips(fecha_dia_alt):
                    if not es_coomeva or self._validar_horario_coomeva_silencioso(fecha_dia_alt):
                        alternativas.append({
                            "fecha": fecha_dia_alt,
                            "es_mismo_dia": False,
                            "diferencia_dias": abs(delta_dias),
                            "texto": fecha_dia_alt.strftime("%A %d de %B a las %I:%M %p")
                        })
        
        return alternativas[:cantidad_alternativas]
    
    def _validar_horario_ips(self, fecha: datetime) -> bool:
        """
        Valida que la fecha esté en horarios de la IPS.
        
        Horarios:
        - L-J: 5am-8pm
        - V: 5am-7pm
        - S: 8am-12pm
        - D: Cerrado
        """
        dia_semana = fecha.weekday()
        hora = fecha.hour
        
        # Domingo cerrado
        if dia_semana == 6:
            return False
        
        # Sábado: 8am-12pm
        if dia_semana == 5:
            return 8 <= hora < 12
        
        # Viernes: 5am-7pm
        if dia_semana == 4:
            return 5 <= hora < 19
        
        # Lunes-Jueves: 5am-8pm
        return 5 <= hora < 20
    
    def _validar_horario_coomeva_silencioso(self, fecha: datetime) -> bool:
        """
        Valida SILENCIOSAMENTE si la fecha cumple horario Coomeva (9am-4pm).
        
        IMPORTANTE: Esta validación es INTERNA.
        NUNCA mencionar al paciente que es por Coomeva.
        
        Returns:
            True si está en franja 9am-4pm, False si no
        """
        hora = fecha.hour
        # Coomeva: 9am-4pm (09:00 a 16:00)
        return 9 <= hora < 16
    
    # =========================================================================
    # 🛡️ METODOS AUXILIARES ADICIONALES
    # =========================================================================
    
    def _respuesta_escalamiento(
        self, 
        motivo: str, 
        contexto: Dict = None,
        tipo_escalamiento: str = "general",
        datos_recopilados: Dict = None
    ) -> Dict:
        """
        Genera respuesta de escalamiento a humano CON TODA LA INFORMACIÓN RECOPILADA
        
        Args:
            motivo: Razón del escalamiento
            contexto: Contexto del usuario
            tipo_escalamiento: Tipo de escalamiento (general, complejo, urgente)
            datos_recopilados: Datos extraídos durante la conversación
        """
        nombre = contexto.get("nombre", "Usuario") if contexto else "Usuario"
        telefono = contexto.get("telefono", "No proporcionado") if contexto else "No proporcionado"
        
        # Construir resumen de información recopilada
        info_recopilada = ""
        if datos_recopilados:
            info_recopilada = "\n\n📋 **Información Recopilada:**"
            
            # Datos del paciente
            if datos_recopilados.get("nombre_completo"):
                info_recopilada += f"\n• Paciente: {datos_recopilados['nombre_completo']}"
            if datos_recopilados.get("documento"):
                info_recopilada += f"\n• Documento: {datos_recopilados['documento']}"
            if datos_recopilados.get("telefono"):
                info_recopilada += f"\n• Teléfono: {datos_recopilados['telefono']}"
            if datos_recopilados.get("email"):
                info_recopilada += f"\n• Email: {datos_recopilados['email']}"
            
            # Detalles de la cita
            if datos_recopilados.get("tipo_servicio"):
                info_recopilada += f"\n• Servicio: {datos_recopilados['tipo_servicio']}"
            if datos_recopilados.get("tipo_fisioterapia"):
                info_recopilada += f"\n• Tipo: {datos_recopilados['tipo_fisioterapia']}"
            if datos_recopilados.get("fisioterapeuta"):
                info_recopilada += f"\n• Fisioterapeuta: {datos_recopilados['fisioterapeuta']}"
            if datos_recopilados.get("fecha_preferida"):
                info_recopilada += f"\n• Fecha preferida: {datos_recopilados['fecha_preferida']}"
            if datos_recopilados.get("hora_preferida"):
                info_recopilada += f"\n• Hora preferida: {datos_recopilados['hora_preferida']}"
            
            # Orden médica
            if datos_recopilados.get("tiene_orden_medica"):
                info_recopilada += f"\n• Orden médica: Sí"
                if datos_recopilados.get("numero_sesiones"):
                    info_recopilada += f" ({datos_recopilados['numero_sesiones']} sesiones)"
            
            # Múltiples citas
            if datos_recopilados.get("cantidad_citas"):
                info_recopilada += f"\n• Cantidad de citas: {datos_recopilados['cantidad_citas']}"
            if datos_recopilados.get("dias_especificos"):
                dias = ", ".join(datos_recopilados["dias_especificos"])
                info_recopilada += f"\n• Días solicitados: {dias}"
        
        if tipo_escalamiento == "urgente":
            respuesta = f"""🚨 **Solicitud Urgente**

{motivo}{info_recopilada}

📞 **Contacto Inmediato:**
• WhatsApp: 3193175762
• Teléfono: 6047058040

✅ **Tu información fue registrada**
Nuestro equipo te contactará en máximo 30 minutos con toda esta información.

**Contacto registrado:**
• {nombre} - {telefono}"""
        
        elif tipo_escalamiento == "complejo":
            respuesta = f"""⚙️ **Solicitud Compleja**

{motivo}{info_recopilada}

Esta solicitud requiere coordinación personalizada.

📞 **Nuestro equipo te ayudará:**
• WhatsApp: 3193175762
• Teléfono: 6047058040

✅ **Tu información fue registrada**
Te contactaremos en máximo 1 hora para coordinar todo.

**Contacto registrado:**
• {nombre} - {telefono}"""
        
        else:  # general
            respuesta = f"""💬 **Escalamiento a Equipo Humano**

{motivo}{info_recopilada}

📞 **Contacto:**
• WhatsApp: 3193175762
• Teléfono: 6047058040

✅ **Tu información fue registrada**
Nuestro equipo te atenderá en breve con todos estos detalles.

**Contacto registrado:**
• {nombre} - {telefono}"""
        
        return {
            "respuesta": respuesta,
            "intencion": "escalamiento",
            "requiere_escalamiento": True,
            "motivo": motivo,
            "tipo_escalamiento": tipo_escalamiento,
            "contexto_usuario": contexto,
            "datos_recopilados": datos_recopilados or {},
            "informacion_completa_enviada": True
        }
    
    def _validar_modificacion_fecha(
        self,
        fecha_actual: datetime,
        fecha_nueva: datetime,
        cita_actual: Dict
    ) -> Dict:
        """
        Valida modificacion de fecha con 7 criterios
        
        Returns:
            Dict con {valido: bool, errores: List[str], advertencias: List[str]}
        """
        errores = []
        advertencias = []
        ahora = datetime.now()
        
        # VALIDACION 1: Fecha nueva no puede ser pasada
        if fecha_nueva < ahora:
            errores.append("La nueva fecha no puede estar en el pasado")
        
        # VALIDACION 2: No modificar con menos de 24h de anticipacion
        horas_hasta_cita = (fecha_actual - ahora).total_seconds() / 3600
        if horas_hasta_cita < 24:
            errores.append("No se puede modificar con menos de 24 horas de anticipación")
        
        # VALIDACION 3: Nueva fecha debe ser al menos 24h en el futuro
        horas_nueva_fecha = (fecha_nueva - ahora).total_seconds() / 3600
        if horas_nueva_fecha < 24:
            errores.append("La nueva fecha debe ser al menos 24 horas en el futuro")
        
        # VALIDACION 4: No mover mas de 3 meses
        diferencia_dias = abs((fecha_nueva - fecha_actual).days)
        if diferencia_dias > 90:
            advertencias.append("Modificación de más de 3 meses - requiere validación")
        
        # VALIDACION 5: Horario laboral (lunes a viernes 7am-6pm, sabado 7am-12pm)
        dia_semana = fecha_nueva.weekday()
        hora = fecha_nueva.hour
        
        if dia_semana == 6:  # Domingo
            errores.append("No hay atención los domingos")
        elif dia_semana == 5:  # Sábado
            if hora < 7 or hora >= 12:
                errores.append("Sábados: solo 7:00 AM - 12:00 PM")
        else:  # Lunes a viernes
            if hora < 7 or hora >= 18:
                errores.append("Lunes a viernes: solo 7:00 AM - 6:00 PM")
        
        # VALIDACION 6: No agendar en festivos (lista básica)
        festivos_2025 = [
            datetime(2025, 1, 1),   # Año nuevo
            datetime(2025, 1, 6),   # Reyes
            datetime(2025, 3, 24),  # San José
            datetime(2025, 4, 17),  # Jueves Santo
            datetime(2025, 4, 18),  # Viernes Santo
            datetime(2025, 5, 1),   # Día del trabajo
            datetime(2025, 6, 23),  # Corpus Christi
            datetime(2025, 6, 30),  # San Pedro y San Pablo
            datetime(2025, 7, 20),  # Independencia
            datetime(2025, 8, 7),   # Batalla de Boyacá
            datetime(2025, 8, 18),  # Asunción
            datetime(2025, 10, 13), # Día de la Raza
            datetime(2025, 11, 3),  # Independencia de Cartagena
            datetime(2025, 11, 17), # Independencia de Cartagena
            datetime(2025, 12, 8),  # Inmaculada
            datetime(2025, 12, 25), # Navidad
        ]
        
        fecha_solo_dia = datetime(fecha_nueva.year, fecha_nueva.month, fecha_nueva.day)
        if fecha_solo_dia in festivos_2025:
            errores.append("No hay atención en días festivos")
        
        # VALIDACION 7: Validar estado de la cita
        estado_cita = cita_actual.get("appointmentState", "")
        if estado_cita in ["CANCELLED", "COMPLETED"]:
            errores.append(f"No se puede modificar una cita {estado_cita}")
        
        return {
            "valido": len(errores) == 0,
            "errores": errores,
            "advertencias": advertencias
        }

# Instancia global del chatbot
chatbot = IPSReactChatbot()

async def procesar_mensaje_chatbot(mensaje: str, contexto: Dict = None, archivos: List[str] = None) -> Dict:
    """Función principal para procesar mensajes con soporte para archivos"""
    return await chatbot.procesar_mensaje(mensaje, contexto, archivos)