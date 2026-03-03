# Configuración de precios y planes de la clínica
# Esta información será utilizada por la IA para informar a pacientes

PRECIOS_FISIOTERAPIA = {
    "particular": {
        "precio": 60000,
        "moneda": "COP",
        "descripcion": "Fisioterapia particular (primera vez o control)",
        "nota": "Sin póliza/EPS"
    },
    "con_poliza": {
        "precio": "Variable",
        "descripcion": "Depende de la entidad EPS/póliza",
        "nota": "El costo se define presencialmente según la póliza"
    }
}

PRECIOS_ACONDICIONAMIENTO = {
    "clase_individual": {
        "precio": 50000,
        "moneda": "COP", 
        "duracion": "1 hora",
        "descripcion": "Clase individual de acondicionamiento",
        "tipo": "particular"
    },
    "planes": {
        "basico": {
            "precio": 320000,
            "moneda": "COP",
            "periodo": "mes",
            "clases": 8,
            "frecuencia": "2 por semana",
            "acumulable": False,
            "descripcion": "Plan básico - 8 clases por mes"
        },
        "intermedio": {
            "precio": 380000,
            "moneda": "COP", 
            "periodo": "mes",
            "clases": 12,
            "frecuencia": "3 por semana",
            "acumulable": False,
            "descripcion": "Plan intermedio - 12 clases por mes"
        },
        "avanzado": {
            "precio": 440000,
            "moneda": "COP",
            "periodo": "mes", 
            "clases": 16,
            "frecuencia": "4 por semana",
            "acumulable": False,
            "descripción": "Plan avanzado - 16 clases por mes"
        },
        "intensivo": {
            "precio": 500000,
            "moneda": "COP",
            "periodo": "mes",
            "clases": 20, 
            "frecuencia": "5 por semana",
            "acumulable": False,
            "descripcion": "Plan intensivo - 20 clases por mes"
        }
    }
}

POLITICAS_AGENDAMIENTO = {
    "suscripciones": {
        "agendamiento_maximo": "2 semanas",
        "nota": "Para más de 2 semanas, gestión presencial en primera visita"
    }
}

METODOS_PAGO = {
    "presencial": [
        "Efectivo",
        "Tarjeta",
        "Transferencia"
    ],
    "en_linea": {
        "metodo": "Transferencia",
        "proceso": "Remitir a secretaria para gestión y comprobación de pago"
    }
}

# Función para generar información de precios para la IA
def get_precios_info():
    """Retorna información formateada de precios para la IA"""
    
    info = """
INFORMACIÓN DE PRECIOS Y PLANES:

🏥 FISIOTERAPIA:
• Particular (sin póliza/EPS): $60,000 COP
• Con póliza/EPS: Costo variable según entidad (se define presencialmente)

🏋️ ACONDICIONAMIENTO:
• Clase individual: $50,000 COP (1 hora)

📋 PLANES MENSUALES DE ACONDICIONAMIENTO:
• Plan Básico: $320,000 COP/mes - 8 clases (2 por semana)
• Plan Intermedio: $380,000 COP/mes - 12 clases (3 por semana)
• Plan Avanzado: $440,000 COP/mes - 16 clases (4 por semana)
• Plan Intensivo: $500,000 COP/mes - 20 clases (5 por semana)

⚠️ NOTAS IMPORTANTES:
- Las clases de planes mensuales NO son acumulables
- Con suscripción se pueden agendar hasta 2 semanas
- Para más de 2 semanas, gestión presencial en primera visita

💳 MÉTODOS DE PAGO:
• Presencial: Efectivo, tarjeta o transferencia
• En línea: Transferencia (requiere gestión con secretaria)
"""
    
    return info

def get_precio_especifico(tipo_servicio, plan=None):
    """Obtiene precio específico según el servicio solicitado"""
    
    if tipo_servicio.lower() in ["fisioterapia", "fisio"]:
        return {
            "particular": f"${PRECIOS_FISIOTERAPIA['particular']['precio']:,} COP",
            "con_poliza": "Variable según EPS/póliza (se define presencialmente)"
        }
    
    elif tipo_servicio.lower() in ["acondicionamiento", "gym", "ejercicio"]:
        if plan:
            plan_lower = plan.lower()
            if plan_lower in PRECIOS_ACONDICIONAMIENTO["planes"]:
                plan_info = PRECIOS_ACONDICIONAMIENTO["planes"][plan_lower]
                return {
                    "precio": f"${plan_info['precio']:,} COP/{plan_info['periodo']}",
                    "clases": f"{plan_info['clases']} clases",
                    "frecuencia": plan_info['frecuencia'],
                    "descripcion": plan_info['descripcion']
                }
        else:
            # Retornar información completa de acondicionamiento
            individual = PRECIOS_ACONDICIONAMIENTO["clase_individual"]
            planes = PRECIOS_ACONDICIONAMIENTO["planes"]
            
            info = {
                "clase_individual": f"${individual['precio']:,} COP por hora",
                "planes": {}
            }
            
            for nombre, datos in planes.items():
                info["planes"][nombre] = {
                    "precio": f"${datos['precio']:,} COP/mes",
                    "clases": f"{datos['clases']} clases ({datos['frecuencia']})"
                }
            
            return info
    
    return None

# Mensajes predefinidos para diferentes consultas de precios
MENSAJES_PRECIOS = {
    "fisioterapia": """🏥 **PRECIOS FISIOTERAPIA:**

💰 **Sin póliza/EPS (Particular):** $65,000 COP
💳 **Con póliza/EPS:** Variable según entidad
   (El costo se define presencialmente)

📞 ¿Te gustaría agendar tu cita de fisioterapia?""",

    "acondicionamiento": """🏋️ **PRECIOS ACONDICIONAMIENTO:**

💪 **Clase Individual:** $50,000 COP (1 hora)

📋 **PLANES MENSUALES:**
• **Básico:** $320,000 COP - 8 clases (2/semana)
• **Intermedio:** $380,000 COP - 12 clases (3/semana) 
• **Avanzado:** $440,000 COP - 16 clases (4/semana)
• **Intensivo:** $500,000 COP - 20 clases (5/semana)

⚠️ Las clases de planes NO son acumulables por mes

🗓️ **Agendamiento:** Hasta 2 semanas con suscripción
📞 ¿Te interesa algún plan en particular?""",

    "pagos": """💳 **MÉTODOS DE PAGO:**

🏥 **Presencial:**
• Efectivo
• Tarjeta de crédito/débito
• Transferencia

💻 **En línea:**
• Transferencia bancaria
• Requiere gestión con secretaria para comprobación

📞 Si quieres pagar por transferencia, te conectaré con una secretaria para gestionar el pago."""
}