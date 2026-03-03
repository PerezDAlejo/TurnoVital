from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routes import citas
from app.routes import webhook
from app.routes import admin  # Nuevo: rutas administrativas
from app.routes import admin_system  # Nuevo: administración del sistema
from app.routes import monitoring  # NUEVO: Monitoreo y dashboard
from app.routes import secretary_api  # NUEVO: API para secretarias (cola)
from app.metrics import metrics
from app.monitoring.ips_logger import LogEvent, LogLevel, SystemComponent
import openai
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()  # <-- Esto carga las variables del .env

openai.api_key = os.getenv("OPENAI_API_KEY")

import uuid
from typing import Callable
from app.config import PHYSIO_ALLOWED_CANONICAL
from typing import Dict
from datetime import datetime

app = FastAPI(
    title="Sistema de Agendamiento Médico",
    description="API para gestionar pacientes y citas de una clínica",
    version="1.0.0"
)

# Middleware CORS para futuras integraciones con frontend o Twilio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next: Callable):
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response

# Inicializar sistema de logging avanzado
@app.on_event("startup")
async def startup_event():
    from app.utils.timeout_manager import cleanup_expired_sessions
    from app.utils.system_monitor import system_monitor
    from app.routes.webhook import conversaciones, escalaciones, secretarias
    from app.monitoring.ips_logger import ips_logger, SystemComponent, LogLevel
    from app.database import init_connection_pool
    
    # Inicializar pool de conexiones de base de datos (OPCIONAL)
    try:
        init_connection_pool(minconn=2, maxconn=10)
        ips_logger.log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            level=LogLevel.INFO,
            component=SystemComponent.DATABASE,
            message="Pool de conexiones de base de datos inicializado exitosamente"
        ))
    except Exception as e:
        # Base de datos es opcional - el sistema puede funcionar sin ella
        ips_logger.log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            level=LogLevel.WARNING,
            component=SystemComponent.DATABASE,
            message=f"Base de datos PostgreSQL no disponible (modo sin BD): {str(e)}"
        ))
        print("⚠️  PostgreSQL no disponible - Sistema funcionará sin base de datos persistente")
        print("💡 Tip: Configura DATABASE_URL en .env para habilitar PostgreSQL")
    
    # Iniciar task en background para limpieza de sesiones
    try:
        asyncio.create_task(cleanup_expired_sessions(conversaciones, escalaciones, secretarias))
        ips_logger.log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            level=LogLevel.INFO,
            component=SystemComponent.GENERAL,
            message="Sistema de limpieza de sesiones iniciado"
        ))
    except Exception as e:
        ips_logger.log_system_error(SystemComponent.GENERAL, e)
    
    # Iniciar monitoreo del sistema
    try:
        asyncio.create_task(
            system_monitor.start_monitoring(conversaciones, escalaciones, secretarias)
        )
        ips_logger.log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            level=LogLevel.INFO,
            component=SystemComponent.GENERAL,
            message="Sistema de monitoreo iniciado exitosamente"
        ))
    except Exception as e:
        ips_logger.log_system_error(SystemComponent.GENERAL, e)
    
    # Log de inicio del sistema
    ips_logger.log_event(LogEvent(
        timestamp=datetime.now().isoformat(),
        level=LogLevel.INFO,
        component=SystemComponent.GENERAL,
        message="Sistema IPS React iniciado completamente",
        metadata={
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "demo_mode": os.getenv("DEMO_MODE", "false"),
            "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "ocr_enabled": os.getenv("OCR_ENABLED", "1")
        }
    ))

# Cargar rutas
app.include_router(citas.router)
app.include_router(webhook.router)
app.include_router(admin.router)  # Nuevo: rutas administrativas
app.include_router(admin_system.router)  # Nuevo: administración del sistema
app.include_router(monitoring.router)  # NUEVO: Monitoreo y dashboard
app.include_router(secretary_api.router)  # NUEVO: API para secretarias (cola)

@app.get("/")
def root():
    return {
        "name": "Sistema de Agendamiento Médico",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "mensaje": "API operativa. Visita /docs para interactuar."}

@app.get("/health")
async def health():
    """🆕 BUG #10 FIX: Health check comprehensivo"""
    from datetime import datetime
    import os
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "services": {}
    }
    
    # Check OpenAI
    try:
        import openai
        api_key = os.getenv("OPENAI_API_KEY")
        health_status["services"]["openai"] = {
            "status": "configured" if api_key else "missing_key",
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        }
    except Exception as e:
        health_status["services"]["openai"] = {"status": "error", "error": str(e)}
    
    # Check SaludTools
    try:
        from app.saludtools import SaludtoolsAPI
        saludtools = SaludtoolsAPI()
        health_status["services"]["saludtools"] = {
            "status": "initialized",
            "environment": saludtools.environment,
            "mock_mode": saludtools.mock_mode
        }
    except Exception as e:
        health_status["services"]["saludtools"] = {"status": "error", "error": str(e)}
    
    # Check Database (opcional)
    try:
        db_url = os.getenv("DATABASE_URL")
        health_status["services"]["database"] = {
            "status": "configured" if db_url else "not_configured",
            "optional": True
        }
    except Exception as e:
        health_status["services"]["database"] = {"status": "error", "error": str(e)}
    
    # Determinar status general
    critical_services = ["openai", "saludtools"]
    all_healthy = all(
        health_status["services"].get(svc, {}).get("status") not in ["error", "missing_key"]
        for svc in critical_services
    )
    
    if not all_healthy:
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/metrics")
def metrics_endpoint():
    """🆕 BUG #11 FIX: Métricas con más contexto"""
    if os.getenv("METRICS_ENABLED", "1").lower() not in {"1","true","yes","on"}:
        return {"disabled": True}
    
    from datetime import datetime
    base_metrics = metrics.snapshot()
    
    # Añadir contexto adicional
    enhanced_metrics = {
        **base_metrics,
        "timestamp": datetime.now().isoformat(),
        "uptime_info": {
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "version": "1.0.0"
        }
    }
    
    return enhanced_metrics

@app.get("/tipos/fisioterapia")
def tipos_fisioterapia():
    return {"tipos": list(PHYSIO_ALLOWED_CANONICAL.keys())}

@app.get("/monitor")
def monitor_endpoint():
    """🆕 BUG #11 FIX: Endpoint de monitoreo simple"""
    from app.monitoring_simple import simple_monitor
    return simple_monitor.get_stats()

def _prometheus_escape(s: str) -> str:
    return s.replace('-', '_').replace('.', '_')

@app.get("/metrics/prometheus")
def metrics_prometheus():
    if os.getenv("METRICS_ENABLED", "1").lower() not in {"1","true","yes","on"}:
        return "# metrics disabled\n"
    snap = metrics.snapshot()
    lines = ["# HELP app_uptime_seconds Uptime en segundos", "# TYPE app_uptime_seconds gauge", f"app_uptime_seconds {snap['uptime_sec']:.0f}"]
    for name, val in snap['counters'].items():
        esc = _prometheus_escape(f"app_counter_{name}")
        lines.append(f"# TYPE {esc} counter")
        lines.append(f"{esc} {val}")
    for name, val in snap['gauges'].items():
        esc = _prometheus_escape(f"app_gauge_{name}")
        lines.append(f"# TYPE {esc} gauge")
        lines.append(f"{esc} {val}")
    return "\n".join(lines) + "\n"