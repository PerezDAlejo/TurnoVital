"""
Sistema de Agendamiento Médico con integración Saludtools
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de ambiente
ENVIRONMENT = os.getenv("ENVIRONMENT", "testing")  # testing o prod

# Configuración de logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Instancia global de Saludtools (se inicializa cuando se importe)
from .saludtools import SaludtoolsAPI

saludtools_client = SaludtoolsAPI(environment=ENVIRONMENT)