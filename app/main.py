from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routes import citas
from app.routes import webhook
from app.metrics import metrics
import openai
import os
from dotenv import load_dotenv

load_dotenv()  # <-- Esto carga las variables del .env

openai.api_key = os.getenv("OPENAI_API_KEY")

import uuid
from typing import Callable
from app.config import PHYSIO_ALLOWED_CANONICAL
from typing import Dict

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

# Cargar rutas
app.include_router(citas.router)
app.include_router(webhook.router)

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
def health():
    return {"status": "ok"}

@app.get("/metrics")
def metrics_endpoint():
    if os.getenv("METRICS_ENABLED", "1").lower() not in {"1","true","yes","on"}:
        return {"disabled": True}
    return metrics.snapshot()

@app.get("/tipos/fisioterapia")
def tipos_fisioterapia():
    return {"tipos": list(PHYSIO_ALLOWED_CANONICAL.keys())}

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