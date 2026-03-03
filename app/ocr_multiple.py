"""
🔍 OCR MÚLTIPLES IMÁGENES - VERSIÓN INTELIGENTE CON BASE DE DATOS
Extrae texto de múltiples imágenes con cache inteligente y aprendizaje
"""
from __future__ import annotations
import os, io, logging, asyncio, hashlib
from typing import Optional, List, Dict, Any
import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15.0
MAX_IMAGES_PER_MESSAGE = 10
MAX_TEXT_LENGTH = 8000  # Incrementado para múltiples imágenes

# Verificar dependencias OCR
try:
    import pytesseract
    from PIL import Image
    
    # Configurar PATH de Tesseract para Windows
    if os.name == 'nt':  # Windows
        tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            logger.info(f"Tesseract configurado en: {tesseract_path}")
        else:
            logger.warning("Tesseract no encontrado en la ruta por defecto")
    
    _OCR_AVAILABLE = True
    logger.info("OCR disponible y configurado")
except Exception as e:
    _OCR_AVAILABLE = False
    logger.warning(f"OCR no disponible: {e}")

# Importar cache inteligente
try:
    from app.services.ocr_cache import ocr_cache, smart_validator
    _CACHE_AVAILABLE = True
except Exception:
    _CACHE_AVAILABLE = False
    logger.warning("Cache OCR no disponible")

def ocr_enabled() -> bool:
    """Verifica si OCR está habilitado"""
    return os.getenv("OCR_ENABLED", "0").lower() in {"1","true","yes","on"}

async def extract_text_from_local_file(file_path: str) -> Optional[str]:
    """Extrae texto de un archivo local de imagen"""
    print(f"[OCR] 🔍 Iniciando extracción para: {file_path}")
    
    if not ocr_enabled():
        print(f"[OCR] ❌ OCR deshabilitado en configuración")
        return None
    
    if not _OCR_AVAILABLE:
        print(f"[OCR] ❌ OCR no disponible (falta Tesseract/PIL)")
        return None
        return None
    
    try:
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Archivo no existe: {file_path}")
            return None
        
        # Abrir imagen directamente desde archivo local
        img = Image.open(path)
        text = pytesseract.image_to_string(img, lang=os.getenv("OCR_LANG", "spa+eng"))
        text = (text or "").strip()
        
        if not text:
            return None
        
        return text
        
    except Exception as e:
        logger.warning(f"OCR fallo para archivo local {file_path}: {e}")
        return None

