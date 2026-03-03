"""
🔄 CACHE INTELIGENTE DE OCR
Evita reprocesar las mismas imágenes y mejora la velocidad
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from app import database as db

logger = logging.getLogger(__name__)

class OCRCache:
    """Cache inteligente para resultados de OCR"""
    
    @staticmethod
    def get_image_hash(image_data: bytes) -> str:
        """Genera hash único de la imagen"""
        return hashlib.sha256(image_data).hexdigest()
    
    @staticmethod
    def get_cached_result(image_hash: str) -> Optional[Dict[str, Any]]:
        """Busca resultado de OCR en cache con información de confianza mejorada"""
        try:
            conn = db.get_connection()
            cur = conn.cursor()

            # Buscar en cache (últimos 30 días)
            cur.execute("""
                SELECT ocr_text, medical_info, confidence_score, created_at, telefono
                FROM ocr_cache
                WHERE image_hash = %s
                AND created_at > %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (image_hash, datetime.now() - timedelta(days=30)))

            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                logger.info(f"OCR: Cache HIT para imagen {image_hash[:8]}...")

                # Parsear información médica con manejo de confianza
                medical_info = json.loads(result[1]) if result[1] else {}

                # Verificar si la información médica tiene análisis de confianza
                confidence_analysis = medical_info.get("confidence_analysis", {})
                overall_confidence = confidence_analysis.get("overall_confidence", result[2] or 0.0)

                return {
                    "ocr_text": result[0],
                    "medical_info": medical_info,
                    "confidence_score": overall_confidence,
                    "legacy_confidence_score": result[2],  # Mantener compatibilidad
                    "confidence_level": confidence_analysis.get("confidence_level", "unknown"),
                    "from_cache": True,
                    "cached_at": result[3],
                    "telefono": result[4]
                }

            logger.info(f"OCR: Cache MISS para imagen {image_hash[:8]}...")
            return None

        except Exception as e:
            logger.warning(f"Error consultando cache OCR: {e}")
            return None
    
    @staticmethod
    def save_result(image_hash: str, ocr_text: str, medical_info: Dict[str, Any],
                   confidence_score: float = 0.0, telefono: str = None) -> bool:
        """Guarda resultado de OCR en cache con información de confianza mejorada"""
        try:
            conn = db.get_connection()
            cur = conn.cursor()

            # Extraer información de confianza del medical_info si existe
            confidence_analysis = medical_info.get("confidence_analysis", {})
            overall_confidence = confidence_analysis.get("overall_confidence", confidence_score)
            confidence_level = confidence_analysis.get("confidence_level", "unknown")

            # Preparar medical_info para almacenamiento (asegurar compatibilidad)
            enhanced_medical_info = medical_info.copy()
            if "confidence_analysis" not in enhanced_medical_info:
                enhanced_medical_info["confidence_analysis"] = {
                    "overall_confidence": overall_confidence,
                    "confidence_level": confidence_level,
                    "detailed_scores": {},
                    "recommendations": []
                }

            # Insertar o actualizar cache con campos mejorados
            cur.execute("""
                INSERT INTO ocr_cache (image_hash, ocr_text, medical_info, confidence_score, telefono, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (image_hash) DO UPDATE SET
                    ocr_text = EXCLUDED.ocr_text,
                    medical_info = EXCLUDED.medical_info,
                    confidence_score = EXCLUDED.confidence_score,
                    telefono = EXCLUDED.telefono,
                    updated_at = %s
                WHERE ocr_cache.confidence_score < EXCLUDED.confidence_score
                   OR ocr_cache.created_at < EXCLUDED.created_at
            """, (
                image_hash,
                ocr_text,
                json.dumps(enhanced_medical_info, ensure_ascii=False),
                overall_confidence,  # Usar confianza general
                telefono,
                datetime.now(),
                datetime.now()
            ))

            conn.commit()
            cur.close()
            conn.close()

            logger.info(f"OCR: Resultado guardado en cache {image_hash[:8]}... (confianza: {confidence_level})")
            return True

        except Exception as e:
            logger.warning(f"Error guardando cache OCR: {e}")
            return False

class HistoricalAnalyzer:
    """Analizador de patrones históricos"""
    
    @staticmethod
    def get_common_patterns(telefono: str = None) -> Dict[str, Any]:
        """Obtiene patrones comunes de documentos con análisis de confianza mejorado"""
        try:
            conn = db.get_connection()
            cur = conn.cursor()

            where_clause = "WHERE telefono = %s" if telefono else ""
            params = [telefono] if telefono else []

            # Buscar patrones comunes con información de confianza
            cur.execute(f"""
                SELECT
                    medical_info,
                    COUNT(*) as frequency,
                    AVG(confidence_score) as avg_confidence,
                    MAX(confidence_score) as max_confidence,
                    MIN(confidence_score) as min_confidence
                FROM ocr_cache
                {where_clause}
                AND created_at > %s
                GROUP BY medical_info
                ORDER BY frequency DESC, avg_confidence DESC
                LIMIT 10
            """, params + [datetime.now() - timedelta(days=90)])

            patterns = []
            for row in cur.fetchall():
                if row[0]:  # Si hay medical_info
                    medical_info = json.loads(row[0])
                    confidence_analysis = medical_info.get("confidence_analysis", {})

                    patterns.append({
                        "medical_info": medical_info,
                        "frequency": row[1],
                        "avg_confidence": row[2],
                        "max_confidence": row[3],
                        "min_confidence": row[4],
                        "confidence_level": confidence_analysis.get("confidence_level", "unknown"),
                        "document_type": medical_info.get("document_type", "unknown")
                    })

            cur.close()
            conn.close()

            # Agregar estadísticas generales
            stats = {
                "patterns": patterns,
                "total_patterns": len(patterns),
                "avg_overall_confidence": sum(p["avg_confidence"] for p in patterns) / len(patterns) if patterns else 0,
                "most_common_document_type": max(patterns, key=lambda x: x["frequency"])["document_type"] if patterns else "unknown"
            }

            return stats

        except Exception as e:
            logger.warning(f"Error analizando patrones históricos: {e}")
            return {"patterns": [], "total_patterns": 0, "avg_overall_confidence": 0, "most_common_document_type": "unknown"}

class SmartValidator:
    """Validador inteligente usando datos históricos"""
    
    @staticmethod
    def validate_medical_info(medical_info: Dict[str, Any], telefono: str = None) -> Dict[str, Any]:
        """Valida información médica contra histórico del paciente"""
        try:
            if not telefono:
                return medical_info
            
            conn = db.get_connection()
            cur = conn.cursor()
            
            # Buscar paciente en base de datos
            cur.execute("""
                SELECT nombres, apellidos, documento 
                FROM pacientes 
                WHERE telefono = %s 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (telefono.replace("whatsapp:", ""),))
            
            paciente = cur.fetchone()
            
            if paciente:
                # Enriquecer información médica con datos del paciente
                medical_info["patient_name_from_db"] = f"{paciente[0]} {paciente[1]}"
                medical_info["document_from_db"] = paciente[2]
                medical_info["validated_patient"] = True
            
            cur.close()
            conn.close()
            
            return medical_info
            
        except Exception as e:
            logger.warning(f"Error validando información médica: {e}")
            return medical_info

# Instancias globales
ocr_cache = OCRCache()
historical_analyzer = HistoricalAnalyzer() 
smart_validator = SmartValidator()