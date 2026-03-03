"""
ENDPOINT DE MONITOREO Y DASHBOARD - IPS REACT
API REST para monitoreo en tiempo real del sistema
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from typing import Dict, List, Optional, Any
import json
from datetime import datetime, timedelta
import os

router = APIRouter(prefix="/monitor", tags=["monitoring"])

@router.get("/status")
async def get_system_status():
    """Estado general del sistema"""
    try:
        from app.monitoring.ips_logger import get_system_status
        
        # Obtener estado del logger
        logger_status = get_system_status()
        
        # Agregar información adicional del sistema
        system_info = {
            "server_time": datetime.now().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "demo_mode": os.getenv("DEMO_MODE", "false").lower() == "true",
            "ocr_enabled": os.getenv("OCR_ENABLED", "1") == "1",
            "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        }
        
        # Estado de servicios
        services_status = await check_services_health()
        
        return {
            "status": "operational",
            "system_info": system_info,
            "logging": logger_status,
            "services": services_status,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estado: {str(e)}")

@router.get("/logs/{log_type}")
async def get_logs(log_type: str, lines: int = 50):
    """Obtener logs del sistema"""
    
    log_files = {
        "main": "logs/ips_react_main.log",
        "errors": "logs/errors/critical_errors.log", 
        "system": "logs/system/system_events.log",
        "users": "logs/users/user_interactions.log"
    }
    
    if log_type not in log_files:
        raise HTTPException(status_code=400, detail=f"Tipo de log inválido. Usar: {list(log_files.keys())}")
    
    log_file = log_files[log_type]
    
    try:
        if not os.path.exists(log_file):
            return {"logs": [], "message": "Archivo de log no encontrado"}
        
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "log_type": log_type,
            "lines_requested": lines,
            "lines_returned": len(recent_lines),
            "logs": [line.strip() for line in recent_lines],
            "file_path": log_file
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo logs: {str(e)}")

@router.get("/health")
async def health_check():
    """Health check básico del sistema"""
    try:
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "checks": {}
        }
        
        # Check base de datos
        try:
            from app.database import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            health_status["checks"]["database"] = "healthy"
        except Exception as e:
            health_status["checks"]["database"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Check OpenAI
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key and api_key.startswith("sk-"):
                health_status["checks"]["openai"] = "configured"
            else:
                health_status["checks"]["openai"] = "not_configured"
        except Exception as e:
            health_status["checks"]["openai"] = f"error: {str(e)}"
        
        # Check Saludtools
        try:
            from app.saludtools import SaludtoolsAPI
            api = SaludtoolsAPI()
            if api.mock_mode:
                health_status["checks"]["saludtools"] = "mock_mode"
            else:
                health_status["checks"]["saludtools"] = "configured"
        except Exception as e:
            health_status["checks"]["saludtools"] = f"error: {str(e)}"
            
        return health_status
        
    except Exception as e:
        return {
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }

@router.get("/dashboard", response_class=HTMLResponse)
async def monitoring_dashboard():
    """Dashboard HTML para monitoreo visual"""
    
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Monitor IPS React - Sistema de Agendamiento</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 100%);
                color: white;
                padding: 20px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 28px;
                margin-bottom: 5px;
            }
            
            .header p {
                opacity: 0.9;
                font-size: 16px;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                padding: 20px;
            }
            
            .stat-card {
                background: #f8fafc;
                border-radius: 8px;
                padding: 20px;
                border-left: 4px solid #10b981;
                transition: transform 0.2s;
            }
            
            .stat-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }
            
            .stat-card.error {
                border-left-color: #ef4444;
            }
            
            .stat-card.warning {
                border-left-color: #f59e0b;
            }
            
            .stat-title {
                font-weight: 600;
                color: #374151;
                margin-bottom: 8px;
            }
            
            .stat-value {
                font-size: 24px;
                font-weight: bold;
                color: #1f2937;
                margin-bottom: 4px;
            }
            
            .stat-description {
                color: #6b7280;
                font-size: 14px;
            }
            
            .logs-section {
                margin: 20px;
                background: #f9fafb;
                border-radius: 8px;
                padding: 20px;
            }
            
            .logs-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }
            
            .logs-container {
                background: #1f2937;
                color: #f3f4f6;
                padding: 15px;
                border-radius: 6px;
                max-height: 400px;
                overflow-y: auto;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                line-height: 1.4;
            }
            
            .log-entry {
                margin-bottom: 2px;
                word-wrap: break-word;
            }
            
            .log-error {
                color: #fca5a5;
            }
            
            .log-warning {
                color: #fcd34d;
            }
            
            .log-info {
                color: #93c5fd;
            }
            
            .refresh-btn {
                background: #4f46e5;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 500;
            }
            
            .refresh-btn:hover {
                background: #4338ca;
            }
            
            .status-indicator {
                display: inline-block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                margin-right: 8px;
            }
            
            .status-healthy {
                background: #10b981;
            }
            
            .status-warning {
                background: #f59e0b;
            }
            
            .status-error {
                background: #ef4444;
            }
            
            .auto-refresh {
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(255,255,255,0.9);
                padding: 10px;
                border-radius: 8px;
                font-size: 12px;
                color: #6b7280;
            }
        </style>
    </head>
    <body>
        <div class="auto-refresh">
            🔄 Auto-refresh: <span id="countdown">30</span>s
        </div>
        
        <div class="container">
            <div class="header">
                <h1>🏥 Monitor IPS React</h1>
                <p>Sistema de Agendamiento con IA - Estado en Tiempo Real</p>
            </div>
            
            <div class="stats-grid" id="statsGrid">
                <!-- Stats will be loaded here -->
            </div>
            
            <div class="logs-section">
                <div class="logs-header">
                    <h3>📋 Logs del Sistema</h3>
                    <div>
                        <select id="logType">
                            <option value="main">Principal</option>
                            <option value="errors">Errores</option>
                            <option value="system">Sistema</option>
                            <option value="users">Usuarios</option>
                        </select>
                        <button class="refresh-btn" onclick="loadLogs()">Actualizar</button>
                    </div>
                </div>
                <div class="logs-container" id="logsContainer">
                    Cargando logs...
                </div>
            </div>
        </div>
        
        <script>
            let countdown = 30;
            
            async function loadSystemStatus() {
                try {
                    const response = await fetch('/monitor/status');
                    const data = await response.json();
                    
                    const statsGrid = document.getElementById('statsGrid');
                    
                    // Calcular estado general
                    let systemStatus = 'healthy';
                    if (data.logging.critical_errors_count > 0) {
                        systemStatus = 'error';
                    } else if (data.logging.error_count > 10) {
                        systemStatus = 'warning';
                    }
                    
                    statsGrid.innerHTML = `
                        <div class="stat-card ${systemStatus === 'error' ? 'error' : systemStatus === 'warning' ? 'warning' : ''}">
                            <div class="stat-title">
                                <span class="status-indicator status-${systemStatus}"></span>
                                Estado del Sistema
                            </div>
                            <div class="stat-value">${systemStatus === 'healthy' ? '✅ Operativo' : systemStatus === 'warning' ? '⚠️ Advertencia' : '🚨 Error'}</div>
                            <div class="stat-description">Última actualización: ${new Date().toLocaleTimeString()}</div>
                        </div>
                        
                        <div class="stat-card">
                            <div class="stat-title">🤖 Modelo IA</div>
                            <div class="stat-value">${data.system_info.openai_model}</div>
                            <div class="stat-description">Chatbot IPS React Activo</div>
                        </div>
                        
                        <div class="stat-card">
                            <div class="stat-title">📊 Errores Sistema</div>
                            <div class="stat-value">${data.logging.error_count}</div>
                            <div class="stat-description">Errores registrados</div>
                        </div>
                        
                        <div class="stat-card ${data.logging.critical_errors_count > 0 ? 'error' : ''}">
                            <div class="stat-title">🚨 Errores Críticos</div>
                            <div class="stat-value">${data.logging.critical_errors_count}</div>
                            <div class="stat-description">Requieren atención inmediata</div>
                        </div>
                        
                        <div class="stat-card">
                            <div class="stat-title">📋 OCR Activo</div>
                            <div class="stat-value">${data.system_info.ocr_enabled ? '✅ Sí' : '❌ No'}</div>
                            <div class="stat-description">Procesamiento de órdenes médicas</div>
                        </div>
                        
                        <div class="stat-card">
                            <div class="stat-title">🏥 Ambiente</div>
                            <div class="stat-value">${data.system_info.environment.toUpperCase()}</div>
                            <div class="stat-description">Modo: ${data.system_info.demo_mode ? 'Demo' : 'Producción'}</div>
                        </div>
                    `;
                    
                } catch (error) {
                    console.error('Error loading system status:', error);
                    document.getElementById('statsGrid').innerHTML = 
                        '<div class="stat-card error"><div class="stat-title">❌ Error</div><div class="stat-value">No se pudo cargar el estado</div></div>';
                }
            }
            
            async function loadLogs() {
                try {
                    const logType = document.getElementById('logType').value;
                    const response = await fetch(`/monitor/logs/${logType}?lines=50`);
                    const data = await response.json();
                    
                    const logsContainer = document.getElementById('logsContainer');
                    
                    if (data.logs && data.logs.length > 0) {
                        logsContainer.innerHTML = data.logs.map(log => {
                            let logClass = '';
                            if (log.includes('ERROR') || log.includes('CRITICAL')) {
                                logClass = 'log-error';
                            } else if (log.includes('WARNING')) {
                                logClass = 'log-warning';
                            } else if (log.includes('INFO')) {
                                logClass = 'log-info';
                            }
                            
                            return `<div class="log-entry ${logClass}">${log}</div>`;
                        }).join('');
                    } else {
                        logsContainer.innerHTML = '<div class="log-entry">No hay logs disponibles</div>';
                    }
                    
                } catch (error) {
                    console.error('Error loading logs:', error);
                    document.getElementById('logsContainer').innerHTML = 
                        '<div class="log-entry log-error">Error cargando logs</div>';
                }
            }
            
            function startCountdown() {
                const countdownElement = document.getElementById('countdown');
                setInterval(() => {
                    countdown--;
                    countdownElement.textContent = countdown;
                    
                    if (countdown <= 0) {
                        countdown = 30;
                        loadSystemStatus();
                        loadLogs();
                    }
                }, 1000);
            }
            
            // Cargar datos iniciales
            document.addEventListener('DOMContentLoaded', () => {
                loadSystemStatus();
                loadLogs();
                startCountdown();
            });
            
            // Auto-refresh del selector de logs
            document.getElementById('logType').addEventListener('change', loadLogs);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

async def check_services_health():
    """Verificar estado de servicios externos"""
    services = {}
    
    # Check Saludtools
    try:
        from app.saludtools import SaludtoolsAPI
        api = SaludtoolsAPI()
        services["saludtools"] = "mock_mode" if api.mock_mode else "configured"
    except Exception:
        services["saludtools"] = "error"
    
    # Check Database  
    try:
        from app.database import get_db_connection
        with get_db_connection() as conn:
            services["database"] = "connected"
    except Exception:
        services["database"] = "error"
    
    # Check OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    services["openai"] = "configured" if api_key and api_key.startswith("sk-") else "not_configured"
    
    return services