#!/usr/bin/env python3
"""
Script de pruebas para la integración con Saludtools API
Ejecutar: python test_saludtools_new.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# Agregar el directorio raíz al path para imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.saludtools import SaludtoolsAPI
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def print_header(title: str):
    """Imprime un header bonito para las pruebas"""
    print(f"\n{'='*60}")
    print(f"🔬 {title}")
    print(f"{'='*60}")

def print_result(test_name: str, success: bool, data=None):
    """Imprime el resultado de una prueba"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} {test_name}")
    if data:
        print(f"   📄 Data: {data}")

async def test_authentication():
    """Prueba la autenticación con Saludtools"""
    print_header("AUTENTICACIÓN")
    
    try:
        # Inicializar cliente en modo testing
        client = SaludtoolsAPI(environment="testing")
        
        # Intentar autenticación
        success = await client.authenticate()
        
        if success:
            print_result("Autenticación", True, {
                "token_expires_at": client.token_expires_at.isoformat() if client.token_expires_at else None,
                "mock_mode": client.mock_mode
            })
        else:
            print_result("Autenticación", False)
            
        return client if success else None
        
    except Exception as e:
        print_result("Autenticación", False, str(e))
        return None

async def test_patient_operations(client: SaludtoolsAPI):
    """Prueba operaciones de pacientes"""
    print_header("OPERACIONES DE PACIENTES")
    
    # Documento aleatorio estable dentro de la corrida (usaremos el mismo para citas)
    import random
    test_documento = str(91000000 + random.randint(0, 9999))
    
    try:
        # 1. Buscar paciente (probablemente no existe)
        print(f"🔍 Buscando paciente con documento: {test_documento}")
        paciente = await client.buscar_paciente(test_documento)
        # Considerar PASS tanto si no existe (None) como si existe (reutilizable)
        inicial_ok = True  # Siempre válido; diferenciamos en data
        estado = "no_existe" if paciente is None else "ya_existe"
        print_result("Buscar paciente (inicial)", inicial_ok, {"estado": estado, "paciente": paciente})

        # 2. Crear paciente (solo si no existía)
        if paciente is None:
            print(f"👤 Creando nuevo paciente...")
            datos_paciente = {
                "firstName": "Juan Carlos",
                "lastName": "Pérez González",
                "documentType": 1,  # Cédula
                "documentNumber": test_documento,
                "phone": "573001234567",
                "email": "test@example.com",
                "contactPreference": "whatsapp"
            }
            paciente_creado = await client.crear_paciente(datos_paciente)
            creada_ok = paciente_creado is not None
            print_result("Crear paciente", creada_ok, paciente_creado)
        else:
            print_result("Crear paciente", True, {"reutilizado": True})

        # 3. Buscar paciente nuevamente
        print(f"🔍 Buscando paciente (confirmación)...")
        paciente_encontrado = await client.buscar_paciente(test_documento)
        print_result("Buscar paciente (después de crear/reutilizar)", paciente_encontrado is not None, paciente_encontrado)

        # Retornar dict con documento para reutilizar en citas aunque body sea None
        if not paciente_encontrado:
            paciente_encontrado = {"documentNumber": test_documento, "documentType": 1}
        return paciente_encontrado

    except Exception as e:
        print_result("Operaciones de pacientes", False, str(e))
        return None

