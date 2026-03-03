"""
🔍 SISTEMA DE DETECCIÓN DE DATOS FALTANTES
Detecta automáticamente qué información médica falta y la solicita al paciente
"""
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MissingDataDetector:
    """Detecta datos faltantes en información médica extraída"""
    
    def __init__(self):
        # Datos mínimos requeridos para agendamiento
        self.required_patient_data = {
            "nombre": "Nombre completo del paciente",
            "documento": "Número de documento de identidad", 
            "telefono": "Número de teléfono de contacto",
            "email": "Correo electrónico (opcional)",
            "eps": "EPS o plan de salud",
            "tipo_cita": "Tipo de cita (fisioterapia, control, etc.)",
            "fecha_deseada": "Fecha preferida para la cita"
        }
        
        # Datos médicos importantes
        self.medical_requirements = {
            "tiene_orden_medica": "Orden médica válida",
            "doctor_prescriptor": "Nombre del doctor que prescribe",
            "diagnostico": "Diagnóstico o motivo de la cita",
            "sesiones_prescritas": "Número de sesiones prescritas"
        }
    
    def analyze_extracted_data(self, medical_info: Dict[str, Any], conversation_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analiza información extraída y detecta qué falta
        
        Args:
            medical_info: Información médica extraída del OCR
            conversation_data: Datos de la conversación (nombre, teléfono, etc.)
        
        Returns:
            Análisis completo con datos faltantes y sugerencias
        """
        analysis = {
            "completeness_score": 0.0,
            "missing_critical": [],
            "missing_optional": [],
            "available_data": {},
            "suggestions": [],
            "can_proceed": False,
            "next_steps": []
        }
        
        # Combinar datos disponibles
        available_data = {}
        if conversation_data:
            available_data.update(conversation_data)
        if medical_info:
            available_data.update(medical_info)
        
        analysis["available_data"] = available_data
        
        # Verificar datos críticos del paciente
        critical_missing = []
        for field, description in self.required_patient_data.items():
            if field == "email":  # Email es opcional
                continue
                
            value = available_data.get(field)
            if not value or (isinstance(value, str) and len(value.strip()) < 2):
                critical_missing.append({
                    "field": field,
                    "description": description,
                    "suggestion": self._get_field_suggestion(field)
                })
        
        analysis["missing_critical"] = critical_missing
        
        # Verificar datos médicos importantes
        medical_missing = []
        for field, description in self.medical_requirements.items():
            value = available_data.get(field)
            if not value:
                medical_missing.append({
                    "field": field,
                    "description": description,
                    "suggestion": self._get_medical_suggestion(field)
                })
        
        analysis["missing_optional"] = medical_missing
        
        # Calcular puntuación de completitud
        total_fields = len(self.required_patient_data) + len(self.medical_requirements)
        missing_count = len(critical_missing) + len(medical_missing)
        analysis["completeness_score"] = max(0, (total_fields - missing_count) / total_fields)
        
        # Determinar si puede proceder
        analysis["can_proceed"] = len(critical_missing) <= 2  # Máximo 2 datos críticos faltantes
        
        # Generar próximos pasos
        analysis["next_steps"] = self._generate_next_steps(critical_missing, medical_missing, available_data)
        
        return analysis
    
    def _get_field_suggestion(self, field: str) -> str:
        """Genera sugerencia específica para solicitar un campo"""
        suggestions = {
            "nombre": "Por favor, dime tu nombre completo",
            "documento": "¿Cuál es tu número de cédula o documento de identidad?",
            "telefono": "Confirma tu número de teléfono de contacto",
            "eps": "¿Cuál es tu EPS o plan de salud?",
            "tipo_cita": "¿Qué tipo de cita necesitas? (fisioterapia, control, etc.)",
            "fecha_deseada": "¿Para qué fecha te gustaría agendar la cita?"
        }
        return suggestions.get(field, f"Por favor proporciona tu {field}")
    
    def _get_medical_suggestion(self, field: str) -> str:
        """Genera sugerencia para datos médicos faltantes"""
        suggestions = {
            "tiene_orden_medica": "¿Tienes orden médica? Si es así, puedes enviarme la foto",
            "doctor_prescriptor": "¿Cuál es el nombre del doctor que te envió?",
            "diagnostico": "¿Cuál es el motivo o diagnóstico para la cita?",
            "sesiones_prescritas": "¿Cuántas sesiones te prescribió el doctor?"
        }
        return suggestions.get(field, f"¿Puedes proporcionarme información sobre {field}?")
    
    def _generate_next_steps(self, critical_missing: List[Dict], medical_missing: List[Dict], available_data: Dict) -> List[str]:
        """Genera lista de próximos pasos basado en datos faltantes"""
        steps = []
        
        if critical_missing:
            steps.append("📋 **INFORMACIÓN BÁSICA REQUERIDA:**")
            for item in critical_missing[:3]:  # Máximo 3 para no abrumar
                steps.append(f"• {item['suggestion']}")
        
        if medical_missing and len(critical_missing) <= 1:
            steps.append("\n🏥 **INFORMACIÓN MÉDICA ADICIONAL:**")
            for item in medical_missing[:2]:  # Máximo 2 adicionales
                steps.append(f"• {item['suggestion']}")
        
        # Si tiene orden médica pero falta info, sugerir envío
        if available_data.get("tiene_orden_medica") and not available_data.get("doctor_prescriptor"):
            steps.append("\n📸 **Si tienes más páginas de la orden médica, puedes enviarlas ahora**")
        
        return steps
    
    def generate_missing_data_request(self, analysis: Dict[str, Any]) -> str:
        """
        Genera mensaje amigable solicitando datos faltantes
        
        Args:
            analysis: Resultado del análisis de datos faltantes
        
        Returns:
            Mensaje para enviar al paciente
        """
        if analysis["can_proceed"] and analysis["completeness_score"] > 0.8:
            return self._generate_completion_message(analysis)
        
        # Mensaje base
        message_parts = []
        
        # Reconocer lo que ya se tiene
        available_data = analysis["available_data"]
        if available_data:
            message_parts.append("✅ **INFORMACIÓN RECIBIDA:**")
            if available_data.get("patient_name"):
                message_parts.append(f"• Paciente: {available_data['patient_name']}")
            if available_data.get("document_id"):
                message_parts.append(f"• Documento: {available_data['document_id']}")
            if available_data.get("has_medical_order"):
                message_parts.append("• Orden médica: Detectada")
            if available_data.get("session_count"):
                message_parts.append(f"• Sesiones: {available_data['session_count']}")
            if available_data.get("doctor_name"):
                message_parts.append(f"• Doctor: {available_data['doctor_name']}")
        
        # Solicitar datos faltantes
        if analysis["missing_critical"]:
            message_parts.append(f"\n📋 **PARA COMPLETAR TU AGENDAMIENTO NECESITO:**")
            
            for item in analysis["missing_critical"][:3]:  # Top 3 críticos
                message_parts.append(f"• {item['suggestion']}")
        
        # Datos médicos opcionales pero importantes
        if analysis["missing_optional"] and len(analysis["missing_critical"]) <= 1:
            message_parts.append("\n🏥 **INFORMACIÓN ADICIONAL ÚTIL:**")
            for item in analysis["missing_optional"][:2]:  # Top 2 opcionales
                message_parts.append(f"• {item['suggestion']}")
        
        # Mensaje motivacional
        completeness = analysis["completeness_score"]
        if completeness > 0.6:
            message_parts.append(f"\n🎯 **Ya tenemos {completeness:.0%} de la información. ¡Casi listos!**")
        else:
            message_parts.append("\n😊 **Proporciónando esta información podremos agendar tu cita rápidamente.**")
        
        return "\n".join(message_parts)
    
    def _generate_completion_message(self, analysis: Dict[str, Any]) -> str:
        """Genera mensaje cuando se tiene información suficiente"""
        available_data = analysis["available_data"]
        
        message_parts = [
            "🎯 **INFORMACIÓN COMPLETA PARA AGENDAMIENTO**\n"
        ]
        
        # Resumen de información disponible
        if available_data.get("patient_name"):
            message_parts.append(f"👤 **Paciente:** {available_data['patient_name']}")
        if available_data.get("document_id"):
            message_parts.append(f"📄 **Documento:** {available_data['document_id']}")
        if available_data.get("has_medical_order"):
            message_parts.append("📋 **Orden médica:** ✅ Confirmada")
        if available_data.get("session_count"):
            message_parts.append(f"🏥 **Sesiones:** {available_data['session_count']}")
        if available_data.get("doctor_name"):
            message_parts.append(f"👨‍⚕️ **Doctor:** {available_data['doctor_name']}")
        
        message_parts.append("\n✅ **¡Perfecto! Tengo toda la información necesaria.**")
        message_parts.append("\n📅 **¿Para qué fecha y hora te gustaría agendar tu cita?**")
        message_parts.append("Puedes decirme día específico o franja horaria de preferencia.")
        
        return "\n".join(message_parts)
    
    def should_escalate_to_secretary(self, analysis: Dict[str, Any]) -> tuple[bool, str]:
        """
        Determina si debe escalar a secretaria basado en completitud de datos
        
        Returns:
            (should_escalate, reason)
        """
        # Casos que requieren escalación
        if analysis["completeness_score"] < 0.4:
            return True, "Información insuficiente para procesamiento automático"
        
        missing_critical = analysis["missing_critical"]
        if len(missing_critical) > 3:
            return True, "Múltiples datos críticos faltantes"
        
        # Verificar campos críticos específicos
        critical_fields_missing = [item["field"] for item in missing_critical]
        if "nombre" in critical_fields_missing and "documento" in critical_fields_missing:
            return True, "Datos básicos del paciente faltantes"
        
        available_data = analysis["available_data"]
        if not available_data.get("has_medical_order") and not available_data.get("doctor_name"):
            return True, "Sin orden médica ni información del doctor"
        
        return False, "Información suficiente para procesamiento automático"

# Instancia global
missing_data_detector = MissingDataDetector()