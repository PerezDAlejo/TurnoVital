"""
Configuración de la IPS React
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Variables de entorno importantes
ENVIRONMENT = os.getenv("ENVIRONMENT", "testing")
DATABASE_URL = os.getenv("DATABASE_URL")
OCR_ENABLED = os.getenv("OCR_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")

# Información de la IPS
IPS_CONFIG = {
    "nombre": "IPS React",
    "nit": "900370593-7",
    "direccion": "Calle 10 32-115",
    "telefono": "",  # Pendiente
    "horarios": {
        "lunes": {"inicio": "06:00", "fin": "20:00"},
        "martes": {"inicio": "06:00", "fin": "20:00"},
        "miercoles": {"inicio": "06:00", "fin": "20:00"},
        "jueves": {"inicio": "06:00", "fin": "20:00"},
        "viernes": {"inicio": "06:00", "fin": "19:00"},
        "sabado": {"inicio": "08:00", "fin": "12:00"},  # Sábados habilitados
        "domingo": None   # Cerrado
    },
    "ultimo_paciente": {
        "lunes_jueves": "19:00",  # Último paciente 7pm-8pm
        "viernes": "18:00",  # Último paciente 6pm para terminar a 7pm
        "sabado": "11:00"  # Último paciente 11am para terminar a 12m
    }
}

# Tipos de citas disponibles
TIPOS_CITAS = {
    "fisioterapia": [
        {
            "id": "acondicionamiento",
            "nombre": "Acondicionamiento físico",
            "duracion": 60,
            "color": "AMARILLO",
            "categoria": "fisioterapia"
        },
        {
            "id": "control_fisioterapia",
            "nombre": "Control fisioterapia",
            "duracion": 60,
            "color": "VERDE",
            "categoria": "fisioterapia"
        },
        {
            "id": "fisioterapia_primera_vez",
            "nombre": "Fisioterapia primera vez",
            "duracion": 60,
            "color": "ROSADO",
            "categoria": "fisioterapia"
        },
        {
            "id": "continuidad_orden",
            "nombre": "Continuidad de orden",
            "duracion": 60,
            "color": "AZUL_CLARO",
            "categoria": "fisioterapia"
        },
        {
            "id": "cortesia",
            "nombre": "Cortesía",
            "duracion": 60,
            "color": "ROJO",
            "categoria": "fisioterapia"
        },
        {
            "id": "control_rehabilitacion_cardiaca",
            "nombre": "Control Rehabilitación Cardíaca",
            "duracion": 60,
            "color": "AZUL_OSCURO",
            "categoria": "fisioterapia"
        },
        {
            "id": "rehabilitacion_cardiaca_primera_vez",
            "nombre": "Rehabilitación cardíaca primera vez",
            "duracion": 60,
            "color": "MORADO",
            "categoria": "fisioterapia"
        }
    ],
    "medica": [
        {
            "id": "medica_primera_vez",
            "nombre": "Primera vez",
            "duracion": 30,
            "color": None,
            "categoria": "medica"
        },
        {
            "id": "medica_control",
            "nombre": "Control",
            "duracion": 30,
            "color": None,
            "categoria": "medica"
        }
    ]
}

# Tipos de fisioterapia para mapeo
TIPOS_FISIOTERAPIA = {
    "fisioterapia primera vez": "PRIMERAVEZ",
    "primera vez fisioterapia": "PRIMERAVEZ", 
    "control fisioterapia": "CONTROL",
    "fisioterapia control": "CONTROL",
    "acondicionamiento físico": "ACONDICIONAMIENTO",
    "acondicionamiento": "ACONDICIONAMIENTO",
    "rehabilitación cardíaca": "CONTROL",
    "continuidad orden médica": "CONTROL"
}

# ESPECIALISTAS - Lista configurada según directrices entregadas
ESPECIALISTAS = [
    # FISIOTERAPEUTAS
    {
        "id": "fisio_adriana_acevedo",
        "nombre": "Adriana Acevedo Agudelo",
        "especialidad": "fisioterapia",
        "categoria": "fisioterapia",
        "horarios": {},  # Se puede completar posteriormente si difiere del horario general
        "tipos_citas_permitidos": [t["id"] for t in TIPOS_CITAS["fisioterapia"]]
    },
    {
        "id": "fisio_ana_palacio",
        "nombre": "Ana Isabel Palacio Botero",
        "especialidad": "fisioterapia",
        "categoria": "fisioterapia",
        "horarios": {},
        "tipos_citas_permitidos": [t["id"] for t in TIPOS_CITAS["fisioterapia"]]
    },
    {
        "id": "fisio_diana_arana",
        "nombre": "Diana Daniella Arana Carvalho",
        "especialidad": "fisioterapia",
        "categoria": "fisioterapia",
        "horarios": {},
        "tipos_citas_permitidos": [t["id"] for t in TIPOS_CITAS["fisioterapia"]]
    },
    {
        "id": "fisio_diego_mosquera",
        "nombre": "Diego Andres Mosquera Torres",
        "especialidad": "fisioterapia",
        "categoria": "fisioterapia",
        "horarios": {},
        "tipos_citas_permitidos": [t["id"] for t in TIPOS_CITAS["fisioterapia"]]
    },
    {
        "id": "fisio_veronica_echeverri",
        "nombre": "Veronica Echeverri Restrepo",
        "especialidad": "fisioterapia",
        "categoria": "fisioterapia",
        "horarios": {},
        "tipos_citas_permitidos": [t["id"] for t in TIPOS_CITAS["fisioterapia"]]
    },
    {
        "id": "fisio_miguel_moreno",
        "nombre": "Miguel Ignacio Moreno Cardona",
        "especialidad": "fisioterapia",
        "categoria": "fisioterapia",
        "horarios": {},
        "tipos_citas_permitidos": [t["id"] for t in TIPOS_CITAS["fisioterapia"]]
    },
    {
        "id": "fisio_daniela_patino",
        "nombre": "Daniela Patiño Londoño",
        "especialidad": "fisioterapia",
        "categoria": "fisioterapia",
        "horarios": {},
        "tipos_citas_permitidos": [t["id"] for t in TIPOS_CITAS["fisioterapia"]]
    },
    # MÉDICOS
    {
        "id": "med_deporte_jorge_palacio",
        "nombre": "Jorge Ivan Palacio Uribe",
        "especialidad": "medico del deporte y actividad física",
        "categoria": "medica",
        "horarios": {},
        "tipos_citas_permitidos": ["medica_primera_vez", "medica_control"]
    },
    {
        "id": "nutricionista_maria_buitrago",
        "nombre": "Maria Camila del Mar Buitrago",
        "especialidad": "nutricionista",
        "categoria": "medica",
        "horarios": {},
        "tipos_citas_permitidos": ["medica_primera_vez", "medica_control"]
    },
    {
        "id": "med_internista_clara_cadavid",
        "nombre": "Clara Marcela Cadavid Roldan",
        "especialidad": "medico internista",
        "categoria": "medica",
        "horarios": {},
        "tipos_citas_permitidos": ["medica_primera_vez", "medica_control"]
    },
    {
        "id": "med_endocrino_diego_benitez",
        "nombre": "Diego Fernando Benitez España",
        "especialidad": "medico endocrinologo",
        "categoria": "medica",
        "horarios": {},
        "tipos_citas_permitidos": ["medica_primera_vez", "medica_control"]
    },
    {
        "id": "med_ortopedista_jaime_valencia",
        "nombre": "Jaime Valencia",
        "especialidad": "medico ortopedista",
        "categoria": "medica",
        "horarios": {},
        "tipos_citas_permitidos": ["medica_primera_vez", "medica_control"]
    },
]

# Restricciones / servicios NO cubiertos en fisioterapia (para filtrado conversacional)
RESTRICCIONES_FISIOTERAPIA = [
    "rehabilitacion suelo pelvico",
    "rehabilitacion del piso pelvico",
    "rehabilitacion patologias neurologicas",
    "hidroterapia",
    "crioterapia",
    "camara bariatrica",
    "paralisis miofascial",
]

# Mapeo controlado de tipos de cita de fisioterapia permitidos para el chatbot
PHYSIO_ALLOWED_CANONICAL = {
    "PRIMERAVEZ": {"labels": {"primera vez", "primera", "inicial", "valoracion", "evaluacion"}},
    "CONTROL": {"labels": {"control", "seguimiento"}},
    "ACONDICIONAMIENTO": {"labels": {"acondicionamiento", "ejercicio", "fortalecimiento"}},
}
PHYSIO_FORBIDDEN_KEYWORDS = {"SUELO PELV", "PELVIC", "NEUROL", "HIDRO", "CRIO", "BARIATR", "PARALIS", "MIOFASC"}

def mapear_tipo_fisioterapia(descripcion: str, sesiones_orden: int = 1) -> str:
    """Normaliza una descripción libre a los nombres exactos requeridos por SaludTools API.

    Retorna uno de: 
    - "Cita De Primera Vez" (fisioterapia primera vez con orden)
    - "Cita De Control" (fisioterapia seguimiento sin orden)
    - "Acondicionamiento Fisico" (acondicionamiento físico)
    - "Continuidad De Orden" (cuando la orden indica múltiples sesiones)
    
    Args:
        descripcion: Descripción del tipo de servicio
        sesiones_orden: Número de sesiones indicadas en la orden médica (si aplica)
    """
    if not descripcion:
        return "Cita De Control"
    
    raw = descripcion.strip().lower()
    upper = raw.upper()
    
    # Detectar si es continuidad de orden (múltiples sesiones)
    if sesiones_orden and sesiones_orden > 1:
        if "primer" in raw or "nueva" in raw or "primera vez" in raw:
            return "Continuidad De Orden"
    
    if "continuidad" in raw:
        return "Continuidad De Orden"
    
    # Detectar prohibidos (retornar Primera Vez para revisión)
    for kw in PHYSIO_FORBIDDEN_KEYWORDS:
        if kw in upper:
            return "Cita De Primera Vez"
    
    # Detectar acondicionamiento
    if "condicion" in raw or "acondi" in raw or "plan" in raw:
        return "Acondicionamiento Fisico"
    
    # Detectar primera vez
    for code, meta in PHYSIO_ALLOWED_CANONICAL.items():
        if any(lbl in raw for lbl in meta["labels"]):
            if code == "PRIMERAVEZ":
                return "Cita De Primera Vez"
            elif code == "ACONDICIONAMIENTO":
                return "Acondicionamiento Fisico"
    
    if "primer" in raw or "nueva" in raw or "primera vez" in raw:
        return "Cita De Primera Vez"
    
    # Default: control
    return "Cita De Control"

def es_servicio_restringido_fisioterapia(descripcion: str) -> bool:
    """Detecta si la descripción contiene un servicio no ofrecido."""
    if not descripcion:
        return False
    texto = descripcion.lower()
    return any(r in texto for r in RESTRICCIONES_FISIOTERAPIA)

# Función para obtener todos los tipos de citas
def obtener_todos_tipos_citas():
    """Retorna todos los tipos de citas disponibles"""
    return TIPOS_CITAS["fisioterapia"] + TIPOS_CITAS["medica"]

# Función para obtener tipos por categoría
def obtener_tipos_por_categoria(categoria: str):
    """Retorna tipos de citas por categoría (fisioterapia o medica)"""
    return TIPOS_CITAS.get(categoria, [])

# Función para obtener especialistas por categoría
def obtener_especialistas_por_categoria(categoria: str):
    """Retorna especialistas por categoría (medica o fisioterapia)"""
    return [esp for esp in ESPECIALISTAS if esp.get("categoria") == categoria]

# Función para obtener especialista por ID
def obtener_especialista_por_id(especialista_id: str):
    """Retorna datos del especialista por ID"""
    for esp in ESPECIALISTAS:
        if esp.get("id") == especialista_id:
            return esp
    return None

# Función para validar horarios
def es_horario_valido(dia: str, hora: str, especialista_id: str = None) -> bool:
    """
    Valida si un horario está dentro del rango de atención
    
    Args:
        dia: Día de la semana (lunes, martes, etc.)
        hora: Hora en formato HH:MM
        especialista_id: ID del especialista (opcional)
    
    Returns:
        bool: True si está dentro del horario
    """
    # Validar horario general de la IPS
    horario_dia = IPS_CONFIG["horarios"].get(dia.lower())
    if not horario_dia:
        return False  # Día cerrado
    
    from datetime import datetime
    hora_obj = datetime.strptime(hora, "%H:%M").time()
    inicio_obj = datetime.strptime(horario_dia["inicio"], "%H:%M").time()
    fin_obj = datetime.strptime(horario_dia["fin"], "%H:%M").time()
    
    # Validar horario general
    if not (inicio_obj <= hora_obj <= fin_obj):
        return False
    
    # Si se especifica especialista, validar su horario específico
    if especialista_id:
        especialista = obtener_especialista_por_id(especialista_id)
        if especialista and especialista.get("horarios"):
            horario_especialista = especialista["horarios"].get(dia.lower())
            if horario_especialista:
                inicio_esp = datetime.strptime(horario_especialista["inicio"], "%H:%M").time()
                fin_esp = datetime.strptime(horario_especialista["fin"], "%H:%M").time()
                return inicio_esp <= hora_obj <= fin_esp
    
    return True

# Función para obtener información de horarios en texto
def obtener_horarios_texto() -> str:
    """Retorna los horarios en formato de texto legible"""
    return """
