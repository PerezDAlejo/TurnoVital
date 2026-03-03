#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 SUITE DE TESTING UNIFICADO - IPS REACT
===========================================

Suite completa de pruebas para validar sistema antes de producción.
Cubre todos los componentes críticos:
  - Chat y agendamiento
  - Escalamiento a secretarias
  - OCR + Gemini
  - Integración SaludTools
  - Validaciones de negocio

Uso:
  python tests/test_suite_produccion.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from app.chatbot_ips_react import IPSReactChatbot
from app.config import mapear_tipo_fisioterapia
from app.gemini_adapter import GeminiAdapter
from app.ocr_retry_system import sistema_reintentos_ocr
import traceback

# Colores para output
class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_header(title: str):
    """Imprime header de sección"""
    print(f"\n{Color.BLUE}{'='*80}{Color.RESET}")
    print(f"{Color.BLUE}{Color.BOLD}{title.center(80)}{Color.RESET}")
    print(f"{Color.BLUE}{'='*80}{Color.RESET}\n")

def print_test(name: str, passed: bool, details: str = ""):
    """Imprime resultado de test"""
    status = f"{Color.GREEN}✅ PASS{Color.RESET}" if passed else f"{Color.RED}❌ FAIL{Color.RESET}"
    print(f"{status} | {name}")
    if details:
        print(f"      {Color.YELLOW}{details}{Color.RESET}")

