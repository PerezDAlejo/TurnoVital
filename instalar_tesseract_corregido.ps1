# Script para instalar Tesseract OCR en Windows
# Autor: IPS React Chatbot Team
# Fecha: Noviembre 2025

# Configuracion de ejecutor de PowerShell con permisos de administrador
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "ESTE SCRIPT REQUIERE PERMISOS DE ADMINISTRADOR" -ForegroundColor Red
    Write-Host "Relanzando con permisos de administrador..." -ForegroundColor Yellow
    Start-Process PowerShell -Verb RunAs "-NoProfile -ExecutionPolicy Bypass -Command `"cd '$pwd'; & '$PSCommandPath';`""
    exit
}

Write-Host "INSTALANDO TESSERACT OCR PARA WINDOWS" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green

# URL de descarga de Tesseract
$tesseractUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.3.20231005/tesseract-ocr-w64-setup-5.3.3.20231005.exe"
$installerPath = "$env:TEMP\tesseract-installer.exe"

Write-Host "Descargando Tesseract desde $tesseractUrl" -ForegroundColor Yellow

try {
    # Descargar Tesseract
    Invoke-WebRequest -Uri $tesseractUrl -OutFile $installerPath -ErrorAction Stop
    Write-Host "Descarga completada exitosamente" -ForegroundColor Green
    
    # Instalar Tesseract silenciosamente
    Write-Host "Instalando Tesseract OCR..." -ForegroundColor Yellow
    Start-Process -FilePath $installerPath -ArgumentList "/S" -Wait
    
    # Agregar Tesseract al PATH
    $tesseractPath = "C:\Program Files\Tesseract-OCR"
    
    if (Test-Path $tesseractPath) {
        Write-Host "Tesseract instalado exitosamente en $tesseractPath" -ForegroundColor Green
        
        # Agregar al PATH del sistema
        $currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
        if ($currentPath -notlike "*$tesseractPath*") {
            [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$tesseractPath", "Machine")
            Write-Host "Tesseract agregado al PATH del sistema" -ForegroundColor Green
        }
        
        # Verificar instalacion
        Write-Host "Verificando instalacion..." -ForegroundColor Yellow
        & "$tesseractPath\tesseract.exe" --version
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "TESSERACT INSTALADO EXITOSAMENTE" -ForegroundColor Green
            Write-Host "Reinicia tu terminal para que los cambios surtan efecto" -ForegroundColor Yellow
        } else {
            Write-Host "Error en la verificacion de Tesseract" -ForegroundColor Red
        }
    } else {
        Write-Host "Error: No se encontro Tesseract en la ruta esperada" -ForegroundColor Red
    }
    
    # Limpiar archivo temporal
    Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
    
} catch {
    Write-Host "Error durante la instalacion: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "INSTALACION COMPLETADA" -ForegroundColor Green
Write-Host "Presiona cualquier tecla para continuar..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")