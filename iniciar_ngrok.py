#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🚀 NGROK LAUNCHER - IPS REACT
Inicia ngrok y muestra URL formateada para Twilio
"""

import subprocess
import time
import requests
import json
import sys
from datetime import datetime

# Colores
BLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BOLD = '\033[1m'
RESET = '\033[0m'

def print_header():
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}║{' '*68}║{RESET}")
    print(f"{BLUE}║{BOLD}{'🚀 NGROK LAUNCHER - IPS REACT'.center(68)}{RESET}{BLUE}║{RESET}")
    print(f"{BLUE}║{f'Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}'.center(68)}║{RESET}")
    print(f"{BLUE}║{' '*68}║{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

def get_ngrok_url():
    """Obtiene la URL pública de ngrok"""
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=2)
        data = response.json()
        
        if data.get("tunnels"):
            for tunnel in data["tunnels"]:
                if tunnel.get("proto") == "https":
                    return tunnel.get("public_url")
        return None
    except:
        return None

def print_instructions(url):
    """Imprime instrucciones con la URL"""
    webhook_url = f"{url}/webhook/twilio"
    
    print(f"\n{GREEN}{'='*70}{RESET}")
    print(f"{GREEN}║{' '*68}║{RESET}")
    print(f"{GREEN}║{BOLD}{'✅ NGROK ACTIVO - URL PÚBLICA GENERADA'.center(68)}{RESET}{GREEN}║{RESET}")
    print(f"{GREEN}║{' '*68}║{RESET}")
    print(f"{GREEN}{'='*70}{RESET}\n")
    
    print(f"{BOLD}📡 URL PÚBLICA:{RESET}")
    print(f"   {BLUE}{url}{RESET}\n")
    
    print(f"{BOLD}🔗 WEBHOOK PARA TWILIO:{RESET}")
    print(f"   {GREEN}{webhook_url}{RESET}\n")
    
    print(f"{YELLOW}{'─'*70}{RESET}\n")
    
    print(f"{BOLD}📋 PASOS PARA CONFIGURAR TWILIO:{RESET}\n")
    print(f"  1️⃣  Abre: {BLUE}https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn{RESET}")
    print(f"  2️⃣  Ve a: {YELLOW}Sandbox Settings{RESET}")
    print(f"  3️⃣  En {YELLOW}'When a message comes in'{RESET}, pega:")
    print(f"      {GREEN}{webhook_url}{RESET}")
    print(f"  4️⃣  Método: {YELLOW}POST{RESET}")
    print(f"  5️⃣  Click {GREEN}Save{RESET}\n")
    
    print(f"{YELLOW}{'─'*70}{RESET}\n")
    
    print(f"{BOLD}📱 PARA PROBAR:{RESET}\n")
    print(f"  • Envía mensaje a: {GREEN}+1 415 523 8886{RESET}")
    print(f"  • Código sandbox: {GREEN}join {YELLOW}<tu-codigo>{RESET}")
    print(f"  • Luego prueba: {BLUE}'Hola'{RESET}\n")
    
    print(f"{YELLOW}{'─'*70}{RESET}\n")
    
    print(f"{RED}⚠️  IMPORTANTE:{RESET}")
    print(f"  • Mantén esta ventana abierta mientras pruebes")
    print(f"  • Presiona {RED}Ctrl+C{RESET} para detener ngrok")
    print(f"  • El servidor debe estar corriendo en puerto 8000\n")
    
    print(f"{GREEN}{'='*70}{RESET}\n")

def main():
    print_header()
    
    print(f"{YELLOW}🔄 Iniciando ngrok en puerto 8000...{RESET}\n")
    
    # Iniciar ngrok en background
    try:
        process = subprocess.Popen(
            ["ngrok", "http", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except FileNotFoundError:
        print(f"{RED}❌ Error: ngrok no encontrado{RESET}")
        print(f"{YELLOW}💡 Instala ngrok desde: https://ngrok.com/download{RESET}\n")
        sys.exit(1)
    
    # Esperar a que ngrok esté listo
    print(f"{YELLOW}⏳ Esperando que ngrok inicie...{RESET}")
    
    max_attempts = 10
    for attempt in range(max_attempts):
        time.sleep(1)
        url = get_ngrok_url()
        
        if url:
            print(f"{GREEN}✅ Ngrok iniciado correctamente{RESET}")
            print_instructions(url)
            
            # Mantener el proceso vivo
            try:
                process.wait()
            except KeyboardInterrupt:
                print(f"\n\n{YELLOW}🛑 Deteniendo ngrok...{RESET}")
                process.terminate()
                print(f"{GREEN}✅ Ngrok detenido{RESET}\n")
                sys.exit(0)
            
            return
    
    print(f"{RED}❌ Error: No se pudo obtener URL de ngrok{RESET}")
    print(f"{YELLOW}💡 Verifica que el puerto 8000 esté disponible{RESET}\n")
    process.terminate()
    sys.exit(1)

if __name__ == "__main__":
    main()  