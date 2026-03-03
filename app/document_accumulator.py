"""
🔗 SISTEMA DE ACUMULACIÓN DE DOCUMENTOS MÚLTIPLES MENSAJES
Maneja inteligentemente documentos enviados en múltiples mensajes separados
"""
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
import ast

logger = logging.getLogger(__name__)

class DocumentAccumulator:
    """Acumula y combina información médica de múltiples mensajes"""
    
    def __init__(self):
        self.session_timeout = 300  # 5 minutos para completar envío de documentos
        
    def should_accumulate_documents(self, historial: List[tuple], recent_threshold_minutes: int = 5) -> bool:
        """
        Determina si debe seguir acumulando documentos o procesar lo ya recibido
        """
        if not historial:
            return True
            
        # Buscar últimos mensajes con OCR
        recent_cutoff = datetime.now() - timedelta(minutes=recent_threshold_minutes)
        ocr_messages = [entry for entry in historial if entry[0] in ['usuario_media_ocr', 'medical_info_extracted']]
        
        # Si hay mensajes OCR recientes, continúa acumulando
        return len(ocr_messages) > 0
    
    def extract_accumulated_medical_info(self, historial: List[tuple]) -> Dict[str, Any]:
        """
        Extrae y combina toda la información médica acumulada del historial
        """
        accumulated_info = {
            "all_ocr_texts": [],
            "all_medical_info": [],
            "combined_medical_data": {
                "patient_name": None,
                "document_id": None,
                "doctor_name": None,
                "procedures": [],
                "medications": [],
                "diagnosis": [],
                "has_medical_order": False,
                "session_count": None,
                "specialty": None,
                "document_types": set(),
                "total_pages": 0
            },
            "processing_summary": {
                "total_messages_with_ocr": 0,
                "total_images_processed": 0,
                "document_types_detected": set(),
                "confidence_score": 0.0
            }
        }
        
        # Extraer todos los textos OCR
        for role, content in historial:
            if role == "usuario_media_ocr":
                accumulated_info["all_ocr_texts"].append(content)
                accumulated_info["combined_medical_data"]["total_pages"] += 1
                
        # Extraer toda la información médica estructurada
        for role, content in historial:
            if role == "medical_info_extracted":
                try:
                    medical_info = ast.literal_eval(content)
                    accumulated_info["all_medical_info"].append(medical_info)
                    self._merge_medical_info(accumulated_info["combined_medical_data"], medical_info)
                except Exception as e:
                    logger.warning(f"Error parseando medical_info: {e}")
        
        # Extraer información de procesamiento
        for role, content in historial:
            if role == "ocr_processing_info":
                try:
                    proc_info = ast.literal_eval(content)
                    accumulated_info["processing_summary"]["total_messages_with_ocr"] += 1
                    accumulated_info["processing_summary"]["total_images_processed"] += proc_info.get("processed_images", 0)
                    doc_type = proc_info.get("document_type", "unknown")
                    if doc_type != "unknown":
                        accumulated_info["processing_summary"]["document_types_detected"].add(doc_type)
                except Exception as e:
                    logger.warning(f"Error parseando processing_info: {e}")
        
        # Calcular puntuación de confianza
        accumulated_info["processing_summary"]["confidence_score"] = self._calculate_confidence_score(accumulated_info)
        
        # Convertir sets a listas para JSON serialización
        accumulated_info["processing_summary"]["document_types_detected"] = list(accumulated_info["processing_summary"]["document_types_detected"])
        accumulated_info["combined_medical_data"]["document_types"] = list(accumulated_info["combined_medical_data"]["document_types"])
        
        return accumulated_info
    
    def _merge_medical_info(self, combined_data: Dict[str, Any], new_info: Dict[str, Any]):
        """Combina nueva información médica con la acumulada"""
        
        # Tomar el primer nombre de paciente válido encontrado
        if not combined_data["patient_name"] and new_info.get("patient_name"):
            combined_data["patient_name"] = new_info["patient_name"]
            
        # Tomar el primer documento válido encontrado
        if not combined_data["document_id"] and new_info.get("document_id"):
            combined_data["document_id"] = new_info["document_id"]
            
        # Tomar el primer doctor válido encontrado
        if not combined_data["doctor_name"] and new_info.get("doctor_name"):
            combined_data["doctor_name"] = new_info["doctor_name"]
        
        # Acumular procedimientos únicos
        if new_info.get("procedures"):
            for proc in new_info["procedures"]:
                if proc not in combined_data["procedures"]:
                    combined_data["procedures"].append(proc)
        
        # Acumular medicamentos únicos
        if new_info.get("medications"):
            for med in new_info["medications"]:
                if med not in combined_data["medications"]:
                    combined_data["medications"].append(med)
        
        # Acumular diagnósticos únicos
        if new_info.get("diagnosis"):
            for diag in new_info["diagnosis"]:
                if diag not in combined_data["diagnosis"]:
                    combined_data["diagnosis"].append(diag)
        
        # Marcar orden médica si se detecta en cualquier documento
        if new_info.get("has_medical_order"):
            combined_data["has_medical_order"] = True
        
        # Tomar el mayor número de sesiones encontrado
        if new_info.get("session_count"):
            if not combined_data["session_count"] or new_info["session_count"] > combined_data["session_count"]:
                combined_data["session_count"] = new_info["session_count"]
        
        # Tomar la primera especialidad válida encontrada
        if not combined_data["specialty"] and new_info.get("specialty"):
            combined_data["specialty"] = new_info["specialty"]
    
    def _calculate_confidence_score(self, accumulated_info: Dict[str, Any]) -> float:
        """Calcula una puntuación de confianza basada en la información extraída"""
        score = 0.0
        medical_data = accumulated_info["combined_medical_data"]
        
        # Puntos por datos básicos del paciente
        if medical_data.get("patient_name"):
            score += 0.2
        if medical_data.get("document_id"):
            score += 0.2
        if medical_data.get("doctor_name"):
            score += 0.2
        
        # Puntos por información médica
        if medical_data.get("has_medical_order"):
            score += 0.2
        if medical_data.get("procedures"):
            score += 0.1
        if medical_data.get("session_count"):
            score += 0.1
        
        return min(score, 1.0)
    
    def generate_accumulated_summary(self, accumulated_info: Dict[str, Any]) -> str:
        """Genera un resumen de toda la información médica acumulada"""
        medical_data = accumulated_info["combined_medical_data"]
        processing_summary = accumulated_info["processing_summary"]
        
        summary_parts = []
        
        # Header con estadísticas
        summary_parts.append(f"📋 **DOCUMENTOS PROCESADOS ({processing_summary['total_images_processed']} imágenes)**")
        
        # Información del paciente
        if medical_data.get("patient_name") or medical_data.get("document_id"):
            summary_parts.append("👤 **PACIENTE:**")
            if medical_data.get("patient_name"):
                summary_parts.append(f"   • Nombre: {medical_data['patient_name']}")
            if medical_data.get("document_id"):
                summary_parts.append(f"   • Documento: {medical_data['document_id']}")
        
        # Información médica
        if medical_data.get("doctor_name") or medical_data.get("specialty"):
            summary_parts.append("👨‍⚕️ **INFORMACIÓN MÉDICA:**")
            if medical_data.get("doctor_name"):
                summary_parts.append(f"   • Doctor: {medical_data['doctor_name']}")
            if medical_data.get("specialty"):
                summary_parts.append(f"   • Especialidad: {medical_data['specialty']}")
        
        # Procedimientos y sesiones
        if medical_data.get("procedures") or medical_data.get("session_count"):
            summary_parts.append("🏥 **TRATAMIENTO:**")
            if medical_data.get("procedures"):
                for proc in medical_data["procedures"][:3]:  # Máximo 3 procedimientos
                    summary_parts.append(f"   • {proc}")
            if medical_data.get("session_count"):
                summary_parts.append(f"   • Sesiones prescritas: {medical_data['session_count']}")
        
        # Documentos detectados
        if processing_summary["document_types_detected"]:
            doc_types_es = {
                "orden_medica": "Orden médica",
                "laboratorio": "Resultados laboratorio", 
                "radiografia": "Radiografía/Imágenes",
                "historia_clinica": "Historia clínica",
                "documento_medico": "Documento médico"
            }
            summary_parts.append("📄 **TIPOS DE DOCUMENTO:**")
            for doc_type in processing_summary["document_types_detected"]:
                doc_name = doc_types_es.get(doc_type, doc_type.title())
                summary_parts.append(f"   ✅ {doc_name}")
        
        # Confianza
        confidence = processing_summary["confidence_score"]
        if confidence >= 0.8:
            confidence_emoji = "🎯"
            confidence_text = "Excelente"
        elif confidence >= 0.6:
            confidence_emoji = "✅"
            confidence_text = "Buena"
        else:
            confidence_emoji = "⚠️"
            confidence_text = "Básica"
        
        summary_parts.append(f"{confidence_emoji} **Calidad información:** {confidence_text} ({confidence:.0%})")
        
        return "\n".join(summary_parts)
    
    def should_trigger_processing(self, historial: List[tuple], mensaje: str) -> bool:
        """
        Determina si debe procesar la información acumulada basándose en:
        1. Frases que indican fin de envío de documentos
        2. Tiempo transcurrido desde último documento
        3. Intención de proceder con agendamiento
        """
        mensaje_lower = mensaje.lower().strip()
        
        # Frases que indican fin de envío de documentos
        trigger_phrases = [
            "eso es todo", "ya está", "ya esta", "es todo",
            "procede", "proceder", "continua", "continúa", 
            "agenda", "agendar", "cuando", "cuándo",
            "fecha", "hora", "disponible", "cita",
            "listo", "completo", "termino", "terminé",
            "ya envié todo", "ya envie todo", "eso sería todo"
        ]
        
        # Verificar si el mensaje indica finalización
        if any(phrase in mensaje_lower for phrase in trigger_phrases):
            return True
        
        # Si hay información médica acumulada y el mensaje no contiene media
        ocr_entries = [entry for entry in historial if entry[0] in ['usuario_media_ocr', 'medical_info_extracted']]
        if len(ocr_entries) > 0:
            # Considerar procesar si el mensaje parece una pregunta o solicitud de continuación
            continuation_phrases = [
                "?", "que sigue", "qué sigue", "siguiente paso",
                "y ahora", "puedo", "podemos", "necesito"
            ]
            if any(phrase in mensaje_lower for phrase in continuation_phrases):
                return True
        
        return False

def detect_audio_message(media_type: str) -> bool:
    """
    Detecta si el mensaje contiene audio
    """
    if not media_type:
        return False
    
    audio_types = [
        "audio/",
        "audio/mpeg",
        "audio/mp3", 
        "audio/wav",
        "audio/ogg",
        "audio/m4a"
    ]
    
    return any(media_type.lower().startswith(audio_type) for audio_type in audio_types)

def get_audio_response_message() -> str:
    """
    Retorna el mensaje estándar para responder a audios
    """
    return "Por favor, escribe tu mensaje en texto para poder ayudarte mejor. Los audios no puedo procesarlos 😊"

# Instancia global
document_accumulator = DocumentAccumulator()