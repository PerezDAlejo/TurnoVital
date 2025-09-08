"""
Script de pruebas para la integración con Saludtools API
Ejecutar: python test_saludtools.py
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
    
    # 1. PRUEBA DE AUTENTICACIÓN
    print("1️⃣ PROBANDO AUTENTICACIÓN...")
    auth_success = await client.authenticate()
    if auth_success:
        print(f"✅ Autenticación exitosa. Token: {client.access_token[:20]}...")
    else:
        print("❌ Error en autenticación")
        return
    
    print()
    
    # 2. PRUEBA DE BÚSQUEDA DE PACIENTE
    print("2️⃣ PROBANDO BÚSQUEDA DE PACIENTE...")
    documento_prueba = "12345678"
    paciente = await client.buscar_paciente_por_documento(documento_prueba)
    
    if paciente:
        print(f"✅ Paciente encontrado: {paciente.get('firstName')} {paciente.get('lastName')}")
        print(f"   📄 Documento: {paciente.get('documentNumber')}")
        print(f"   📞 Teléfono: {paciente.get('phone')}")
    else:
        print("📝 Paciente no encontrado, procederemos a crear uno")
        
        # Crear paciente de prueba
        datos_paciente = {
            "firstName": "Juan Carlos",
            "lastName": "Pérez González",
            "documentType": 1,
            "documentNumber": documento_prueba,
            "phone": "3001234567",
            "email": "juan.perez@email.com",
            "contactPreference": "whatsapp"
        }
        
        paciente = await client.crear_paciente(datos_paciente)
        if paciente:
            print(f"✅ Paciente creado: {paciente.get('firstName')} {paciente.get('lastName')}")
        else:
            print("❌ Error creando paciente")
            return
    
    print()
    
    # 3. PRUEBA DE BÚSQUEDA DE CITAS
    print("3️⃣ PROBANDO BÚSQUEDA DE CITAS...")
    citas = await client.buscar_citas_por_documento(documento_prueba)
    print(f"📅 Encontradas {len(citas)} citas para el paciente:")
    
    for i, cita in enumerate(citas, 1):
        print(f"   {i}. ID: {cita.get('id')} - Fecha: {cita.get('startDate')} - Estado: {cita.get('appointmentState')}")
    
    print()
    
    # 4. PRUEBA DE CREACIÓN DE CITA
    print("4️⃣ PROBANDO CREACIÓN DE CITA...")
    fecha_cita = datetime.now() + timedelta(days=3)
    fecha_cita = fecha_cita.replace(hour=10, minute=0, second=0, microsecond=0)
    
    datos_cita = {
        "patientId": paciente.get("id"),
        "patientDocumentNumber": documento_prueba,
        "startDate": fecha_cita.isoformat(),
        "endDate": (fecha_cita + timedelta(minutes=30)).isoformat(),
        "appointmentType": "Consulta de prueba",
        "appointmentState": "PENDING",
        "notes": "Cita de prueba creada por script de testing"
    }
    
    cita_creada = await client.crear_cita(datos_cita)
    if cita_creada:
        print(f"✅ Cita creada exitosamente:")
        print(f"   🆔 ID: {cita_creada.get('id')}")
        print(f"   📅 Fecha: {datos_cita['startDate']}")
        print(f"   🏥 Tipo: {datos_cita['appointmentType']}")
        cita_id = cita_creada.get('id')
    else:
        print("❌ Error creando cita")
        return
    
    print()
    
    # 5. PRUEBA DE ACTUALIZACIÓN DE CITA
    print("5️⃣ PROBANDO ACTUALIZACIÓN DE CITA...")
    nueva_fecha = fecha_cita + timedelta(hours=2)  # 2 horas después
    
    datos_actualizacion = {
        "startDate": nueva_fecha.isoformat(),
        "endDate": (nueva_fecha + timedelta(minutes=30)).isoformat(),
        "notes": "Cita reprogramada por script de testing"
    }
    
    cita_actualizada = await client.actualizar_cita(cita_id, datos_actualizacion)
    if cita_actualizada:
        print(f"✅ Cita actualizada exitosamente:")
        print(f"   📅 Nueva fecha: {datos_actualizacion['startDate']}")
    else:
        print("❌ Error actualizando cita")
    
    print()
    
    # 6. PRUEBA DE PARÁMETROS DEL SISTEMA
    print("6️⃣ PROBANDO PARÁMETROS DEL SISTEMA...")
    
    tipos_documento = await client.obtener_tipos_documento()
    print(f"📄 Tipos de documento disponibles: {len(tipos_documento)}")
    for tipo in tipos_documento:
        print(f"   - {tipo.get('id')}: {tipo.get('name')}")
    
    estados_cita = await client.obtener_estados_cita()
    print(f"📋 Estados de cita disponibles: {len(estados_cita)}")
    for estado in estados_cita:
        print(f"   - {estado.get('id')}: {estado.get('name')}")
    
    print()
    
    # 7. PRUEBA DE CANCELACIÓN DE CITA
    print("7️⃣ PROBANDO CANCELACIÓN DE CITA...")
    cancelada = await client.cancelar_cita(cita_id)
    if cancelada:
        print(f"✅ Cita {cita_id} cancelada exitosamente")
    else:
        print("❌ Error cancelando cita")
    
    print()
    print("🎉 TODAS LAS PRUEBAS COMPLETADAS")
    print("=" * 60)
    
    # Resumen final
    if client.mock_mode:
        print("📝 RESUMEN: Todas las pruebas se ejecutaron en modo MOCK")
        print("🔧 Para probar con datos reales:")
        print("   1. Obtén credenciales de Saludtools")
        print("   2. Configura SALUDTOOLS_API_KEY y SALUDTOOLS_API_SECRET en .env")
        print("   3. Ejecuta el script nuevamente")
    else:
        print("📝 RESUMEN: Todas las pruebas se ejecutaron contra Saludtools QA")
        print("✅ La integración está funcionando correctamente")

async def test_funciones_conveniencia():
    """Prueba las funciones de conveniencia del módulo"""
    print("\n🔧 PROBANDO FUNCIONES DE CONVENIENCIA...")
    
    from app.saludtools import buscar_paciente, buscar_citas_paciente, crear_cita_paciente
    
    # Probar funciones de conveniencia
    documento = "87654321"
    
    paciente = await buscar_paciente(documento)
    print(f"🔍 Paciente {documento}: {'Encontrado' if paciente else 'No encontrado'}")
    
    citas = await buscar_citas_paciente(documento)
    print(f"📅 Citas encontradas: {len(citas)}")

if __name__ == "__main__":
    print("🚀 INICIANDO SCRIPT DE PRUEBAS SALUDTOOLS")
    print("Presiona Ctrl+C para cancelar en cualquier momento\n")
    
    try:
        # Ejecutar pruebas principales
        asyncio.run(test_saludtools_integration())
        
        # Ejecutar pruebas de funciones de conveniencia
        asyncio.run(test_funciones_conveniencia())
        
    except KeyboardInterrupt:
        print("\n⏹️ Pruebas interrumpidas por el usuario")
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