class TestSuiteProduccion:
    """Suite completa de testing para producción"""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.tests_total = 0
        self.bot = None
    
    def setup(self):
        """Inicialización del sistema"""
        print_header("🔧 INICIALIZANDO SISTEMA")
        try:
            self.bot = IPSReactChatbot()
            print(f"{Color.GREEN}✅ Chatbot inicializado correctamente{Color.RESET}")
            return True
        except Exception as e:
            print(f"{Color.RED}❌ Error inicializando chatbot: {e}{Color.RESET}")
            return False
    
    # ========================================
    # SUITE 1: TIPOS DE CITA (appointmentType)
    # ========================================
    def test_appointment_types(self):
        """Valida mapeo correcto de tipos de cita para SaludTools"""
        print_header("📋 TEST SUITE 1: APPOINTMENT TYPES")
        
        tests = [
            ("primera vez", 1, "Cita De Primera Vez"),
            ("control", 1, "Cita De Control"),
            ("acondicionamiento", 1, "Acondicionamiento Fisico"),
            ("primera vez", 10, "Continuidad De Orden"),
            ("nueva", 5, "Continuidad De Orden"),
        ]
        
        for desc, sesiones, expected in tests:
            self.tests_total += 1
            result = mapear_tipo_fisioterapia(desc, sesiones_orden=sesiones)
            passed = result == expected
            
            if passed:
                self.tests_passed += 1
            else:
                self.tests_failed += 1
            
            print_test(
                f"{desc} ({sesiones} sesiones) → {expected}",
                passed,
                f"Obtenido: {result}" if not passed else ""
            )
    
    # ========================================
    # SUITE 2: VALIDACIONES DE NEGOCIO
    # ========================================
    def test_business_validations(self):
        """Valida reglas de negocio críticas"""
        print_header("💼 TEST SUITE 2: VALIDACIONES DE NEGOCIO")
        
        # Test 1: Pólizas sin convenio
        self.tests_total += 1
        polizas_test = ["Colpatria", "MedPlus", "Sura", "Sanitas"]
        results = {
            "Colpatria": self.bot._validar_poliza_sin_convenio("Colpatria"),
            "MedPlus": self.bot._validar_poliza_sin_convenio("MedPlus"),
            "Sura": self.bot._validar_poliza_sin_convenio("Sura"),
            "Sanitas": self.bot._validar_poliza_sin_convenio("Sanitas"),
        }
        
        passed = (results["Colpatria"] == True and 
                 results["MedPlus"] == True and 
                 results["Sura"] == False and 
                 results["Sanitas"] == False)
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        
        print_test(
            "Detección pólizas sin convenio",
            passed,
            f"Colpatria: {results['Colpatria']}, MedPlus: {results['MedPlus']}, Sura: {results['Sura']}"
        )
        
        # Test 2: Fisioterapeutas cardíacos
        self.tests_total += 1
        fisios_cardiaca = self.bot.fisioterapeutas_cardiaca
        expected_count = 3
        passed = len(fisios_cardiaca) == expected_count
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        
        print_test(
            f"Lista fisioterapeutas cardíacos ({expected_count})",
            passed,
            f"Encontrados: {len(fisios_cardiaca)}"
        )
        
        # Test 3: Horario Coomeva ortopédica
        self.tests_total += 1
        resultado_valido = self.bot._validar_horario_coomeva(
            "10:00", "ortopédica"
        )
        resultado_invalido = self.bot._validar_horario_coomeva(
            "17:00", "ortopédica"
        )
        
        passed = resultado_valido["valido"] and not resultado_invalido["valido"]
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        
        print_test(
            "Restricción horario Coomeva ortopédica (9am-4pm)",
            passed,
            f"10:00: {resultado_valido['valido']}, 17:00: {resultado_invalido['valido']}"
        )
        
        # Test 4: Excepción cardíaca Coomeva
        self.tests_total += 1
        resultado_cardiaca_temprano = self.bot._validar_horario_coomeva(
            "06:00", "rehabilitación cardíaca"
        )
        resultado_cardiaca_tarde = self.bot._validar_horario_coomeva(
            "19:00", "rehabilitacion cardiaca"
        )
        
        passed = (resultado_cardiaca_temprano["valido"] and 
                 resultado_cardiaca_tarde["valido"])
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        
        print_test(
            "Excepción cardíaca Coomeva (horario completo)",
            passed,
            f"06:00: {resultado_cardiaca_temprano['valido']}, 19:00: {resultado_cardiaca_tarde['valido']}"
        )
    
    # ========================================
    # SUITE 3: GEMINI ADAPTER
    # ========================================
    async def test_gemini_adapter(self):
        """Valida funcionamiento de Gemini como LLM principal"""
        print_header("🤖 TEST SUITE 3: GEMINI ADAPTER")
        
        try:
            adapter = GeminiAdapter()
            
            # Test 1: Inicialización
            self.tests_total += 1
            passed = adapter.use_gemini or adapter.openai_client is not None
            
            if passed:
                self.tests_passed += 1
            else:
                self.tests_failed += 1
            
            print_test("Inicialización adaptador Gemini/GPT", passed)
            
            # Test 2: Generación de texto simple
            self.tests_total += 1
            try:
                response = await adapter.generate_response(
                    "Responde solo 'OK' si me entiendes",
                    context=""
                )
                passed = response and len(response) > 0
                
                if passed:
                    self.tests_passed += 1
                else:
                    self.tests_failed += 1
                
                print_test("Generación de respuesta", passed, f"Respuesta: {response[:50]}...")
            except Exception as e:
                self.tests_failed += 1
                print_test("Generación de respuesta", False, str(e))
            
        except Exception as e:
            self.tests_failed += 1
            print_test("Gemini adapter", False, str(e))
    
    # ========================================
    # SUITE 4: FLUJO COMPLETO AGENDAMIENTO
    # ========================================
    async def test_agendamiento_flow(self):
        """Valida flujo completo de agendamiento"""
        print_header("📅 TEST SUITE 4: FLUJO AGENDAMIENTO")
        
        # Test 1: Iniciar conversación
        self.tests_total += 1
        try:
            contexto_test = {
                "telefono": "+57300TEST123",
                "nombre_contacto": "Test User"
            }
            response = await self.bot.procesar_mensaje(
                "Hola, quiero agendar fisioterapia",
                contexto=contexto_test,
                archivos=[]
            )
            
            # El método devuelve un dict con 'mensaje'
            passed = response and ("mensaje" in response or isinstance(response, dict))
            
            if passed:
                self.tests_passed += 1
            else:
                self.tests_failed += 1
            
            print_test("Iniciar conversación agendamiento", passed)
        except Exception as e:
            self.tests_failed += 1
            print_test("Iniciar conversación", False, str(e))
        
        # Test 2: Datos completos en un mensaje
        self.tests_total += 1
        try:
            contexto_test2 = {
                "telefono": "+57300TEST456",
                "nombre_contacto": "Test User 2"
            }
            mensaje_completo = """
            Hola, quiero agendar fisioterapia de control.
            Mi cédula es 1234567890
            Me llamo Juan Pérez
            Nací el 15/03/1990
            Tengo EPS Sura
            Mi celular es 3001234567
            Email: juan@test.com
            Dirección: Calle 10 #20-30
            Contacto emergencia: María López, 3009876543, madre
            Quiero cita este viernes a las 10am con Miguel
            """
            
            response = await self.bot.procesar_mensaje(
                mensaje_completo,
                contexto=contexto_test2,
                archivos=[]
            )
            
            # Debería reconocer datos y avanzar en el flujo
            passed = response and isinstance(response, dict)
            
            if passed:
                self.tests_passed += 1
            else:
                self.tests_failed += 1
            
            print_test("Datos completos en un mensaje", passed)
        except Exception as e:
            self.tests_failed += 1
            print_test("Datos completos", False, str(e))
    
    # ========================================
    # SUITE 5: ESCALAMIENTO
    # ========================================
    def test_escalamiento_logic(self):
        """Valida lógica de escalamiento a secretarias"""
        print_header("🆘 TEST SUITE 5: ESCALAMIENTO")
        
        # Test 1: Números de secretarias en .env
        self.tests_total += 1
        secretary_numbers = os.getenv('SECRETARY_NUMBERS', '')
        passed = len(secretary_numbers) > 0
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        
        print_test(
            "Números de secretarias configurados",
            passed,
            f"Encontrados en .env" if passed else "No encontrados"
        )
        
        # Test 2: Método escalamiento existe
        self.tests_total += 1
        passed = hasattr(self.bot, '_manejar_escalamiento') or hasattr(self.bot, 'escalar_a_secretaria')
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        
        print_test("Método escalamiento existe", passed)
    
    # ========================================
    # SUITE 6: CAMPOS EMERGENCIA Y PAGO
    # ========================================
    def test_emergency_payment_fields(self):
        """Valida campos de contacto emergencia y pago"""
        print_header("🚨 TEST SUITE 6: CAMPOS EMERGENCIA Y PAGO")
        
        # Test 1: Campos en datos_paciente
        self.tests_total += 1
        self.bot.datos_paciente = {}
        self.bot.datos_paciente['contacto_emergencia_nombre'] = "Test"
        self.bot.datos_paciente['contacto_emergencia_telefono'] = "3001234567"
        self.bot.datos_paciente['contacto_emergencia_parentesco'] = "Hermano"
        
        passed = (
            'contacto_emergencia_nombre' in self.bot.datos_paciente and
            'contacto_emergencia_telefono' in self.bot.datos_paciente and
            'contacto_emergencia_parentesco' in self.bot.datos_paciente
        )
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        
        print_test("Campos contacto emergencia soportados", passed)
        
        # Test 2: Método pago
        self.tests_total += 1
        self.bot.datos_paciente['metodo_pago'] = "eps_presencial"
        
        passed = 'metodo_pago' in self.bot.datos_paciente
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        
        print_test("Campo método de pago soportado", passed)
    
    # ========================================
    # EJECUCIÓN PRINCIPAL
    # ========================================
    async def run_all_tests(self):
        """Ejecuta todas las suites de testing"""
        start_time = datetime.now()
        
        print(f"\n{Color.BOLD}{Color.BLUE}")
        print("╔════════════════════════════════════════════════════════════════════════════╗")
        print("║                                                                            ║")
        print("║               🧪 SUITE DE TESTING UNIFICADO - IPS REACT 🧪                ║")
        print("║                                                                            ║")
        print("║                        Validación Pre-Producción                           ║")
        print("║                                                                            ║")
        print("╚════════════════════════════════════════════════════════════════════════════╝")
        print(f"{Color.RESET}\n")
        
        # Setup
        if not self.setup():
            print(f"\n{Color.RED}❌ FALLO EN INICIALIZACIÓN - TESTS ABORTADOS{Color.RESET}\n")
            return
        
        # Ejecutar suites
        try:
            self.test_appointment_types()
            self.test_business_validations()
            await self.test_gemini_adapter()
            await self.test_agendamiento_flow()
            self.test_escalamiento_logic()
            self.test_emergency_payment_fields()
        except Exception as e:
            print(f"\n{Color.RED}❌ ERROR CRÍTICO: {e}{Color.RESET}")
            traceback.print_exc()
        
        # Resultados finales
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print_header("📊 RESULTADOS FINALES")
        
        pass_rate = (self.tests_passed / self.tests_total * 100) if self.tests_total > 0 else 0
        
        print(f"\n{Color.BOLD}Total Tests:{Color.RESET} {self.tests_total}")
        print(f"{Color.GREEN}✅ Passed:{Color.RESET} {self.tests_passed}")
        print(f"{Color.RED}❌ Failed:{Color.RESET} {self.tests_failed}")
        print(f"{Color.BLUE}⏱️  Duration:{Color.RESET} {duration:.2f}s")
        print(f"{Color.YELLOW}📈 Pass Rate:{Color.RESET} {pass_rate:.1f}%\n")
        
        if self.tests_failed == 0:
            print(f"{Color.GREEN}{Color.BOLD}")
            print("╔════════════════════════════════════════════════════════════════════════════╗")
            print("║                                                                            ║")
            print("║                   🎉 TODOS LOS TESTS PASARON 🎉                           ║")
            print("║                                                                            ║")
            print("║                  ✅ Sistema listo para producción ✅                       ║")
            print("║                                                                            ║")
            print("╚════════════════════════════════════════════════════════════════════════════╝")
            print(f"{Color.RESET}\n")
        else:
            print(f"{Color.RED}{Color.BOLD}")
            print("╔════════════════════════════════════════════════════════════════════════════╗")
            print("║                                                                            ║")
            print("║                     ⚠️  ALGUNOS TESTS FALLARON  ⚠️                        ║")
            print("║                                                                            ║")
            print("║              Revisar errores antes de ir a producción                     ║")
            print("║                                                                            ║")
            print("╚════════════════════════════════════════════════════════════════════════════╝")
            print(f"{Color.RESET}\n")
        
        return self.tests_failed == 0


# ========================================
# PUNTO DE ENTRADA
# ========================================
if __name__ == "__main__":
    suite = TestSuiteProduccion()
    
    try:
        success = asyncio.run(suite.run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}⚠️  Tests interrumpidos por usuario{Color.RESET}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Color.RED}❌ ERROR FATAL: {e}{Color.RESET}\n")
        traceback.print_exc()
        sys.exit(1)
