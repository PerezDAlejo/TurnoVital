#!/usr/bin/env python3
"""
TEST INTEGRAL DE CORRECCIONES
Fecha: 12 de Diciembre de 2025
Objetivo: Verificar que todas las correcciones críticas funcionen correctamente
"""

import sys
import os

# Agregar directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import mapear_tipo_fisioterapia
from app.chatbot_ips_react import IPSReactChatbot
import asyncio

# Colores para output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_test(name, passed, details=""):
    """Imprime resultado de test con colores"""
    status = f"{GREEN}✅ PASSED{RESET}" if passed else f"{RED}❌ FAILED{RESET}"
    print(f"{status} - {name}")
    if details:
        print(f"   {YELLOW}{details}{RESET}")

def print_section(title):
    """Imprime título de sección"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{title:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

# =============================================
# TEST 1: mapear_tipo_fisioterapia
# =============================================

def test_appointmentType():
    """Test de mappeo de tipos a strings exactos de SaludTools"""
    print_section("TEST 1: appointmentType Mapping")
    
    tests = [
        ("primera vez", 1, "Cita De Primera Vez"),
        ("control", 1, "Cita De Control"),
        ("acondicionamiento", 1, "Acondicionamiento Fisico"),
        ("primera vez con orden", 10, "Continuidad De Orden"),
        ("nueva fisioterapia", 5, "Continuidad De Orden"),
        ("continuidad", 1, "Continuidad De Orden"),
    ]
    
    passed_count = 0
    for descripcion, sesiones, expected in tests:
        result = mapear_tipo_fisioterapia(descripcion, sesiones_orden=sesiones)
        passed = result == expected
        print_test(
            f"'{descripcion}' + {sesiones} sesiones → '{result}'",
            passed,
            f"Expected: '{expected}'" if not passed else ""
        )
        if passed:
            passed_count += 1
    
    print(f"\n{YELLOW}Total: {passed_count}/{len(tests)} tests passed{RESET}")
    return passed_count == len(tests)

# =============================================
# TEST 2: Validación Pólizas Sin Convenio
# =============================================

async def test_polizas_sin_convenio():
    """Test de validación de pólizas sin convenio"""
    print_section("TEST 2: Pólizas Sin Convenio")
    
    chatbot = IPSReactChatbot()
    
    tests = [
        ("Colpatria", True),  # Sin convenio
        ("MedPlus", True),    # Sin convenio
        ("Sura", False),       # Con convenio
        ("Sanitas", False),    # Con convenio
        ("colmedica", True),   # Sin convenio (case insensitive)
        ("Liberty", True),     # Sin convenio
    ]
    
    passed_count = 0
    for eps, should_be_sin_convenio in tests:
        result = chatbot._validar_poliza_sin_convenio(eps)
        passed = result == should_be_sin_convenio
        estado = "SIN convenio" if result else "CON convenio"
        expected_estado = "SIN convenio" if should_be_sin_convenio else "CON convenio"
        
        print_test(
            f"{eps}: {estado}",
            passed,
            f"Expected: {expected_estado}" if not passed else ""
        )
        if passed:
            passed_count += 1
    
    print(f"\n{YELLOW}Total: {passed_count}/{len(tests)} tests passed{RESET}")
    return passed_count == len(tests)

# =============================================
# TEST 3: Validación Fisioterapeutas Cardíacos
# =============================================

async def test_fisioterapeutas_cardiacos():
    """Test de validación de fisioterapeutas para rehabilitación cardíaca"""
    print_section("TEST 3: Fisioterapeutas Cardíacos")
    
    chatbot = IPSReactChatbot()
    
    # Verificar que la lista esté correcta
    expected_cardiaca = [
        "Diana Daniella Arana Carvalho",
        "Ana Isabel Palacio Botero",
        "Adriana Acevedo Agudelo"
    ]
    
    passed = True
    for fisio in expected_cardiaca:
        if fisio in chatbot.fisioterapeutas_cardiaca:
            print_test(f"{fisio} en lista", True)
        else:
            print_test(f"{fisio} en lista", False, "NO encontrado en lista de cardíacos")
            passed = False
    
    # Verificar que solo sean 3
    if len(chatbot.fisioterapeutas_cardiaca) == 3:
        print_test("Exactamente 3 fisioterapeutas cardíacos", True)
    else:
        print_test(
            "Exactamente 3 fisioterapeutas cardíacos", 
            False, 
            f"Found {len(chatbot.fisioterapeutas_cardiaca)}"
        )
        passed = False
    
    return passed

# =============================================
# TEST 4: Validación Horario Coomeva
# =============================================

async def test_horario_coomeva():
    """Test de validación de horario para Coomeva"""
    print_section("TEST 4: Horario Coomeva")
    
    chatbot = IPSReactChatbot()
    
    tests = [
        ("09:00", "fisioterapia ortopédica", True),   # Dentro de franja
        ("14:30", "fisioterapia ortopédica", True),   # Dentro de franja
        ("16:00", "fisioterapia ortopédica", True),   # Límite superior
        ("08:30", "fisioterapia ortopédica", False),  # Antes de franja
        ("17:00", "fisioterapia ortopédica", False),  # Después de franja
        ("06:00", "rehabilitación cardíaca", True),   # Excepción cardíaca
        ("19:00", "rehabilitación cardíaca", True),   # Excepción cardíaca
    ]
    
    passed_count = 0
    for hora, tipo_fisio, should_be_valid in tests:
        result = chatbot._validar_horario_coomeva(hora, tipo_fisio)
        is_valid = result.get("valido", False)
        passed = is_valid == should_be_valid
        
        estado = "VÁLIDO" if is_valid else "INVÁLIDO"
        expected_estado = "VÁLIDO" if should_be_valid else "INVÁLIDO"
        
        print_test(
            f"{hora} - {tipo_fisio}: {estado}",
            passed,
            f"Expected: {expected_estado}" if not passed else ""
        )
        if passed:
            passed_count += 1
    
    print(f"\n{YELLOW}Total: {passed_count}/{len(tests)} tests passed{RESET}")
    return passed_count == len(tests)

# =============================================
# TEST 5: Campos de Contacto Emergencia
# =============================================

async def test_campos_contacto_emergencia():
    """Test de campos de contacto de emergencia en datos_paciente"""
    print_section("TEST 5: Campos Contacto Emergencia")
    
    chatbot = IPSReactChatbot()
    
    expected_fields = [
        "contacto_emergencia_nombre",
        "contacto_emergencia_telefono",
        "contacto_emergencia_parentesco"
    ]
    
    passed = True
    for field in expected_fields:
        if field in chatbot.datos_paciente:
            print_test(f"Campo '{field}' existe", True)
        else:
            print_test(f"Campo '{field}' existe", False, "NO encontrado en datos_paciente")
            passed = False
    
    return passed

# =============================================
# TEST 6: Obtener Fisioterapeuta Más Disponible
# =============================================

async def test_obtener_fisioterapeuta_disponible():
    """Test de obtención de fisioterapeuta más disponible"""
    print_section("TEST 6: Obtener Fisioterapeuta Disponible")
    
    chatbot = IPSReactChatbot()
    
    try:
        # Test para ortopédica (cualquiera)
        fisio_ortopedica = await chatbot._obtener_fisioterapeuta_mas_disponible("ortopedica")
        print_test(
            f"Fisioterapeuta para ortopédica: {fisio_ortopedica}",
            True
        )
        
        # Test para cardíaca (solo los 3 especializados)
        fisio_cardiaca = await chatbot._obtener_fisioterapeuta_mas_disponible("cardiaca")
        is_valid = fisio_cardiaca in chatbot.fisioterapeutas_cardiaca
        print_test(
            f"Fisioterapeuta para cardíaca: {fisio_cardiaca}",
            is_valid,
            "NO está en lista de cardíacos" if not is_valid else ""
        )
        
        return True
    except Exception as e:
        print_test("Obtener fisioterapeuta disponible", False, str(e))
        return False

# =============================================
# MAIN TEST RUNNER
# =============================================

async def main():
    """Ejecuta todos los tests"""
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}{'TEST INTEGRAL - CORRECCIONES SISTEMA IPS REACT':^60}{RESET}")
    print(f"{GREEN}{'='*60}{RESET}\n")
    
    results = {
        "appointmentType Mapping": test_appointmentType(),
        "Pólizas Sin Convenio": await test_polizas_sin_convenio(),
        "Fisioterapeutas Cardíacos": await test_fisioterapeutas_cardiacos(),
        "Horario Coomeva": await test_horario_coomeva(),
        "Campos Contacto Emergencia": await test_campos_contacto_emergencia(),
        "Obtener Fisioterapeuta Disponible": await test_obtener_fisioterapeuta_disponible()
    }
    
    # Resumen final
    print_section("RESUMEN FINAL")
    
    total_tests = len(results)
    passed_tests = sum(1 for passed in results.values() if passed)
    
    for test_name, passed in results.items():
        status = f"{GREEN}✅ PASSED{RESET}" if passed else f"{RED}❌ FAILED{RESET}"
        print(f"{status} - {test_name}")
    
    percentage = (passed_tests / total_tests) * 100
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    if passed_tests == total_tests:
        print(f"{GREEN}🎉 TODOS LOS TESTS PASARON: {passed_tests}/{total_tests} (100%){RESET}")
    else:
        print(f"{YELLOW}⚠️  TESTS PASADOS: {passed_tests}/{total_tests} ({percentage:.1f}%){RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
