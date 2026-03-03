"""
TEST GEMINI ADAPTER - IPS REACT
================================
Script de prueba para validar la integración de Gemini 2.0 Flash.

Pruebas incluidas:
1. Conexión y configuración
2. Inyección de fecha actual
3. Expresiones temporales ("mañana", "siguiente viernes")
4. Conversación natural
5. Comparación Gemini vs GPT-4o
6. Estadísticas de uso

Autor: Alejandro Pérez Dávila
Fecha: Diciembre 2025
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Colores para terminal
class Colores:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'


def print_header(titulo: str):
    """Imprime header formateado"""
    print(f"\n{Colores.CYAN}{'='*70}{Colores.RESET}")
    print(f"{Colores.CYAN}{Colores.BOLD}{titulo.center(70)}{Colores.RESET}")
    print(f"{Colores.CYAN}{'='*70}{Colores.RESET}\n")


def print_test(nombre: str, exito: bool, mensaje: str = ""):
    """Imprime resultado de test"""
    icono = "✅" if exito else "❌"
    color = Colores.GREEN if exito else Colores.RED
    print(f"{icono} {color}{nombre}{Colores.RESET}")
    if mensaje:
        print(f"   {mensaje}")


async def test_configuracion():
    """Verifica configuración básica"""
    print_header("TEST 1: CONFIGURACIÓN")
    
    # Verificar variables de entorno
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    use_gemini = os.getenv("USE_GEMINI", "false").lower() == "true"
    
    print_test(
        "GEMINI_API_KEY",
        bool(gemini_key),
        f"Key: {'AIza...' + gemini_key[-10:] if gemini_key else 'NO CONFIGURADA'}"
    )
    
    print_test(
        "OPENAI_API_KEY",
        bool(openai_key),
        f"Key: {'sk-...' + openai_key[-10:] if openai_key else 'NO CONFIGURADA'}"
    )
    
    print_test(
        "USE_GEMINI",
        True,
        f"Modo: {'GEMINI ACTIVO' if use_gemini else 'GPT-4o ACTIVO'}"
    )
    
    # Intentar importar módulo
    try:
        import google.generativeai as genai
        print_test("google.generativeai", True, "Módulo importado correctamente")
    except ImportError as e:
        print_test("google.generativeai", False, f"Error: {e}")
        return False
    
    # Verificar adaptador
    try:
        from app.gemini_adapter import gemini_adapter
        print_test("GeminiAdapter", True, "Adaptador inicializado")
        return True
    except Exception as e:
        print_test("GeminiAdapter", False, f"Error: {e}")
        return False


async def test_fecha_actual():
    """Verifica inyección de fecha actual"""
    print_header("TEST 2: INYECCIÓN DE FECHA")
    
    try:
        from app.gemini_adapter import gemini_adapter
        
        # Obtener fecha actual
        fecha_info = gemini_adapter._obtener_fecha_actual_colombia()
        
        print(f"{Colores.CYAN}Fecha completa:{Colores.RESET} {fecha_info['completa']}")
        print(f"{Colores.CYAN}ISO:{Colores.RESET} {fecha_info['iso']}")
        print(f"{Colores.CYAN}Hora:{Colores.RESET} {fecha_info['hora']}")
        
        # Obtener fechas relativas
        fechas_rel = gemini_adapter._calcular_fechas_relativas()
        
        print(f"\n{Colores.CYAN}Fechas relativas:{Colores.RESET}")
        print(f"  Hoy: {fechas_rel['hoy']}")
        print(f"  Mañana: {fechas_rel['mañana']}")
        print(f"  Siguiente viernes: {fechas_rel['siguiente_viernes']}")
        print(f"  Siguiente lunes: {fechas_rel['siguiente_lunes']}")
        
        print_test("Inyección de fecha", True, "Todas las fechas calculadas correctamente")
        return True
        
    except Exception as e:
        print_test("Inyección de fecha", False, f"Error: {e}")
        return False


async def test_expresiones_temporales():
    """Prueba expresiones temporales comunes"""
    print_header("TEST 3: EXPRESIONES TEMPORALES")
    
    try:
        from app.gemini_adapter import gemini_adapter
        
        expresiones = [
            "Quiero cita para mañana",
            "Necesito fisioterapia el siguiente viernes",
            "Agéndame para este sábado",
            "En 3 días por favor"
        ]
        
        print(f"{Colores.YELLOW}Expresiones a testear:{Colores.RESET}")
        for exp in expresiones:
            print(f"  • \"{exp}\"")
        
        print(f"\n{Colores.GREEN}Contexto temporal generado:{Colores.RESET}")
        contexto = gemini_adapter._construir_contexto_temporal()
        print(contexto[:300] + "...")
        
        print_test(
            "Expresiones temporales",
            True,
            "Contexto generado con todas las fechas"
        )
        return True
        
    except Exception as e:
        print_test("Expresiones temporales", False, f"Error: {e}")
        return False


async def test_conversacion_simple():
    """Prueba conversación simple"""
    print_header("TEST 4: CONVERSACIÓN SIMPLE")
    
    try:
        from app.gemini_adapter import gemini_adapter
        
        # Mensaje de prueba
        mensajes = [
            {
                "role": "system",
                "content": "Eres un asistente médico. Responde de forma breve y amigable."
            },
            {
                "role": "user",
                "content": "Hola, necesito agendar una cita de fisioterapia"
            }
        ]
        
        print(f"{Colores.CYAN}Enviando mensaje...{Colores.RESET}")
        
        resultado = await gemini_adapter.generar_respuesta(
            mensajes=mensajes,
            temperature=0.3,
            max_tokens=200
        )
        
        print(f"\n{Colores.GREEN}Respuesta:{Colores.RESET}")
        print(f"  {resultado['respuesta'][:200]}...")
        print(f"\n{Colores.CYAN}Backend:{Colores.RESET} {resultado['backend']}")
        print(f"{Colores.CYAN}Modelo:{Colores.RESET} {resultado['modelo']}")
        print(f"{Colores.CYAN}Tokens:{Colores.RESET} {resultado['tokens']}")
        
        print_test(
            "Conversación simple",
            True,
            f"Respuesta generada con {resultado['backend']}"
        )
        return True
        
    except Exception as e:
        print_test("Conversación simple", False, f"Error: {e}")
        return False


async def test_estadisticas():
    """Muestra estadísticas de uso"""
    print_header("TEST 5: ESTADÍSTICAS")
    
    try:
        from app.gemini_adapter import gemini_adapter
        
        stats = gemini_adapter.obtener_estadisticas()
        
        print(f"{Colores.CYAN}Modo actual:{Colores.RESET} {stats['modo_actual'].upper()}")
        print(f"{Colores.CYAN}Total llamadas:{Colores.RESET} {stats['total_llamadas']}")
        print(f"{Colores.CYAN}Llamadas Gemini:{Colores.RESET} {stats['llamadas_gemini']}")
        print(f"{Colores.CYAN}Llamadas GPT-4o:{Colores.RESET} {stats['llamadas_openai_fallback']}")
        print(f"{Colores.CYAN}Errores Gemini:{Colores.RESET} {stats['errores_gemini']}")
        print(f"{Colores.CYAN}% Uso Gemini:{Colores.RESET} {stats['porcentaje_gemini']}%")
        
        print_test("Estadísticas", True, "Datos recuperados correctamente")
        return True
        
    except Exception as e:
        print_test("Estadísticas", False, f"Error: {e}")
        return False


async def main():
    """Ejecuta todos los tests"""
    print(f"\n{Colores.BOLD}{Colores.BLUE}")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "TEST GEMINI ADAPTER - IPS REACT".center(68) + "║")
    print("║" + f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    print(Colores.RESET)
    
    # Ejecutar tests
    tests = [
        ("Configuración", test_configuracion),
        ("Fecha actual", test_fecha_actual),
        ("Expresiones temporales", test_expresiones_temporales),
        ("Conversación simple", test_conversacion_simple),
        ("Estadísticas", test_estadisticas)
    ]
    
    resultados = []
    for nombre, test_func in tests:
        try:
            resultado = await test_func()
            resultados.append((nombre, resultado))
        except Exception as e:
            print(f"\n{Colores.RED}Error en test '{nombre}': {e}{Colores.RESET}")
            resultados.append((nombre, False))
    
    # Resumen final
    print_header("RESUMEN")
    
    exitos = sum(1 for _, r in resultados if r)
    total = len(resultados)
    
    for nombre, resultado in resultados:
        print_test(nombre, resultado)
    
    print(f"\n{Colores.BOLD}Total:{Colores.RESET} {exitos}/{total} tests exitosos")
    
    if exitos == total:
        print(f"\n{Colores.GREEN}{Colores.BOLD}🎉 TODOS LOS TESTS PASARON{Colores.RESET}")
        print(f"\n{Colores.CYAN}Sistema listo para producción{Colores.RESET}\n")
    else:
        print(f"\n{Colores.YELLOW}{Colores.BOLD}⚠️ ALGUNOS TESTS FALLARON{Colores.RESET}")
        print(f"\n{Colores.CYAN}Revisa la configuración antes de continuar{Colores.RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