class OCRFallbackManager:
    """Gestor de mecanismos de fallback para OCR"""

    def __init__(self):
        self.max_retries = 3
        self.retry_delays = [1, 2, 4]  # Segundos entre reintentos

    async def process_with_fallback(self, url: str, telefono: str = None) -> Dict[str, Any]:
        """Procesa imagen con múltiples estrategias de fallback"""
        result = {
            "success": False,
            "text": None,
            "method_used": None,
            "error_details": [],
            "quality_assessment": {},
            "fallback_attempts": 0
        }

        # Estrategia 1: OCR estándar
        text = await self._try_standard_ocr(url, telefono)
        if text:
            result.update({
                "success": True,
                "text": text,
                "method_used": "standard_ocr"
            })
            return result

        result["fallback_attempts"] += 1
        result["error_details"].append("standard_ocr_failed")

        # Estrategia 2: OCR con preprocesamiento mejorado
        enhanced_text = await self._try_enhanced_ocr(url, telefono)
        if enhanced_text:
            result.update({
                "success": True,
                "text": enhanced_text,
                "method_used": "enhanced_ocr"
            })
            return result

        result["fallback_attempts"] += 1
        result["error_details"].append("enhanced_ocr_failed")

        # Estrategia 3: OCR con configuración alternativa
        alt_text = await self._try_alternative_config_ocr(url, telefono)
        if alt_text:
            result.update({
                "success": True,
                "text": alt_text,
                "method_used": "alternative_config"
            })
            return result

        result["fallback_attempts"] += 1
        result["error_details"].append("alternative_config_failed")

        # Estrategia 4: Fallback a análisis básico de imagen
        basic_analysis = await self._try_basic_image_analysis(url)
        if basic_analysis:
            result.update({
                "success": True,
                "text": basic_analysis.get("extracted_text", ""),
                "method_used": "basic_analysis",
                "quality_assessment": basic_analysis.get("assessment", {})
            })
            return result

        result["fallback_attempts"] += 1
        result["error_details"].append("basic_analysis_failed")

        return result

    async def _try_standard_ocr(self, url: str, telefono: str = None) -> Optional[str]:
        """Intenta OCR estándar con reintentos"""
        for attempt in range(self.max_retries):
            try:
                text = await self._perform_ocr(url, telefono, config="standard")
                if text and len(text.strip()) > 10:  # Mínimo de calidad
                    return text
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delays[attempt])
            except Exception as e:
                logger.warning(f"OCR attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delays[attempt])
        return None

    async def _try_enhanced_ocr(self, url: str, telefono: str = None) -> Optional[str]:
        """Intenta OCR con preprocesamiento mejorado"""
        try:
            # Descargar imagen
            image_data = await self._download_image(url)
            if not image_data:
                return None

            # Aplicar preprocesamiento
            processed_image = self._preprocess_image(image_data)

            # Extraer texto con configuración optimizada
            text = await self._perform_ocr_on_image(processed_image, config="enhanced")
            return text.strip() if text else None

        except Exception as e:
            logger.warning(f"Enhanced OCR failed: {e}")
            return None

    async def _try_alternative_config_ocr(self, url: str, telefono: str = None) -> Optional[str]:
        """Intenta OCR con configuración alternativa"""
        try:
            # Probar diferentes configuraciones de Tesseract
            configs = ["spa", "eng", "spa+eng", "spa+eng+fra"]

            for config in configs:
                text = await self._perform_ocr(url, telefono, config=config)
                if text and len(text.strip()) > 5:
                    return text

            return None

        except Exception as e:
            logger.warning(f"Alternative config OCR failed: {e}")
            return None

    async def _try_basic_image_analysis(self, url: str) -> Optional[Dict[str, Any]]:
        """Análisis básico de imagen cuando OCR falla completamente"""
        try:
            # Descargar imagen
            image_data = await self._download_image(url)
            if not image_data:
                return None

            img = Image.open(io.BytesIO(image_data))

            # Análisis básico
            assessment = {
                "image_size": img.size,
                "image_mode": img.mode,
                "estimated_quality": "low",
                "has_text_regions": False,
                "extracted_text": ""
            }

            # Verificar si hay regiones con texto potencial
            # (lógica simplificada - en producción usar librerías de análisis de imagen)
            width, height = img.size
            if width > 100 and height > 100:
                assessment["estimated_quality"] = "medium"
                assessment["has_text_regions"] = True
                assessment["extracted_text"] = "[IMAGEN CON TEXTO POTENCIAL - OCR FALLÓ]"

            return assessment

        except Exception as e:
            logger.warning(f"Basic image analysis failed: {e}")
            return None

    async def _download_image(self, url: str) -> Optional[bytes]:
        """Descarga imagen con manejo de errores mejorado"""
        try:
            auth = None
            if "api.twilio.com" in url:
                account_sid = os.getenv("TWILIO_ACCOUNT_SID")
                auth_token = os.getenv("TWILIO_AUTH_TOKEN")
                if account_sid and auth_token:
                    auth = (account_sid, auth_token)

            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
                r = await client.get(url, auth=auth)
                r.raise_for_status()

                content_type = r.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    return None

                return r.content

        except Exception as e:
            logger.warning(f"Image download failed: {e}")
            return None

    def _preprocess_image(self, image_data: bytes) -> Image.Image:
        """Preprocesa imagen para mejorar OCR"""
        img = Image.open(io.BytesIO(image_data))

        # Convertir a escala de grises si no lo está
        if img.mode != 'L':
            img = img.convert('L')

        # Mejorar contraste
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # Redimensionar si es muy pequeña
        width, height = img.size
        if width < 300 or height < 300:
            scale_factor = max(300 / width, 300 / height)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return img

    async def _perform_ocr(self, url: str, telefono: str = None, config: str = "standard") -> Optional[str]:
        """Realiza OCR con configuración específica"""
        try:
            # Descargar imagen
            image_data = await self._download_image(url)
            if not image_data:
                return None

            img = Image.open(io.BytesIO(image_data))

            # Configuración OCR
            lang = os.getenv("OCR_LANG", "spa+eng")
            if config == "enhanced":
                img = self._preprocess_image(image_data)
            elif config != "standard":
                lang = config

            text = pytesseract.image_to_string(img, lang=lang)
            return text.strip() if text else None

        except Exception as e:
            logger.warning(f"OCR performance failed: {e}")
            return None

    async def _perform_ocr_on_image(self, img: Image.Image, config: str = "standard") -> Optional[str]:
        """Realiza OCR directamente en imagen PIL"""
        try:
            lang = os.getenv("OCR_LANG", "spa+eng")
            text = pytesseract.image_to_string(img, lang=lang)
            return text.strip() if text else None
        except Exception as e:
            return None

# Instancia global del gestor de fallback
ocr_fallback_manager = OCRFallbackManager()

async def extract_text_from_single_image(url: str, telefono: str = None) -> Optional[str]:
    """Extrae texto de una sola imagen con cache inteligente y fallback avanzado"""
    if not ocr_enabled() or not _OCR_AVAILABLE:
        return None

    # Si parece una ruta local, usar la función para archivos locales
    if not url.startswith(("http://", "https://")) and ("/" in url or "\\" in url):
        return await extract_text_from_local_file(url)

    image_data = None
    image_hash = None

    try:
        # Usar el gestor de fallback para procesar la imagen
        fallback_result = await ocr_fallback_manager.process_with_fallback(url, telefono)

        if not fallback_result["success"]:
            logger.warning(f"OCR: Todos los métodos de fallback fallaron para {url}")
            return None

        text = fallback_result["text"]
        method_used = fallback_result["method_used"]

        logger.info(f"OCR: Texto extraído exitosamente con método '{method_used}' ({len(text)} caracteres)")

        # Generar hash para cache
        if _CACHE_AVAILABLE:
            # Descargar imagen para generar hash
            image_data = await ocr_fallback_manager._download_image(url)
            if image_data:
                image_hash = hashlib.sha256(image_data).hexdigest()

                # Verificar cache primero (solo si tenemos hash)
                cached_result = ocr_cache.get_cached_result(image_hash)
                if cached_result:
                    logger.info("OCR: Usando resultado desde cache")
                    return cached_result.get("ocr_text")

                # Guardar en cache si está disponible
                medical_info = _extract_medical_info_simple(text)
                confidence_analysis = medical_info.get("confidence_analysis", {})
                confidence_score = confidence_analysis.get("overall_confidence", len(text) / 1000.0)

                ocr_cache.save_result(
                    image_hash=image_hash,
                    ocr_text=text,
                    medical_info=medical_info,
                    confidence_score=min(confidence_score, 1.0),
                    telefono=telefono
                )

        return text

    except Exception as e:
        logger.warning(f"OCR fallo completo para imagen {url}: {e}")
        return None

class ConfidenceScorer:
    """Sistema avanzado de puntuación de confianza para OCR"""

    def __init__(self):
        self.min_confidence_threshold = 0.3
        self.high_confidence_threshold = 0.8

    def calculate_overall_confidence(self, text: str, medical_info: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula confianza general del OCR y entidades extraídas"""
        scores = {
            "text_quality_score": self._calculate_text_quality_score(text),
            "entity_recognition_score": self._calculate_entity_recognition_score(medical_info),
            "document_structure_score": self._calculate_document_structure_score(text),
            "pattern_matching_score": self._calculate_pattern_matching_score(text, medical_info)
        }

        # Puntuación ponderada general
        weights = {
            "text_quality_score": 0.3,
            "entity_recognition_score": 0.4,
            "document_structure_score": 0.2,
            "pattern_matching_score": 0.1
        }

        overall_score = sum(scores[key] * weights[key] for key in scores.keys())
        overall_score = min(1.0, max(0.0, overall_score))

        return {
            "overall_confidence": overall_score,
            "confidence_level": self._get_confidence_level(overall_score),
            "detailed_scores": scores,
            "recommendations": self._generate_confidence_recommendations(overall_score, scores)
        }

    def _calculate_text_quality_score(self, text: str) -> float:
        """Evalúa calidad del texto extraído"""
        if not text or not text.strip():
            return 0.0

        score = 0.0
        text_length = len(text.strip())

        # Longitud del texto (mínimo 50 caracteres para ser útil)
        if text_length >= 50:
            score += 0.3
        elif text_length >= 20:
            score += 0.15

        # Presencia de caracteres alfanuméricos
        alpha_ratio = sum(c.isalpha() for c in text) / text_length if text_length > 0 else 0
        if alpha_ratio > 0.6:
            score += 0.3
        elif alpha_ratio > 0.3:
            score += 0.15

        # Ausencia de caracteres basura (símbolos excesivos)
        symbol_ratio = sum(not c.isalnum() and not c.isspace() for c in text) / text_length if text_length > 0 else 0
        if symbol_ratio < 0.2:
            score += 0.2
        elif symbol_ratio < 0.4:
            score += 0.1

        # Presencia de palabras completas
        words = text.split()
        avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
        if avg_word_length >= 4:
            score += 0.2

        return min(1.0, score)

    def _calculate_entity_recognition_score(self, medical_info: Dict[str, Any]) -> float:
        """Evalúa calidad del reconocimiento de entidades"""
        score = 0.0
        entities_found = 0
        total_entities = 0

        # Evaluar nombre del paciente
        if medical_info.get("patient_name"):
            entities_found += 1
            # Verificar formato de nombre (al menos dos palabras, capitalizadas)
            name_parts = medical_info["patient_name"].split()
            if len(name_parts) >= 2 and all(part[0].isupper() for part in name_parts if part):
                score += 0.15
            else:
                score += 0.05
        total_entities += 1

        # Evaluar documento de identidad
        if medical_info.get("document_id"):
            entities_found += 1
            doc_id = medical_info["document_id"]
            # Verificar formato de cédula colombiano (6-15 dígitos)
            if doc_id.isdigit() and 6 <= len(doc_id) <= 15:
                score += 0.15
            else:
                score += 0.05
        total_entities += 1

        # Evaluar nombre del doctor
        if medical_info.get("doctor_name"):
            entities_found += 1
            doctor_name = medical_info["doctor_name"]
            # Verificar formato de nombre profesional
            if len(doctor_name.split()) >= 2 and any(title in doctor_name.lower() for title in ["dr", "dra", "doctor", "doctora"]):
                score += 0.15
            else:
                score += 0.05
        total_entities += 1

        # Evaluar especialidad
        if medical_info.get("specialty"):
            entities_found += 1
            score += 0.1
        total_entities += 1

        # Evaluar procedimientos
        if medical_info.get("procedures") and len(medical_info["procedures"]) > 0:
            entities_found += 1
            score += 0.1
        total_entities += 1

        # Evaluar sesiones
        if medical_info.get("session_count"):
            entities_found += 1
            score += 0.1
        total_entities += 1

        # Bonus por cobertura de entidades
        coverage_bonus = (entities_found / total_entities) * 0.2
        score += coverage_bonus

        return min(1.0, score)

    def _calculate_document_structure_score(self, text: str) -> float:
        """Evalúa estructura del documento"""
        score = 0.0
        text_lower = text.lower()

        # Presencia de encabezados médicos comunes
        medical_headers = [
            "orden médica", "prescripción", "diagnóstico", "paciente",
            "doctor", "fecha", "tratamiento", "medicamento"
        ]

        headers_found = sum(1 for header in medical_headers if header in text_lower)
        if headers_found >= 3:
            score += 0.4
        elif headers_found >= 1:
            score += 0.2

        # Presencia de números (fechas, cantidades, etc.)
        import re
        numbers_found = len(re.findall(r'\d+', text))
        if numbers_found >= 5:
            score += 0.3
        elif numbers_found >= 2:
            score += 0.15

        # Estructura de párrafos
        lines = text.split('\n')
        structured_lines = sum(1 for line in lines if len(line.strip()) > 10)
        if structured_lines >= len(lines) * 0.6:
            score += 0.3

        return min(1.0, score)

    def _calculate_pattern_matching_score(self, text: str, medical_info: Dict[str, Any]) -> float:
        """Evalúa coincidencia con patrones médicos conocidos"""
        score = 0.0
        text_lower = text.lower()

        # Patrones de órdenes médicas
        medical_patterns = [
            r'orden\s+médica', r'prescripción\s+médica', r'fórmula\s+médica',
            r'sesiones?\s+de\s+(?:fisioterapia|terapia)', r'(\d+)\s*sesiones',
            r'paciente:?\s*[A-Za-z]', r'dr\.?\s*[A-Za-z]', r'cédula:?\s*\d+'
        ]

        import re
        patterns_matched = sum(1 for pattern in medical_patterns if re.search(pattern, text, re.IGNORECASE))
        if patterns_matched >= 4:
            score += 0.5
        elif patterns_matched >= 2:
            score += 0.3
        elif patterns_matched >= 1:
            score += 0.1

        # Verificar consistencia interna
        if medical_info.get("has_medical_order") and medical_info.get("doctor_name"):
            score += 0.3
        elif medical_info.get("has_medical_order") or medical_info.get("doctor_name"):
            score += 0.15

        return min(1.0, score)

    def _get_confidence_level(self, score: float) -> str:
        """Convierte puntuación numérica a nivel descriptivo"""
        if score >= self.high_confidence_threshold:
            return "high"
        elif score >= self.min_confidence_threshold:
            return "medium"
        else:
            return "low"

    def _generate_confidence_recommendations(self, overall_score: float, detailed_scores: Dict[str, float]) -> List[str]:
        """Genera recomendaciones basadas en la puntuación de confianza"""
        recommendations = []

        if overall_score < self.min_confidence_threshold:
            recommendations.append("La calidad del OCR es baja. Considere reintentar con una imagen más clara.")

        # Recomendaciones específicas por componente
        if detailed_scores["text_quality_score"] < 0.5:
            recommendations.append("El texto extraído tiene baja calidad. Verifique la claridad de la imagen original.")

        if detailed_scores["entity_recognition_score"] < 0.5:
            recommendations.append("Pocas entidades médicas reconocidas. Puede requerir verificación manual.")

        if detailed_scores["document_structure_score"] < 0.5:
            recommendations.append("Estructura del documento poco clara. Asegúrese de que el documento esté bien escaneado.")

        if overall_score >= self.high_confidence_threshold:
            recommendations.append("Información extraída con alta confianza. Proceda con automatización.")

        return recommendations

# Instancia global del scorer de confianza
confidence_scorer = ConfidenceScorer()

def _extract_medical_info_simple(text: str) -> Dict[str, Any]:
    """Extrae información médica básica para el cache con scoring de confianza"""
    info = {}
    text_lower = text.lower()

    # Detectar tipo de documento
    if any(word in text_lower for word in ["fisioterapia", "rehabilitación", "terapia física"]):
        info["document_type"] = "fisioterapia"
    elif any(word in text_lower for word in ["orden médica", "prescripción"]):
        info["document_type"] = "orden_medica"
    elif any(word in text_lower for word in ["laboratorio", "resultados", "análisis"]):
        info["document_type"] = "laboratorio"

    # Buscar sesiones
    import re
    session_match = re.search(r"(\d+)\s*sesion", text_lower)
    if session_match:
        info["sessions"] = int(session_match.group(1))

    # Buscar nombres (capitalizado)
    name_matches = re.findall(r"[A-Z][a-záéíóúü]+(?:\s+[A-Z][a-záéíóúü]+)*", text)
    if name_matches:
        info["potential_names"] = name_matches[:3]  # Primeros 3 matches

    info["text_length"] = len(text)

    # Calcular confianza usando el nuevo sistema
    confidence_analysis = confidence_scorer.calculate_overall_confidence(text, info)
    info["confidence_analysis"] = confidence_analysis
    info["confidence"] = confidence_analysis["confidence_level"]

    return info

class MultiImageOCR:
    """Clase principal para OCR de múltiples imágenes"""
    
    def __init__(self):
        self.max_images = MAX_IMAGES_PER_MESSAGE
        self.max_text_length = MAX_TEXT_LENGTH
    
    async def extract_text_from_multiple_images(self, media_data: List[Dict[str, str]]) -> Dict[str, Any]:
        """Extrae texto de múltiples imágenes"""
        return await extract_text_from_multiple_images(media_data)
    
    def _detect_document_type(self, text: str) -> str:
        """Detecta el tipo de documento basado en el texto"""
        return _detect_document_type(text)

    def _extract_medical_info(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Extrae información médica del texto"""
        return _extract_medical_info(text)

    def _assess_processing_quality(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Evalúa la calidad general del procesamiento OCR"""
        quality = {
            "overall_quality": "unknown",
            "quality_score": 0.0,
            "issues": [],
            "recommendations": []
        }

        # Evaluar tasa de éxito
        total_images = results.get("total_images", 0)
        processed_images = results.get("processed_images", 0)
        success_rate = processed_images / total_images if total_images > 0 else 0

        if success_rate >= 0.8:
            quality["overall_quality"] = "excellent"
            quality["quality_score"] = 0.9
        elif success_rate >= 0.6:
            quality["overall_quality"] = "good"
            quality["quality_score"] = 0.7
        elif success_rate >= 0.3:
            quality["overall_quality"] = "fair"
            quality["quality_score"] = 0.5
        else:
            quality["overall_quality"] = "poor"
            quality["quality_score"] = 0.2
            quality["issues"].append("low_success_rate")
            quality["recommendations"].append("Considerar mejorar calidad de imágenes enviadas")

        # Evaluar longitud del texto
        text_length = len(results.get("combined_text", ""))
        if text_length < 50:
            quality["quality_score"] -= 0.2
            quality["issues"].append("insufficient_text")
            quality["recommendations"].append("Verificar que las imágenes contengan texto legible")

        # Evaluar confianza del OCR
        confidence_analysis = results.get("confidence_analysis", {})
        confidence_score = confidence_analysis.get("overall_confidence", 0.0)

        if confidence_score < 0.3:
            quality["quality_score"] -= 0.3
            quality["issues"].append("low_confidence")
            quality["recommendations"].append("Imagen de baja calidad - sugerir reescaneo")

        # Evaluar información médica extraída
        medical_info = results.get("medical_info", {})
        entities_found = sum(1 for key in ["patient_name", "doctor_name", "document_id"]
                           if medical_info.get(key))

        if entities_found == 0:
            quality["issues"].append("no_entities_found")
            quality["recommendations"].append("No se encontraron entidades médicas - posible documento no médico")
        elif entities_found < 2:
            quality["issues"].append("few_entities_found")
            quality["recommendations"].append("Información limitada extraída - considerar verificación manual")

        # Ajustar puntuación final
        quality["quality_score"] = max(0.0, min(1.0, quality["quality_score"]))

        return quality

async def extract_text_from_multiple_images(media_data: List[Dict[str, str]], telefono: str = None) -> Dict[str, Any]:
    """
    Extrae texto de múltiples imágenes con cache inteligente
    
    Args:
        media_data: Lista de diccionarios con keys: 'url', 'content_type', 'index'
        telefono: Teléfono del usuario para validación inteligente
    
    Returns:
        Diccionario con información extraída y combinada
    """
    if not ocr_enabled() or not _OCR_AVAILABLE:
        return {"success": False, "error": "OCR no disponible", "texts": []}
    
    results = {
        "success": True,
        "total_images": len(media_data),
        "processed_images": 0,
        "failed_images": 0,
        "texts": [],
        "combined_text": "",
        "medical_info": {},
        "document_types": [],
        "cache_hits": 0,
        "processing_summary": {}
    }
    
    if not media_data:
        results["success"] = False
        results["error"] = "No hay imágenes para procesar"
        return results
    
    # Limitar número de imágenes
    media_data = media_data[:MAX_IMAGES_PER_MESSAGE]
    
    # Procesar cada imagen
    tasks = []
    for i, media in enumerate(media_data):
        url = media.get("url", "")
        if url:
            tasks.append(extract_text_from_single_image(url, telefono))
    
    # Ejecutar todas las extracciones en paralelo
    extracted_texts = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_texts = []
    successful_extractions = 0
    
    for i, result in enumerate(extracted_texts):
        if isinstance(result, Exception):
            logger.warning(f"Error procesando imagen {i}: {result}")
            results["failed_images"] += 1
        elif result:
            all_texts.append(result)
            results["texts"].append({
                "index": i,
                "text": result,
                "length": len(result)
            })
            successful_extractions += 1
        else:
            results["failed_images"] += 1
    
    results["processed_images"] = successful_extractions
    
    if not all_texts:
        results["success"] = False
        results["error"] = "No se pudo extraer texto de ninguna imagen"
        return results
    
    # Combinar todos los textos
    combined_text = "\n\n--- DOCUMENTO {} ---\n\n".join(all_texts)
    results["combined_text"] = combined_text[:MAX_TEXT_LENGTH]
    
    # Detectar tipo de documento principal con clasificador avanzado
    doc_classification = document_classifier.classify_document(combined_text)
    main_doc_type = doc_classification["document_type"]
    results["document_types"] = [main_doc_type]
    results["document_classification"] = doc_classification
    
    # Extraer información médica con análisis de confianza
    medical_info = _extract_medical_info(combined_text)

    # Agregar análisis de confianza al resultado
    confidence_analysis = confidence_scorer.calculate_overall_confidence(combined_text, medical_info)
    medical_info["confidence_analysis"] = confidence_analysis

    # Validación inteligente si hay cache disponible
    if _CACHE_AVAILABLE and telefono:
        medical_info = smart_validator.validate_medical_info(medical_info, telefono)

    results["medical_info"] = medical_info
    results["confidence_analysis"] = confidence_analysis
    
    # Resumen de procesamiento mejorado
    results["processing_summary"] = {
        "total_images_received": len(media_data),
        "total_images_processed": successful_extractions,
        "total_text_length": len(combined_text),
        "main_document_type": main_doc_type,
        "document_confidence": doc_classification.get("confidence", 0.0),
        "medical_info_extracted": bool(medical_info),
        "confidence_level": confidence_analysis.get("confidence_level", "unknown"),
        "overall_confidence_score": confidence_analysis.get("overall_confidence", 0.0),
        "cache_enhanced": _CACHE_AVAILABLE and telefono is not None,
        "fallback_used": any("failed" in str(result) for result in extracted_texts if isinstance(result, Exception)),
        "processing_quality": _assess_processing_quality(results)
    }
    
    logger.info(f"OCR múltiple: {successful_extractions}/{len(media_data)} imágenes procesadas")
    
    return results
    
    # Procesar cada imagen
    for item in image_media:
        url = item.get('url')
        index = item.get('index', 0)
        
        if not url:
            continue
            
        # Extraer texto de la imagen
        text = await extract_text_from_single_image(url)
        
        if text:
            image_result = {
                "index": index,
                "url": url,
                "text": text,
                "length": len(text)
            }
            results["texts"].append(image_result)
            results["processed_images"] += 1
    
    # Combinar todos los textos
    if results["texts"]:
        combined_parts = []
        for i, text_data in enumerate(results["texts"]):
            page_number = text_data["index"] + 1
            combined_parts.append(f"--- PÁGINA/IMAGEN {page_number} ---")
            combined_parts.append(text_data["text"])
            combined_parts.append("")  # Línea en blanco
        
        results["combined_text"] = "\n".join(combined_parts)
        
        # Truncar si es muy largo
        if len(results["combined_text"]) > MAX_TEXT_LENGTH:
            results["combined_text"] = results["combined_text"][:MAX_TEXT_LENGTH] + "\n[...TEXTO TRUNCADO...]"
        
        # Analizar tipo de documento
        results["detected_document_type"] = _detect_document_type(results["combined_text"])
        
        # Extraer información médica
        results["medical_info"] = _extract_medical_info(results["combined_text"])
    
    return results

class AdvancedDocumentClassifier:
    """Clasificador avanzado de tipos de documentos médicos"""

    def __init__(self):
        self.document_types = {
            "orden_medica": {
                "primary_patterns": [
                    "orden médica", "orden medica", "órden médica", "fórmula médica",
                    "prescripción médica", "prescripcion medica", "formula medica",
                    "receta médica", "receta medica"
                ],
                "secondary_patterns": [
                    "medicamento", "tratamiento", "sesiones", "terapia",
                    "fisioterapia", "rehabilitación", "prescribir"
                ],
                "confidence_boost": 0.9
            },
            "laboratorio": {
                "primary_patterns": [
                    "laboratorio", "resultados de laboratorio", "examen de sangre",
                    "hemograma", "química sanguínea", "perfil lipídico", "glucosa",
                    "colesterol", "triglicéridos", "hdl", "ldl", "creatinina"
                ],
                "secondary_patterns": [
                    "analisis", "análisis", "prueba", "examen", "sangre", "orina",
                    "heces", "cultivo", "biopsia", "marcadores tumorales"
                ],
                "confidence_boost": 0.85
            },
            "radiografia": {
                "primary_patterns": [
                    "radiografía", "radiografia", "rx ", "rayos x", "rayos-x",
                    "tomografía", "tomografia", "resonancia magnética", "rmn",
                    "ecografía", "ecografia", "ultrasonido", "mamografía"
                ],
                "secondary_patterns": [
                    "imagen", "imagenología", "diagnóstico por imagen", "placa",
                    "tac", "scanner", "mri", "ct scan"
                ],
                "confidence_boost": 0.8
            },
            "historia_clinica": {
                "primary_patterns": [
                    "historia clínica", "historia clinica", "evolución médica",
                    "evolución medica", "notas médicas", "notas medicas",
                    "consulta externa", "urgencias", "hospitalización"
                ],
                "secondary_patterns": [
                    "diagnóstico", "síntomas", "tratamiento", "evolución",
                    "antecedentes", "alergias", "medicamentos actuales"
                ],
                "confidence_boost": 0.75
            },
            "referencia": {
                "primary_patterns": [
                    "remisión", "remision", "referencia médica", "interconsulta",
                    "valoración por", "valoracion por", "derivación", "derivar",
                    "consulta con especialista", "contra-referencia"
                ],
                "secondary_patterns": [
                    "especialista", "valoración", "evaluación", "estudio",
                    "seguimiento", "control", "vigilancia"
                ],
                "confidence_boost": 0.8
            },
            "epicrisis": {
                "primary_patterns": [
                    "epicrisis", "alta médica", "alta medica", "egreso",
                    "resumen de egreso", "informe de alta", "carta de alta"
                ],
                "secondary_patterns": [
                    "ingreso", "estancia hospitalaria", "procedimientos realizados",
                    "tratamiento recibido", "recomendaciones", "seguimiento"
                ],
                "confidence_boost": 0.85
            },
            "consentimiento": {
                "primary_patterns": [
                    "consentimiento informado", "autorización", "consentimiento",
                    "riesgos", "beneficios", "alternativas", "firma del paciente"
                ],
                "secondary_patterns": [
                    "procedimiento", "intervención", "cirugía", "tratamiento",
                    "riesgos potenciales", "complicaciones"
                ],
                "confidence_boost": 0.9
            },
            "certificado_medico": {
                "primary_patterns": [
                    "certificado médico", "certificado medica", "incapacidad",
                    "reposo", "licencia médica", "constancia médica",
                    "certificación médica", "justificación médica"
                ],
                "secondary_patterns": [
                    "días de reposo", "diagnóstico", "fecha de emisión",
                    "válido hasta", "para fines", "certifico que"
                ],
                "confidence_boost": 0.9
            },
            "examen_fisico": {
                "primary_patterns": [
                    "examen físico", "exploración física", "signos vitales",
                    "presión arterial", "frecuencia cardíaca", "temperatura",
                    "peso", "talla", "imc", "exploración por sistemas"
                ],
                "secondary_patterns": [
                    "ta", "fc", "fr", "temp", "kg", "cm", "normal", "anormal",
                    "cabeza y cuello", "tórax", "abdomen", "extremidades"
                ],
                "confidence_boost": 0.75
            }
        }

    def classify_document(self, text: str) -> Dict[str, Any]:
        """Clasifica el documento con análisis detallado"""
        text_lower = text.lower()
        scores = {}

        # Calcular puntuación para cada tipo de documento
        for doc_type, config in self.document_types.items():
            primary_score = sum(1 for pattern in config["primary_patterns"]
                              if pattern in text_lower) * 2  # Peso doble para patrones primarios
            secondary_score = sum(1 for pattern in config["secondary_patterns"]
                                if pattern in text_lower) * 1  # Peso normal para secundarios

            total_score = primary_score + secondary_score
            confidence_boost = config["confidence_boost"]

            # Aplicar boost de confianza y normalizar
            final_score = min(1.0, (total_score / 10.0) * confidence_boost)
            scores[doc_type] = final_score

        # Determinar tipo principal
        if scores:
            main_type = max(scores.keys(), key=lambda x: scores[x])
            main_score = scores[main_type]

            # Solo considerar válido si tiene puntuación mínima
            if main_score >= 0.1:
                return {
                    "document_type": main_type,
                    "confidence": main_score,
                    "all_scores": scores,
                    "secondary_types": sorted(
                        [(k, v) for k, v in scores.items() if k != main_type and v >= 0.05],
                        key=lambda x: x[1], reverse=True
                    )[:3]  # Top 3 tipos secundarios
                }

        # Fallback a clasificación genérica
        return self._fallback_classification(text)

    def _fallback_classification(self, text: str) -> Dict[str, Any]:
        """Clasificación fallback cuando no se detecta tipo específico"""
        text_lower = text.lower()

        # Verificar si es documento médico genérico
        medical_indicators = [
            "médico", "medico", "doctor", "dr.", "dra.", "paciente",
            "diagnóstico", "tratamiento", "medicamento", "consulta",
            "especialista", "hospital", "clínica", "clinica"
        ]

        medical_score = sum(1 for indicator in medical_indicators if indicator in text_lower)

        if medical_score >= 2:
            return {
                "document_type": "documento_medico",
                "confidence": min(0.6, medical_score / 10.0),
                "all_scores": {},
                "secondary_types": []
            }

        return {
            "document_type": "unknown",
            "confidence": 0.0,
            "all_scores": {},
            "secondary_types": []
        }

# Instancia global del clasificador avanzado
document_classifier = AdvancedDocumentClassifier()

def _assess_processing_quality(results: Dict[str, Any]) -> Dict[str, Any]:
    """Evalúa la calidad general del procesamiento OCR"""
    quality = {
        "overall_quality": "unknown",
        "quality_score": 0.0,
        "issues": [],
        "recommendations": []
    }

    # Evaluar tasa de éxito
    total_images = results.get("total_images", 0)
    processed_images = results.get("processed_images", 0)
    success_rate = processed_images / total_images if total_images > 0 else 0

    if success_rate >= 0.8:
        quality["overall_quality"] = "excellent"
        quality["quality_score"] = 0.9
    elif success_rate >= 0.6:
        quality["overall_quality"] = "good"
        quality["quality_score"] = 0.7
    elif success_rate >= 0.3:
        quality["overall_quality"] = "fair"
        quality["quality_score"] = 0.5
    else:
        quality["overall_quality"] = "poor"
        quality["quality_score"] = 0.2
        quality["issues"].append("low_success_rate")
        quality["recommendations"].append("Considerar mejorar calidad de imágenes enviadas")

    # Evaluar longitud del texto
    text_length = len(results.get("combined_text", ""))
    if text_length < 50:
        quality["quality_score"] -= 0.2
        quality["issues"].append("insufficient_text")
        quality["recommendations"].append("Verificar que las imágenes contengan texto legible")

    # Evaluar confianza del OCR
    confidence_analysis = results.get("confidence_analysis", {})
    confidence_score = confidence_analysis.get("overall_confidence", 0.0)

    if confidence_score < 0.3:
        quality["quality_score"] -= 0.3
        quality["issues"].append("low_confidence")
        quality["recommendations"].append("Imagen de baja calidad - sugerir reescaneo")

    # Evaluar información médica extraída
    medical_info = results.get("medical_info", {})
    entities_found = sum(1 for key in ["patient_name", "doctor_name", "document_id"]
                        if medical_info.get(key))

    if entities_found == 0:
        quality["issues"].append("no_entities_found")
        quality["recommendations"].append("No se encontraron entidades médicas - posible documento no médico")
    elif entities_found < 2:
        quality["issues"].append("few_entities_found")
        quality["recommendations"].append("Información limitada extraída - considerar verificación manual")

    # Ajustar puntuación final
    quality["quality_score"] = max(0.0, min(1.0, quality["quality_score"]))

    return quality

def _detect_document_type(text: str) -> str:
    """Detecta el tipo de documento usando clasificador avanzado"""
    classification = document_classifier.classify_document(text)
    return classification["document_type"]

def extract_medical_info_from_text(text: str) -> Dict[str, Any]:
    """
    Extrae información médica del texto OCR de órdenes médicas.

    Esta función es un wrapper público que combina la detección de tipo de documento
    con la extracción de información médica específica.

    Args:
        text: Texto extraído por OCR de imágenes de órdenes médicas

    Returns:
        Diccionario con información médica extraída incluyendo:
        - has_medical_order: bool - Si se detectó una orden médica
        - document_type: str - Tipo de documento detectado
        - doctor_name: str - Nombre del doctor prescriptor
        - diagnosis: str - Diagnóstico encontrado
        - patient_name: str - Nombre del paciente
        - document_id: str - Número de documento del paciente
        - specialty: str - Especialidad médica
        - session_count: int - Número de sesiones prescritas
        - procedures: list - Procedimientos detectados
        - medications: list - Medicamentos detectados
    """
    try:
        if not text or not isinstance(text, str):
            return {
                "has_medical_order": False,
                "document_type": "unknown",
                "doctor_name": None,
                "diagnosis": None,
                "patient_name": None,
                "document_id": None,
                "specialty": None,
                "session_count": None,
                "procedures": [],
                "medications": []
            }

        # Detectar tipo de documento
        document_type = _detect_document_type(text)

        # Extraer información médica detallada
        medical_info = _extract_medical_info(text)

        # Combinar resultados
        result = {
            "has_medical_order": medical_info.get("has_medical_order", False),
            "document_type": document_type,
            "doctor_name": medical_info.get("doctor_name"),
            "diagnosis": medical_info.get("diagnosis", [])[0] if medical_info.get("diagnosis") else None,
            "patient_name": medical_info.get("patient_name"),
            "document_id": medical_info.get("document_id"),
            "specialty": medical_info.get("specialty"),
            "session_count": medical_info.get("session_count"),
            "procedures": medical_info.get("procedures", []),
            "medications": medical_info.get("medications", [])
        }

        return result

    except Exception as e:
        logger.warning(f"Error extrayendo información médica del texto: {e}")
        return {
            "has_medical_order": False,
            "document_type": "unknown",
            "doctor_name": None,
            "diagnosis": None,
            "patient_name": None,
            "document_id": None,
            "specialty": None,
            "session_count": None,
            "procedures": [],
            "medications": []
        }


class EnhancedEntityRecognizer:
    """Reconocedor avanzado de entidades médicas mejorado"""

    def __init__(self):
        self.patient_name_patterns = [
            # Patrones directos con etiquetas
            r'(?:paciente|nombre|nom)[\s:]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)',
            r'(?:paciente|nombre|nom)[\s:]*[^\w]*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)',

            # Patrones en contexto médico
            r'(?:el|la)\s+(?:paciente|señor|señora|sr|sra)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)',

            # Nombres en mayúsculas consecutivas (común en documentos)
            r'\b([A-ZÁÉÍÓÚÑ]{2,}[a-záéíóúñ]*\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',

            # Nombres con apellidos comunes colombianos
            r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+(?:de\s+)?(?:la\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)'
        ]

        self.doctor_name_patterns = [
            # Patrones con títulos médicos
            r'(?:dr|dra|doctor|doctora|md|médico|médica)[\s\.]*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)',
            r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)[\s,]+(?:dr|dra|doctor|doctora|md)',

            # Especialistas específicos
            r'(?:especialista|especialidad)[\s:]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)',

            # Firmas al final del documento
            r'(?:at[ei]entamente|firma|firmado\s+por)[\s:]*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)'
        ]

        self.document_id_patterns = [
            # Cédulas colombianas
            r'(?:cédula|cedula|cc|documento|id|identificación)[\s:#]*(\d{6,15})',
            r'(\d{6,15})(?:\s*(?:cédula|cedula|cc|documento|id))',

            # Números de historia clínica
            r'(?:historia|h\.?c\.?|hc)[\s:#]*(\d{4,15})',
            r'(?:número|num|no\.?)[\s:#]*(\d{4,15})'
        ]

    def extract_patient_name(self, text: str) -> Optional[str]:
        """Extrae nombre del paciente con mayor precisión"""
        import re

        candidates = []

        for pattern in self.patient_name_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                name = match.group(1).strip()
                # Validar formato de nombre
                if self._validate_name_format(name):
                    candidates.append(name)

        if not candidates:
            return None

        # Seleccionar el mejor candidato
        return self._select_best_name_candidate(candidates)

    def extract_doctor_name(self, text: str) -> Optional[str]:
        """Extrae nombre del doctor con mayor precisión"""
        import re

        candidates = []

        for pattern in self.doctor_name_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                name = match.group(1).strip()
                # Validar formato de nombre profesional
                if self._validate_doctor_name_format(name):
                    candidates.append(name)

        if not candidates:
            return None

        return self._select_best_doctor_candidate(candidates)

    def extract_document_id(self, text: str) -> Optional[str]:
        """Extrae número de documento con validación mejorada"""
        import re

        candidates = []

        for pattern in self.document_id_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                doc_id = match.group(1).strip()
                # Validar formato de documento colombiano
                if self._validate_document_id_format(doc_id):
                    candidates.append(doc_id)

        if not candidates:
            return None

        # Seleccionar el documento más probable
        return self._select_best_document_candidate(candidates)

    def _validate_name_format(self, name: str) -> bool:
        """Valida formato básico de nombre"""
        if not name or len(name) < 3 or len(name) > 80:
            return False

        parts = name.split()
        if len(parts) < 2:
            return False

        # Al menos una parte debe empezar con mayúscula
        has_capital = any(part[0].isupper() for part in parts if part)
        # No debe contener solo números
        has_no_digits = not any(char.isdigit() for char in name)
        # No debe contener caracteres especiales excesivos
        special_chars = sum(1 for char in name if not char.isalnum() and not char.isspace())
        reasonable_special = special_chars <= len(parts)  # Máximo 1 caracter especial por parte

        return has_capital and has_no_digits and reasonable_special

    def _validate_doctor_name_format(self, name: str) -> bool:
        """Valida formato de nombre de doctor"""
        if not name or len(name) < 3 or len(name) > 80:
            return False

        parts = name.split()
        if len(parts) < 2:
            return False

        # Debe tener al menos una mayúscula
        has_capital = any(part[0].isupper() for part in parts if part)
        # Puede contener títulos médicos
        medical_titles = ['dr', 'dra', 'doctor', 'doctora', 'md', 'médico', 'médica']
        has_title = any(title.lower() in name.lower() for title in medical_titles)

        return has_capital and (has_title or len(parts) >= 2)

    def _validate_document_id_format(self, doc_id: str) -> bool:
        """Valida formato de documento de identidad colombiano"""
        if not doc_id or not doc_id.isdigit():
            return False

        length = len(doc_id)
        # Cédulas colombianas: 6-15 dígitos
        # Historias clínicas: 4-15 dígitos
        return 4 <= length <= 15

    def _select_best_name_candidate(self, candidates: List[str]) -> str:
        """Selecciona el mejor candidato de nombre"""
        if len(candidates) == 1:
            return candidates[0]

        # Preferir nombres con más partes (más completos)
        sorted_candidates = sorted(candidates, key=lambda x: len(x.split()), reverse=True)
        return sorted_candidates[0]

    def _select_best_doctor_candidate(self, candidates: List[str]) -> str:
        """Selecciona el mejor candidato de doctor"""
        if len(candidates) == 1:
            return candidates[0]

        # Preferir nombres con títulos médicos
        medical_titles = ['dr', 'dra', 'doctor', 'doctora']
        for candidate in candidates:
            if any(title.lower() in candidate.lower() for title in medical_titles):
                return candidate

        # Si no hay títulos, seleccionar el más largo
        return max(candidates, key=len)

    def _select_best_document_candidate(self, candidates: List[str]) -> str:
        """Selecciona el mejor candidato de documento"""
        if len(candidates) == 1:
            return candidates[0]

        # Preferir documentos con longitud típica de cédula (8-12 dígitos)
        preferred_length = [doc for doc in candidates if 8 <= len(doc) <= 12]
        if preferred_length:
            return preferred_length[0]

        # Si no hay preferidos, seleccionar el más largo
        return max(candidates, key=len)

# Instancia global del reconocedor mejorado
entity_recognizer = EnhancedEntityRecognizer()

def _extract_medical_info(text: str) -> Dict[str, Any]:
    """Extrae información médica específica del texto usando reconocimiento mejorado"""
    info = {
        "patient_name": None,
        "document_id": None,
        "doctor_name": None,
        "procedures": [],
        "medications": [],
        "diagnosis": [],
        "has_medical_order": False,
        "session_count": None,
        "specialty": None
    }

    lines = text.split('\n')
    text_lower = text.lower()

    # Detectar orden médica
    medical_order_patterns = [
        "orden médica", "orden medica", "prescripción", "prescripcion",
        "fórmula médica", "formula medica", "medicamento", "tratamiento"
    ]
    info["has_medical_order"] = any(pattern in text_lower for pattern in medical_order_patterns)

    # Usar reconocedor mejorado para entidades críticas
    info["patient_name"] = entity_recognizer.extract_patient_name(text)
    info["doctor_name"] = entity_recognizer.extract_doctor_name(text)
    info["document_id"] = entity_recognizer.extract_document_id(text)

    # Buscar procedimientos/terapias (mantener lógica existente pero mejorada)
    therapy_patterns = [
        r'fisioterapia\s*(\d+)?\s*sesiones?',
        r'terapia\s+(?:física|fisica|respiratoria|ocupacional|neurológica)',
        r'sesiones?\s*(?:de\s*)?(?:fisioterapia|terapia|rehabilitación)\s*(\d+)?',
        r'(\d+)\s*sesiones?\s*(?:de\s*)?(?:fisioterapia|terapia|rehabilitación)',
        r'(?:tratamiento|terapia)\s+(?:de\s*)?(?:fisioterapia|neurología|cardiología)'
    ]

    import re
    for pattern in therapy_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            procedure = match.group(0)
            if procedure not in info["procedures"]:  # Evitar duplicados
                info["procedures"].append(procedure)

            # Extraer número de sesiones
            numbers = re.findall(r'\d+', procedure)
            if numbers and not info["session_count"]:
                info["session_count"] = int(numbers[0])

    # Detectar especialidad con más patrones
    specialties = {
        "fisioterapia": ["fisioterapia", "fisio", "terapia física", "terapia fisica", "rehabilitación"],
        "neurologia": ["neurología", "neurologia", "neurólogo", "neurologo", "neurológica", "neurologica"],
        "cardiologia": ["cardiología", "cardiologia", "cardiólogo", "cardiologo", "cardiológica", "cardiologica"],
        "dermatologia": ["dermatología", "dermatologia", "dermatólogo", "dermatologo"],
        "ginecologia": ["ginecología", "ginecologia", "ginecólogo", "ginecologo"],
        "ortopedia": ["ortopedia", "ortopédico", "ortopedico", "traumatología"],
        "pediatria": ["pediatría", "pediatria", "pediatra"],
        "medicina_interna": ["medicina interna", "internista"],
        "psiquiatria": ["psiquiatría", "psiquiatria", "psiquiatra"]
    }

    for specialty, keywords in specialties.items():
        if any(keyword in text_lower for keyword in keywords):
            info["specialty"] = specialty
            break

    # Buscar medicamentos (mejorado)
    medication_patterns = [
        r'(?:medicamento|medicina|droga|fármaco)[\s:]+([A-Za-záéíóúñ\s]+)',
        r'(?:recetar|recetado|administrar)[\s:]+([A-Za-záéíóúñ\s]+(?:\d+\s*mg|\d+\s*ml|\d+\s*ui|\d+\s*comprimidos?))',
        r'\b([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)*)\s+(\d+(?:\.\d+)?)\s*(?:mg|ml|ui|comprimidos?|tabletas?)\b'
    ]

    for pattern in medication_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            medication = match.group(1).strip()
            if len(medication) > 2 and medication not in info["medications"]:
                info["medications"].append(medication)

    return info

# Función de compatibilidad con el sistema existente
async def extract_text_from_image(url: str) -> Optional[str]:
    """Función de compatibilidad - extrae texto de una imagen (versión original)"""
    return await extract_text_from_single_image(url)

def process_whatsapp_media(form_data: dict) -> List[Dict[str, str]]:
    """
    Procesa datos de formulario de WhatsApp para extraer información de múltiples medios
    
    Args:
        form_data: Datos del formulario de Twilio WhatsApp
    
    Returns:
        Lista de diccionarios con información de cada medio
    """
    num_media = int(form_data.get("NumMedia", 0) or 0)
    print(f"[OCR] 📊 NumMedia detectado: {num_media}")
    
    media_list = []
    
    for i in range(num_media):
        media_url = form_data.get(f"MediaUrl{i}")
        media_type = form_data.get(f"MediaContentType{i}")
        print(f"[OCR] 📷 Media {i}: URL={media_url}, Type={media_type}")
        
        if media_url:
            media_list.append({
                "index": i,
                "url": media_url,
                "content_type": media_type or "unknown"
            })
    
    print(f"[OCR] 📋 Media list final: {len(media_list)} elementos")
    return media_list

async def process_medical_order_images(form_data: dict) -> Dict[str, Any]:
    """
    Función principal para procesar imágenes de órdenes médicas desde WhatsApp
    
    Args:
        form_data: Datos del formulario de Twilio WhatsApp
    
    Returns:
        Información extraída de todas las imágenes
    """
    print(f"[OCR] 📋 Iniciando process_medical_order_images")
    print(f"[OCR] 📋 Form data keys: {list(form_data.keys())}")
    
    # Extraer información de medios
    media_list = process_whatsapp_media(form_data)
    print(f"[OCR] 📋 Media list: {media_list}")
    
    if not media_list:
        print(f"[OCR] ❌ No hay archivos multimedia")
        return {
            "success": False,
            "error": "No hay archivos multimedia en el mensaje",
            "total_images": 0,
            "processed_images": 0,
            "has_medical_order": False
        }
    
    print(f"[OCR] 🔍 Procesando {len(media_list)} imágenes...")
    # Procesar imágenes
    results = await extract_text_from_multiple_images(media_list)
    print(f"[OCR] ✅ Resultados: {results}")
    
    # Asegurar que todas las claves esperadas estén presentes
    if "total_images" not in results:
        results["total_images"] = len(media_list)
    if "processed_images" not in results:
        results["processed_images"] = len([r for r in results.get("individual_results", []) if r.get("success")])
    
    # Agregar flag de orden médica para compatibilidad
    if results.get("medical_info"):
        results["has_medical_order"] = results["medical_info"].get("has_medical_order", False)
    else:
        results["has_medical_order"] = False
    
    print(f"[OCR] 🎯 Resultado final: success={results.get('success')}, images={results.get('processed_images')}/{results.get('total_images')}")
    return results