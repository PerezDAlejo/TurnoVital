#!/usr/bin/env python3
"""
Servidor de desarrollo directo
"""
import os
import sys
import uvicorn

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app

if __name__ == "__main__":
    print("=" * 60)
    print("  SERVIDOR IPS REACT - SISTEMA DE AGENDAMIENTO MEDICO")
    print("=" * 60)
    print("\nEndpoints disponibles:")
    print("   - Health:  http://localhost:8000/health")
    print("   - Docs:    http://localhost:8000/docs")
    print("   - Webhook: http://localhost:8000/webhook/twilio")
    print("   - Metrics: http://localhost:8000/metrics")
    print("\n" + "=" * 60)
    print("Iniciando servidor...")
    print("=" * 60 + "\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )