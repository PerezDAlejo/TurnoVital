"""
SISTEMA DE REINTENTOS INTELIGENTE PARA OCR - IPS REACT
======================================================
Maneja reintentos automáticos cuando el OCR falla, con mensajes específicos según el tipo de error.

ARQUITECTURA HÍBRIDA DE IA:
---------------------------
- CHAT CONVERSACIONAL: Gemini 2.0 Flash (rápido, económico, 96% ahorro)
- OCR ÓRDENES MÉDICAS: GPT-4o Vision (precisión médica crítica, 86% probado)
- COSTO TOTAL: ~$77,500 COP/mes para 2500 pacientes (vs $650,000 solo GPT-4o)

FUNCIONALIDADES:
----------------
1. Contador de reintentos por teléfono (máximo 3 intentos)
2. Detección inteligente de tipos de error (borrosa, oscura, sin texto, rotada)
3. Mensajes específicos para cada tipo de error
4. Escalamiento automático a secretaria después de 3 intentos fallidos
5. Reseteo automático después de éxito o escalamiento

Autor: Alejandro Pérez Dávila
Fecha: Diciembre 2025
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TipoErrorOCR(Enum):
    """Tipos de errores detectables en el procesamiento OCR"""
    IMAGEN_BORROSA = "imagen_borrosa"
    SIN_TEXTO = "sin_texto"
    IMAGEN_OSCURA = "imagen_oscura"
    IMAGEN_ROTADA = "rotada"
    FORMATO_INVALIDO = "formato_invalido"
    IMAGEN_CORRUPTA = "corrupta"
    ERROR_GENERAL = "general"


@dataclass
class EstadoReintento:
    """Estado de reintentos para un teléfono específico"""
    telefono: str
    intentos: int
    ultimo_error: Optional[TipoErrorOCR]
    timestamp_ultimo_intento: datetime
    historial_errores: list
    
    def puede_reintentar(self, max_intentos: int = 3) -> bool:
        """Verifica si aún puede reintentar"""
        return self.intentos < max_intentos
    
    def incrementar_intento(self, tipo_error: TipoErrorOCR):
        """Incrementa contador y registra error"""
        self.intentos += 1
        self.ultimo_error = tipo_error
        self.timestamp_ultimo_intento = datetime.now()
        self.historial_errores.append({
            "intento": self.intentos,
            "error": tipo_error.value,
            "timestamp": self.timestamp_ultimo_intento.isoformat()
        })
    
    def resetear(self):
        """Resetea el estado después de éxito o escalamiento"""
        self.intentos = 0
        self.ultimo_error = None
        self.historial_errores = []


class SistemaReintentosOCR:
    """
    Sistema centralizado para manejar reintentos de OCR.
    
    Características:
    - Máximo 3 intentos por teléfono
    - Mensajes personalizados según tipo de error
    - Escalamiento automático al fallar 3 veces
    - Limpieza automática de estados antiguos (>24 horas)
    """
    
    def __init__(self, max_intentos: int = 3):
        """
        Inicializa el sistema de reintentos.
        
        Args:
            max_intentos: Número máximo de intentos antes de escalar (default: 3)
        """
        self.max_intentos = max_intentos
        self.estados: Dict[str, EstadoReintento] = {}
        
        # Mensajes específicos por tipo de error
        self.mensajes_error = {
            TipoErrorOCR.IMAGEN_BORROSA: (
                "📸 La imagen está borrosa y no puedo leer el texto claramente.\n\n"
                "💡 **Consejo:** Intenta tomar la foto con mejor enfoque y asegúrate de que "
                "el documento esté bien iluminado."
            ),
            TipoErrorOCR.SIN_TEXTO: (
                "📄 No detecto texto legible en la imagen.\n\n"
                "💡 **Consejo:** Asegúrate de que la imagen contenga el documento completo "
                "y esté en posición correcta. Si es un PDF, intenta enviarlo como documento."
            ),
            TipoErrorOCR.IMAGEN_OSCURA: (
                "💡 La imagen está muy oscura y dificulta la lectura.\n\n"
                "**Consejo:** Intenta tomar la foto con mejor iluminación. "
                "Si es posible, usa luz natural o enciende más luces."
            ),
            TipoErrorOCR.IMAGEN_ROTADA: (
                "🔄 Parece que la imagen está rotada o en posición incorrecta.\n\n"
                "💡 **Consejo:** Envía la imagen en posición vertical con el texto legible. "
                "Asegúrate de que el documento esté derecho."
            ),
            TipoErrorOCR.FORMATO_INVALIDO: (
                "⚠️ El formato del archivo no es compatible.\n\n"
                "💡 **Consejo:** Envía la orden médica como imagen (JPG, PNG) o PDF. "
                "Evita formatos comprimidos o documentos de Word."
            ),
            TipoErrorOCR.IMAGEN_CORRUPTA: (
                "❌ El archivo está corrupto y no puedo abrirlo.\n\n"
                "💡 **Consejo:** Intenta tomar una nueva foto o reenviar el documento. "
                "Si el problema persiste, prueba con otro dispositivo."
            ),
            TipoErrorOCR.ERROR_GENERAL: (
                "⚠️ No pude procesar tu orden médica correctamente.\n\n"
                "💡 **Consejo:** Intenta enviarla nuevamente asegurándote de que:\n"
                "• La imagen esté clara y bien iluminada\n"
                "• El texto sea legible\n"
                "• El documento esté completo"
            )
        }
        
        logger.info("✅ Sistema de reintentos OCR inicializado (max_intentos=%d)", max_intentos)
    
    def obtener_estado(self, telefono: str) -> EstadoReintento:
        """
        Obtiene o crea el estado de reintentos para un teléfono.
        
        Args:
            telefono: Número de teléfono del usuario
            
        Returns:
            EstadoReintento: Estado actual de reintentos
        """
        if telefono not in self.estados:
            self.estados[telefono] = EstadoReintento(
                telefono=telefono,
                intentos=0,
                ultimo_error=None,
                timestamp_ultimo_intento=datetime.now(),
                historial_errores=[]
            )
        return self.estados[telefono]
    
    def detectar_tipo_error(
        self, 
        texto_extraido: str, 
        confianza: float, 
        error_mensaje: str = ""
    ) -> TipoErrorOCR:
        """
        Detecta el tipo de error basándose en el resultado del OCR.
        
        Args:
            texto_extraido: Texto extraído por el OCR (puede estar vacío)
            confianza: Nivel de confianza del OCR (0.0 a 1.0)
            error_mensaje: Mensaje de error si lo hubo
            
        Returns:
            TipoErrorOCR: Tipo de error detectado
        """
        # Verificar mensajes de error explícitos
        if error_mensaje:
            error_lower = error_mensaje.lower()
            
            if "corrupted" in error_lower or "corrupt" in error_lower:
                return TipoErrorOCR.IMAGEN_CORRUPTA
            
            if "format" in error_lower or "invalid" in error_lower:
                return TipoErrorOCR.FORMATO_INVALIDO
            
            if "can't assist" in error_lower or "cannot assist" in error_lower:
                # OpenAI rechazó la imagen por contenido
                return TipoErrorOCR.ERROR_GENERAL
        
        # Análisis del texto extraído
        if not texto_extraido or len(texto_extraido.strip()) < 20:
            return TipoErrorOCR.SIN_TEXTO
        
        # Análisis de confianza
        if confianza < 0.3:
            return TipoErrorOCR.IMAGEN_BORROSA
        
        if confianza < 0.5:
            # Verificar si puede ser imagen oscura o rotada
            # (heurística: texto muy corto con baja confianza)
            if len(texto_extraido.strip()) < 100:
                return TipoErrorOCR.IMAGEN_OSCURA
            return TipoErrorOCR.IMAGEN_ROTADA
        
        # Si llegamos aquí, es un error general
        return TipoErrorOCR.ERROR_GENERAL
    
    def registrar_intento_fallido(
        self, 
        telefono: str, 
        texto_extraido: str = "", 
        confianza: float = 0.0,
        error_mensaje: str = ""
    ) -> Tuple[bool, str, int]:
        """
        Registra un intento fallido de OCR.
        
        Args:
            telefono: Número de teléfono del usuario
            texto_extraido: Texto extraído (si lo hubo)
            confianza: Nivel de confianza del OCR
            error_mensaje: Mensaje de error si lo hubo
            
        Returns:
            Tuple[bool, str, int]: (debe_escalar, mensaje_usuario, intentos_realizados)
        """
        estado = self.obtener_estado(telefono)
        tipo_error = self.detectar_tipo_error(texto_extraido, confianza, error_mensaje)
        
        estado.incrementar_intento(tipo_error)
        intentos_realizados = estado.intentos
        
        logger.warning(
            "⚠️ [%s] Intento OCR %d/%d fallido - Error: %s",
            telefono, intentos_realizados, self.max_intentos, tipo_error.value
        )
        
        # Verificar si debe escalar
        debe_escalar = not estado.puede_reintentar(self.max_intentos)
        
        if debe_escalar:
            mensaje = self._generar_mensaje_escalamiento(estado)
            logger.error(
                "🚨 [%s] Máximo de reintentos alcanzado (%d) - Escalando a secretaria",
                telefono, self.max_intentos
            )
        else:
            mensaje = self._generar_mensaje_reintento(tipo_error, intentos_realizados)
        
        return (debe_escalar, mensaje, intentos_realizados)
    
    def registrar_exito(self, telefono: str):
        """
        Registra un OCR exitoso y resetea el contador.
        
        Args:
            telefono: Número de teléfono del usuario
        """
        if telefono in self.estados:
            logger.info("✅ [%s] OCR exitoso - Reseteando contador de reintentos", telefono)
            self.estados[telefono].resetear()
    
    def resetear_estado(self, telefono: str):
        """
        Resetea el estado de reintentos para un teléfono.
        
        Args:
            telefono: Número de teléfono del usuario
        """
        if telefono in self.estados:
            logger.info("🔄 [%s] Reseteando estado de reintentos manualmente", telefono)
            del self.estados[telefono]
    
    def _generar_mensaje_reintento(self, tipo_error: TipoErrorOCR, intento_actual: int) -> str:
        """
        Genera mensaje de reintento personalizado según el tipo de error.
        
        Args:
            tipo_error: Tipo de error detectado
            intento_actual: Número de intento actual
            
        Returns:
            str: Mensaje para el usuario
        """
        mensaje_base = self.mensajes_error.get(tipo_error, self.mensajes_error[TipoErrorOCR.ERROR_GENERAL])
        
        mensaje = f"{mensaje_base}\n\n"
        mensaje += f"📊 **Intento {intento_actual} de {self.max_intentos}**\n\n"
        mensaje += "Por favor, intenta enviar la orden médica nuevamente siguiendo los consejos. 📸"
        
        return mensaje
    
    def _generar_mensaje_escalamiento(self, estado: EstadoReintento) -> str:
        """
        Genera mensaje de escalamiento cuando se agotan los reintentos.
        
        Args:
            estado: Estado actual de reintentos
            
        Returns:
            str: Mensaje de escalamiento
        """
        mensaje = (
            "😔 He tenido dificultades procesando tu orden médica después de "
            f"{self.max_intentos} intentos.\n\n"
            "🙋‍♀️ **Una secretaria se contactará contigo pronto** para ayudarte "
            "personalmente con tu agendamiento.\n\n"
            "Gracias por tu paciencia. 🙏"
        )
        return mensaje
    
    def limpiar_estados_antiguos(self, horas: int = 24):
        """
        Limpia estados de reintentos más antiguos que X horas.
        
        Args:
            horas: Horas de antigüedad para limpiar (default: 24)
        """
        ahora = datetime.now()
        limite = ahora - timedelta(hours=horas)
        
        estados_a_eliminar = [
            telefono for telefono, estado in self.estados.items()
            if estado.timestamp_ultimo_intento < limite
        ]
        
        for telefono in estados_a_eliminar:
            logger.info("🧹 Limpiando estado antiguo de reintentos para %s", telefono)
            del self.estados[telefono]
        
        if estados_a_eliminar:
            logger.info("✅ Limpiados %d estados antiguos de reintentos", len(estados_a_eliminar))
    
    def obtener_estadisticas(self) -> Dict:
        """
        Obtiene estadísticas del sistema de reintentos.
        
        Returns:
            Dict: Estadísticas generales
        """
        total_usuarios = len(self.estados)
        usuarios_con_errores = sum(1 for e in self.estados.values() if e.intentos > 0)
        
        distribucion_errores = {}
        for estado in self.estados.values():
            if estado.ultimo_error:
                tipo = estado.ultimo_error.value
                distribucion_errores[tipo] = distribucion_errores.get(tipo, 0) + 1
        
        return {
            "total_usuarios_con_estado": total_usuarios,
            "usuarios_con_errores": usuarios_con_errores,
            "distribucion_errores": distribucion_errores,
            "max_intentos_configurado": self.max_intentos
        }


# Instancia global del sistema de reintentos
sistema_reintentos_ocr = SistemaReintentosOCR(max_intentos=3)