🏥 IPS React - Horarios de atención:
📍 Dirección: Calle 10 32-115

⏰ Horarios:
• Lunes a Jueves: 6:00 AM - 8:00 PM
• Viernes: 6:00 AM - 7:00 PM
• Sábados: 8:00 AM - 12:00 M
• Domingos: Cerrado

⚕️ Tipos de citas disponibles:

CITAS MÉDICAS (30 min):
• Primera vez
• Control

FISIOTERAPIA (60 min):
• Acondicionamiento físico
• Control fisioterapia  
• Fisioterapia primera vez
• Continuidad de orden
• Cortesía
• Control Rehabilitación Cardíaca
• Rehabilitación cardíaca primera vez

💡 Último paciente: 7:00 PM (L-J), 6:00 PM (V), 11:00 AM (S)
"""

def obtener_especialistas_texto() -> str:
    """Retorna la lista de especialistas en formato legible"""
    if not ESPECIALISTAS:
        return "Lista de especialistas pendiente de configuración"
    
    texto = "\n👨‍⚕️ ESPECIALISTAS DISPONIBLES:\n\n"
    
    # Agrupar por categoría
    medicos = obtener_especialistas_por_categoria("medica")
    fisioterapeutas = obtener_especialistas_por_categoria("fisioterapia")
    
    if medicos:
        texto += "MÉDICOS:\n"
        for esp in medicos:
            texto += f"• {esp['nombre']} - {esp['especialidad']}\n"
        texto += "\n"
    
    if fisioterapeutas:
        texto += "FISIOTERAPEUTAS:\n"
        for esp in fisioterapeutas:
            texto += f"• {esp['nombre']} - {esp['especialidad']}\n"
    
    return texto
