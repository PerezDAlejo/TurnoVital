"""
🔍 SISTEMA DETECCIÓN DE DATOS FALTANTES
Detecta automáticamente qué información médica falta y la solicita al paciente
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class MedicalDataValidator:
    """Valida información médica extraída y detecta datos faltantes"""
    
    def __init__(self):
        # Campos obligatorios para cada tipo de cita
        self.required_fields = {
            "PRIMERA VEZ": {
                "patient_info": ["patient_name", "document_id", "telefono"],
                "medical_info": ["has_medical_order", "doctor_name", "specialty"],
                "appointment_info": ["session_count", "procedures"]
            },
            "CONTROL": {
                "patient_info": ["patient_name", "document_id", "telefono"],
                "medical_info": ["doctor_name"],
                "appointment_info": ["procedures"]
            },
            "ACONDICIONAMIENTO": {
                "patient_info": ["patient_name", "document_id", "telefono"],
                "appointment_info": ["procedures"]
            }
        }
        
        # Campos opcionales pero recomendados
        self.recommended_fields = {
            "patient_info": ["email", "plan_salud"],
            "medical_info": ["diagnosis", "medications"],
            "appointment_info": ["fecha_deseada", "franja"]
        }
    
    def validate_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida información médica extraída y retorna análisis de completitud
        """
        appointment_type = data.get('appointment_type', 'fisioterapia')
        patient_data = data.get('patient_data', {})
        medical_info = data.get('medical_info', {})
        
        # Campos obligatorios básicos
        required_patient_fields = ['nombre', 'cedula', 'telefono']
        required_medical_fields = ['diagnostico'] if appointment_type == 'fisioterapia' else []
        
        missing_data = []
        
        # Verificar datos del paciente
        for field in required_patient_fields:
            if not patient_data.get(field):
                missing_data.append(field)
        
        # Verificar información médica
        for field in required_medical_fields:
            if not medical_info.get(field):
                missing_data.append(field)
        
        # Campos recomendados
        recommended_fields = ['email', 'eps', 'alergias', 'medicamentos']
        missing_recommended = []
        
        for field in recommended_fields:
            if field in ['email', 'eps'] and not patient_data.get(field):
                missing_recommended.append(field)
            elif field in ['alergias', 'medicamentos'] and not medical_info.get(field):
                missing_recommended.append(field)
        
        # Calcular score de completitud
        total_fields = len(required_patient_fields) + len(required_medical_fields) + len(recommended_fields)
        missing_total = len(missing_data) + len(missing_recommended)
        completeness_score = max(0, (total_fields - missing_total) / total_fields)
        
        is_valid = len(missing_data) == 0  # Solo obligatorios determinan validez
        
        return {
            "is_valid": is_valid,
            "completeness_score": completeness_score,
            "missing_data": missing_data,
            "missing_recommended": missing_recommended,
            "total_fields": total_fields,
            "completion_message": self.generate_completion_message(missing_data, missing_recommended)
        }
    
    def validate_extracted_data_old(self, medical_info: Dict[str, Any], appointment_type: str = "PRIMERA VEZ") -> Dict[str, Any]:
        """
        Valida información médica extraída y retorna análisis de completitud
        """
        validation_result = {
            "is_complete": True,
            "missing_critical": [],
            "missing_recommended": [],
            "validation_score": 0.0,
            "suggestions": [],
            "required_questions": []
        }
        
        # Obtener campos requeridos para el tipo de cita
        required = self.required_fields.get(appointment_type, self.required_fields["PRIMERA VEZ"])
        
        # Validar información del paciente
        self._validate_patient_info(medical_info, required["patient_info"], validation_result)
        
        # Validar información médica
        self._validate_medical_info(medical_info, required["medical_info"], validation_result)
        
        # Validar información de cita
        self._validate_appointment_info(medical_info, required["appointment_info"], validation_result)
        
        # Validar campos recomendados
        self._validate_recommended_fields(medical_info, validation_result)
        
        # Calcular puntuación de completitud
        validation_result["validation_score"] = self._calculate_validation_score(validation_result)
        
        # Determinar si está completo
        validation_result["is_complete"] = len(validation_result["missing_critical"]) == 0
        
        # Generar preguntas necesarias
        validation_result["required_questions"] = self._generate_questions(validation_result)
        
        return validation_result
    
    def _validate_patient_info(self, medical_info: Dict[str, Any], required: List[str], result: Dict[str, Any]):
        """Valida información básica del paciente"""
        patient_data = medical_info.get("patient_data", {})
        
        for field in required:
            if field == "patient_name" and not medical_info.get("patient_name"):
                result["missing_critical"].append("nombre_completo")
                result["suggestions"].append("Necesito tu nombre completo para agendar la cita")
                
            elif field == "document_id" and not medical_info.get("document_id"):
                result["missing_critical"].append("documento_identidad")
                result["suggestions"].append("Por favor comparte tu número de cédula o documento de identidad")
                
            elif field == "telefono" and not patient_data.get("telefono"):
                result["missing_critical"].append("telefono_contacto")
                result["suggestions"].append("Confirma tu número de teléfono de contacto")
    
    def _validate_medical_info(self, medical_info: Dict[str, Any], required: List[str], result: Dict[str, Any]):
        """Valida información médica específica"""
        for field in required:
            if field == "has_medical_order" and not medical_info.get("has_medical_order"):
                result["missing_critical"].append("orden_medica")
                result["suggestions"].append("¿Tienes orden médica para el tratamiento? Si la tienes, envíame una foto")
                
            elif field == "doctor_name" and not medical_info.get("doctor_name"):
                result["missing_critical"].append("nombre_doctor")
                result["suggestions"].append("¿Cuál es el nombre del doctor que te dio la orden médica?")
                
            elif field == "specialty" and not medical_info.get("specialty"):
                result["missing_recommended"].append("especialidad_medica")
                result["suggestions"].append("¿Para qué especialidad médica es el tratamiento?")
    
    def _validate_appointment_info(self, medical_info: Dict[str, Any], required: List[str], result: Dict[str, Any]):
        """Valida información específica de la cita"""
        for field in required:
            if field == "session_count" and not medical_info.get("session_count"):
                result["missing_recommended"].append("numero_sesiones")
                result["suggestions"].append("¿Sabes cuántas sesiones de tratamiento necesitas?")
                
            elif field == "procedures" and not medical_info.get("procedures"):
                result["missing_recommended"].append("tipo_procedimiento")
                result["suggestions"].append("¿Qué tipo específico de tratamiento necesitas?")
    
    def _validate_recommended_fields(self, medical_info: Dict[str, Any], result: Dict[str, Any]):
        """Valida campos recomendados pero no críticos"""
        patient_data = medical_info.get("patient_data", {})
        
        if not patient_data.get("email"):
            result["missing_recommended"].append("email")
            result["suggestions"].append("¿Tienes email para confirmaciones? (opcional)")
        
        if not patient_data.get("plan_salud"):
            result["missing_recommended"].append("eps_plan_salud")
            result["suggestions"].append("¿Tienes EPS o plan de salud?")
    
    def _calculate_validation_score(self, result: Dict[str, Any]) -> float:
        """Calcula puntuación de completitud (0.0 a 1.0)"""
        critical_missing = len(result["missing_critical"])
        recommended_missing = len(result["missing_recommended"])
        
        # Penalizar más los campos críticos
        score = 1.0
        score -= (critical_missing * 0.2)  # -20% por cada campo crítico faltante
        score -= (recommended_missing * 0.05)  # -5% por cada campo recomendado faltante
        
        return max(0.0, score)
    
    def _generate_questions(self, result: Dict[str, Any]) -> List[str]:
        """Genera preguntas específicas para obtener datos faltantes"""
        questions = []
        
        # Mapear campos faltantes a preguntas específicas
        question_mapping = {
            "nombre_completo": "Por favor, dime tu nombre completo",
            "documento_identidad": "¿Cuál es tu número de cédula o documento de identidad?",
            "telefono_contacto": "Confirma tu número de teléfono de contacto",
            "orden_medica": "¿Tienes orden médica? Si es así, envíame una foto de la orden",
            "nombre_doctor": "¿Cuál es el nombre del doctor que te prescribió el tratamiento?",
            "numero_sesiones": "¿Cuántas sesiones de tratamiento necesitas según la orden médica?",
            "email": "¿Tienes correo electrónico para enviarte confirmaciones? (opcional)",
            "eps_plan_salud": "¿Tienes EPS o algún plan de salud?"
        }
        
        # Priorizar campos críticos
        for missing in result["missing_critical"]:
            if missing in question_mapping:
                questions.append(question_mapping[missing])
        
        # Agregar campos recomendados si no hay muchos críticos
        if len(result["missing_critical"]) <= 2:
            for missing in result["missing_recommended"][:2]:  # Máximo 2 recomendados
                if missing in question_mapping:
                    questions.append(question_mapping[missing])
        
        return questions
    
    def generate_completion_message(self, missing_data: List[str], missing_recommended: List[str]) -> str:
        """Genera mensaje para datos faltantes simples"""
        if not missing_data and not missing_recommended:
            return "✅ Información completa"
        
        parts = []
        if missing_data:
            parts.append(f"Faltan datos obligatorios: {', '.join(missing_data)}")
        if missing_recommended:
            parts.append(f"Datos recomendados faltantes: {', '.join(missing_recommended)}")
        
        return " | ".join(parts)
    
    def generate_completion_message_old(self, validation_result: Dict[str, Any]) -> str:
        """Genera mensaje para solicitar información faltante"""
        if validation_result["is_complete"]:
            return "✅ **Información completa** - Procedo con el agendamiento"
        
        score = validation_result["validation_score"]
        questions = validation_result["required_questions"]
        
        if score < 0.4:
            message_parts = [
                "📋 **Necesito algunos datos adicionales para agendar tu cita:**\n"
            ]
        elif score < 0.7:
            message_parts = [
                "✅ **Casi listo!** Solo necesito confirmar algunos datos:\n"
            ]
        else:
            message_parts = [
                "🎯 **Información casi completa** - solo un par de detalles:\n"
            ]
        
        # Agregar preguntas numeradas
        for i, question in enumerate(questions[:4], 1):  # Máximo 4 preguntas
            message_parts.append(f"{i}. {question}")
        
        message_parts.append("\n💬 **Puedes responder todo junto o una por una**")
        
        return "\n".join(message_parts)

# Instancia global
medical_validator = MedicalDataValidator()