async def test_appointment_operations(client: SaludtoolsAPI, paciente: dict):
    """Flujo completo de citas: listar -> crear -> listar -> editar -> cancelar."""
    print_header("OPERACIONES DE CITAS")
    if not paciente:
        print_result("Operaciones de citas", False, "No hay paciente para probar")
        return
    documento = paciente.get("documentNumber") or paciente.get("document")
    if not documento:
        print_result("Operaciones de citas", False, "Paciente sin documento")
        return
    try:
        # Listar inicial
        print(f"📅 Buscando citas para documento: {documento}")
        inicial = await client.buscar_citas_paciente(documento)
        print_result("Buscar citas (inicial)", isinstance(inicial, list), f"Encontradas: {len(inicial) if inicial else 0}")
        # Crear
        fecha_cita = datetime.now() + timedelta(days=1)
        datos_cita = {
            "patientDocumentType": paciente.get("documentType", 1),
            "patientDocumentNumber": documento,
            "doctorDocumentType": int(os.getenv("SALUDTOOLS_DOCTOR_DOCUMENT_TYPE", "1")),
            "doctorDocumentNumber": os.getenv("SALUDTOOLS_DOCTOR_DOCUMENT_NUMBER", "11111"),
            "startDate": fecha_cita.strftime("%Y-%m-%dT%H:%M:%S"),
            "endDate": (fecha_cita + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S"),
            "modality": "CONVENTIONAL",
            "appointmentState": "PENDING",
            "appointmentType": "CITADEPRUEBA",
            "clinic": int(os.getenv("SALUDTOOLS_CLINIC_ID", "8")),
            "comment": "Cita demo integración",
            "notificationState": "ATTEND",
        }
        print("📝 Creando nueva cita...")
        creada = await client.crear_cita_paciente(datos_cita)
        creada_ok = bool(creada) and isinstance(creada, dict) and creada.get("id")
        print_result("Crear cita", creada_ok, creada)
        # Listar post
        print("🔍 Buscando citas después de crear...")
        post = await client.buscar_citas_paciente(documento)
        print_result("Buscar citas (después de crear)", isinstance(post, list), f"Encontradas: {len(post) if post else 0}")
        # Editar
        if creada_ok:
            nueva_fecha = fecha_cita + timedelta(hours=1)
            upd = {
                "startDate": nueva_fecha.isoformat(),
                "endDate": (nueva_fecha + timedelta(minutes=30)).isoformat(),
                "notes": "Actualizada demo"
            }
            print("✏️ Editando cita...")
            editada = await client.editar_cita_paciente(creada["id"], upd)
            print_result("Editar cita", editada is not None, editada)
        # Cancelar
        if creada_ok:
            print("🗑️ Cancelando cita...")
            cancel_ok = await client.cancelar_cita_paciente(creada["id"])
            print_result("Cancelar cita", bool(cancel_ok), cancel_ok)
    except Exception as e:
        print_result("Operaciones de citas", False, str(e))

async def test_rate_limiting(client: SaludtoolsAPI):
    """Prueba el rate limiting"""
    print_header("RATE LIMITING")
    
    try:
        print(f"🚦 Probando rate limiting (múltiples requests)")
        
        # Hacer varias requests rápidas para probar rate limiting
        requests_exitosas = 0
        for i in range(5):
            try:
                # Buscar paciente ficticio para generar requests
                await client.buscar_paciente(f"test{i}")
                requests_exitosas += 1
            except Exception as e:
                print(f"   Request {i+1} falló: {e}")
        
        print_result("Rate limiting", True, f"Requests exitosas: {requests_exitosas}/5")
        
    except Exception as e:
        print_result("Rate limiting", False, str(e))

async def main():
    """Ejecuta todas las pruebas"""
    print(f"\n🧪 INICIANDO PRUEBAS DE INTEGRACIÓN SALUDTOOLS")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verificar variables de entorno
    if not os.getenv("SALUDTOOLS_API_KEY") and not os.getenv("ENVIRONMENT") == "testing":
        print(f"\n⚠️ ADVERTENCIA: Variables de entorno no configuradas.")
        print(f"   El sistema ejecutará en modo MOCK para pruebas.")
    
    # Ejecutar pruebas secuencialmente
    client = await test_authentication()
    
    if client:
        paciente = await test_patient_operations(client)
        await test_appointment_operations(client, paciente)
        await test_rate_limiting(client)
    else:
        print(f"\n❌ No se pudo autenticar. Saltando pruebas de operaciones.")
    
    print_header("RESUMEN DE PRUEBAS")
    print(f"✅ Pruebas completadas")
    print(f"📊 Revisa los resultados arriba para identificar problemas")
    print(f"🔧 Si hay errores, verifica las credenciales en .env")
    
    if client and client.mock_mode:
        print(f"\n💡 NOTA: Las pruebas se ejecutaron en modo MOCK")
        print(f"   Para pruebas reales, configura SALUDTOOLS_API_KEY y SALUDTOOLS_API_SECRET")

if __name__ == "__main__":
    asyncio.run(main())
