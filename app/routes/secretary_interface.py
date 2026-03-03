# Interfaz web simple para secretarias gestionar disponibilidad
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
import json

# HTML para interfaz de secretarias
SECRETARY_INTERFACE_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Panel de Secretarias - Sistema de Citas</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .status-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
            background: #f9f9f9;
        }
        .available {
            border-left: 5px solid #28a745;
        }
        .busy {
            border-left: 5px solid #dc3545;
        }
        .escalation {
            border: 1px solid #007bff;
            background: #e7f3ff;
            margin: 10px 0;
            padding: 15px;
            border-radius: 8px;
        }
        .button {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
        }
        .button:hover {
            background: #0056b3;
        }
        .finish-btn {
            background: #28a745;
        }
        .finish-btn:hover {
            background: #1e7e34;
        }
        .queue-count {
            background: #ffc107;
            color: #000;
            padding: 5px 10px;
            border-radius: 15px;
            font-weight: bold;
        }
        .refresh-btn {
            background: #6c757d;
        }
        .auto-refresh {
            text-align: center;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏥 Panel de Secretarias - Sistema de Citas</h1>
        
        <div class="auto-refresh">
            <button class="button refresh-btn" onclick="location.reload()">🔄 Actualizar</button>
            <span>Auto-refresh cada 30s</span>
        </div>

        <div id="secretary-status">
            <h2>📊 Estado de Secretarias</h2>
            <div id="secretaries"></div>
        </div>

        <div id="queue-status">
            <h2>📋 Cola de Espera <span class="queue-count" id="queue-count">0</span></h2>
            <div id="queue"></div>
        </div>

        <div id="escalations">
            <h2>🚨 Casos Activos</h2>
            <div id="active-cases"></div>
        </div>
    </div>

    <script>
        async function loadData() {
            try {
                const response = await fetch('/human/escalations');
                const data = await response.json();
                
                // Actualizar estado de secretarias
                const secretariesDiv = document.getElementById('secretaries');
                secretariesDiv.innerHTML = '';
                
                Object.entries(data.secretarias || {}).forEach(([phone, info]) => {
                    const assigned = info.assigned || 0;
                    const isAvailable = assigned === 0;
                    
                    secretariesDiv.innerHTML += `
                        <div class="status-card ${isAvailable ? 'available' : 'busy'}">
                            <strong>${phone}</strong>
                            <br>Estado: ${isAvailable ? '✅ Disponible' : '🔴 Ocupada'}
                            <br>Casos asignados: ${assigned}
                        </div>
                    `;
                });

                // Actualizar cola
                const queueCount = data.queue ? data.queue.length : 0;
                document.getElementById('queue-count').textContent = queueCount;
                
                const queueDiv = document.getElementById('queue');
                queueDiv.innerHTML = '';
                
                if (queueCount === 0) {
                    queueDiv.innerHTML = '<p>No hay casos en cola</p>';
                } else {
                    (data.queue || []).forEach(caseId => {
                        queueDiv.innerHTML += `
                            <div class="escalation">
                                <strong>Caso: ${caseId}</strong>
                                <br>⏱️ Esperando asignación automática
                            </div>
                        `;
                    });
                }

                // Actualizar casos activos
                const casesDiv = document.getElementById('active-cases');
                casesDiv.innerHTML = '';
                
                Object.entries(data.escalaciones || {}).forEach(([telefono, escalacion]) => {
                    const assignment = escalacion.assignment || {};
                    const assignedTo = assignment.assigned_to || 'No asignado';
                    const caseId = escalacion.caseId || 'Sin ID';
                    
                    casesDiv.innerHTML += `
                        <div class="escalation">
                            <strong>📞 ${telefono}</strong>
                            <br><strong>Caso:</strong> ${caseId}
                            <br><strong>Asignado a:</strong> ${assignedTo}
                            <br><strong>Motivo:</strong> ${escalacion.motivo || 'No especificado'}
                            <br>
                            <button class="button finish-btn" onclick="finishCase('${telefono}')">
                                ✅ Marcar como Terminado
                            </button>
                            <button class="button" onclick="releaseCase('${telefono}')">
                                🔄 Liberar Caso
                            </button>
                        </div>
                    `;
                });

                if (Object.keys(data.escalaciones || {}).length === 0) {
                    casesDiv.innerHTML = '<p>No hay casos activos</p>';
                }

            } catch (error) {
                console.error('Error cargando datos:', error);
            }
        }

        async function finishCase(telefono) {
            try {
                const response = await fetch(`/human/resolve/${telefono}`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.success) {
                    alert('✅ Caso marcado como terminado');
                    loadData(); // Recargar datos
                } else {
                    alert('❌ Error: ' + result.mensaje);
                }
            } catch (error) {
                alert('❌ Error de conexión');
            }
        }

        async function releaseCase(telefono) {
            try {
                const response = await fetch(`/human/release/${telefono}`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.success) {
                    alert('🔄 Caso liberado - el bot puede retomar');
                    loadData(); // Recargar datos
                } else {
                    alert('❌ Error: ' + result.mensaje);
                }
            } catch (error) {
                alert('❌ Error de conexión');
            }
        }

        // Cargar datos al inicio
        loadData();
        
        // Auto-refresh cada 30 segundos
        setInterval(loadData, 30000);
    </script>
</body>
</html>
"""

def get_secretary_interface():
    """Retorna la interfaz web para secretarias"""
    return HTMLResponse(content=SECRETARY_INTERFACE_HTML)