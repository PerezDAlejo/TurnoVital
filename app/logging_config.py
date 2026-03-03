"""
Configuración centralizada de logging para el sistema de agendamiento.
Unifica el manejo de logs y proporciona formateo consistente.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging(
    log_level: str = None,
    log_file: str = None,
    enable_console: bool = True,
    enable_file: bool = True
):
    """
    Configura el sistema de logging centralizado.
    
    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
        log_file: Archivo de log (por defecto: logs/agendamiento.log)
        enable_console: Habilitar logging en consola
        enable_file: Habilitar logging en archivo
    """
    
    # Determinar nivel de logging
    if not log_level:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Determinar archivo de log
    if not log_file:
        log_file = os.getenv("LOG_FILE", "logs/agendamiento.log")
    
    # Crear directorio de logs si no existe
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Configurar formato
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configurar el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Limpiar handlers existentes
    root_logger.handlers = []
    
    # Handler para consola
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, log_level))
        root_logger.addHandler(console_handler)
    
    # Handler para archivo con rotación
    if enable_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, log_level))
        root_logger.addHandler(file_handler)
    
    # Configurar loggers específicos
    configure_specific_loggers()
    
    logging.info(f"Sistema de logging configurado - Nivel: {log_level}, Archivo: {log_file}")

def configure_specific_loggers():
    """Configura loggers específicos para módulos particulares."""
    
    # Reducir verbosidad de bibliotecas externas
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("twilio").setLevel(logging.WARNING)
    
    # Configurar nuestros loggers
    app_loggers = [
        "app.sistema_agendamiento",
        "app.saludtools",
        "app.database",
        "app.notifications",
        "app.ai",
        "app.routes.webhook",
        "app.routes.citas"
    ]
    
    for logger_name in app_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)

def log_system_info():
    """Registra información del sistema al inicio."""
    logger = logging.getLogger("app.system")
    
    logger.info("=== INICIO DEL SISTEMA DE AGENDAMIENTO ===")
    logger.info(f"Fecha/Hora: {datetime.now().isoformat()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Plataforma: {sys.platform}")
    
    # Información de configuración (sin credenciales)
    env_vars = [
        "ENVIRONMENT",
        "API_DOCS_ENABLED",
        "CALENDAR_ENABLED",
        "NOTIFY_SECRETARIES",
        "SECRETARY_CAPACITY",
        "OCR_ENABLED"
    ]
    
    for var in env_vars:
        value = os.getenv(var, "No configurado")
        logger.info(f"Config {var}: {value}")
    
    logger.info("=== SISTEMA INICIADO ===")

def log_error_with_context(logger, error: Exception, context: dict = None):
    """
    Registra un error con contexto adicional.
    
    Args:
        logger: Logger a usar
        error: Excepción capturada
        context: Diccionario con contexto adicional
    """
    import traceback
    
    logger.error(f"ERROR: {str(error)}")
    
    if context:
        for key, value in context.items():
            logger.error(f"  {key}: {value}")
    
    logger.error("Traceback:")
    for line in traceback.format_exception(type(error), error, error.__traceback__):
        logger.error(f"  {line.strip()}")

# Configurar logging por defecto al importar este módulo
if not logging.getLogger().handlers:
    setup_logging()