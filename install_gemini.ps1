# ================================================================
# INSTALADOR GEMINI 2.0 FLASH - IPS REACT
# ================================================================
# Script para instalar y configurar Gemini en el sistema

Write-Host "`n" -NoNewline
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  INSTALADOR GEMINI 2.0 FLASH - IPS REACT" -ForegroundColor Cyan  
Write-Host "================================================================" -NoNewline
Write-Host "`n"

# Verificar que estamos en el entorno virtual
if (-not $env:VIRTUAL_ENV) {
    Write-Host "[ERROR] No se detect\u00f3 entorno virtual activo" -ForegroundColor Red
    Write-Host "`nPor favor ejecuta primero:" -ForegroundColor Yellow
    Write-Host "  .venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host "`n"
    exit 1
}

Write-Host "[OK] Entorno virtual detectado: $env:VIRTUAL_ENV" -ForegroundColor Green
Write-Host "`n"

# Paso 1: Actualizar pip
Write-Host "[1/4] Actualizando pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] pip actualizado" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Fallo al actualizar pip" -ForegroundColor Red
    exit 1
}

# Paso 2: Instalar google-generativeai
Write-Host "`n[2/4] Instalando google-generativeai..." -ForegroundColor Cyan
pip install "google-generativeai>=0.3.0" --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] google-generativeai instalado" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Fallo al instalar google-generativeai" -ForegroundColor Red
    exit 1
}

# Paso 3: Verificar instalaci\u00f3n
Write-Host "`n[3/4] Verificando instalaci\u00f3n..." -ForegroundColor Cyan
python -c "import google.generativeai as genai; print('  [OK] Importaci\u00f3n exitosa')" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] M\u00f3dulo funcional" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Fallo al importar google.generativeai" -ForegroundColor Red
    exit 1
}

# Paso 4: Verificar configuraci\u00f3n .env
Write-Host "`n[4/4] Verificando configuraci\u00f3n .env..." -ForegroundColor Cyan
if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw
    
    if ($envContent -match "GEMINI_API_KEY=AIza") {
        Write-Host "  [OK] GEMINI_API_KEY configurada" -ForegroundColor Green
    } else {
        Write-Host "  [WARNING] GEMINI_API_KEY no encontrada en .env" -ForegroundColor Yellow
    }
    
    if ($envContent -match "USE_GEMINI=true") {
        Write-Host "  [OK] USE_GEMINI=true (Gemini activado)" -ForegroundColor Green
    } else {
        Write-Host "  [INFO] USE_GEMINI=false (Gemini desactivado)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [ERROR] Archivo .env no encontrado" -ForegroundColor Red
    exit 1
}

# Resumen final
Write-Host "`n" -NoNewline
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  INSTALACI\u00d3N COMPLETA" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "`n"

Write-Host "ARQUITECTURA H\u00cdBRIDA CONFIGURADA:" -ForegroundColor Cyan
Write-Host "  - Chat conversacional: Gemini 2.0 Flash" -ForegroundColor White
Write-Host "  - OCR \u00f3rdenes m\u00e9dicas: GPT-4o Vision" -ForegroundColor White
Write-Host "  - Sistema retry OCR: 3 intentos autom\u00e1ticos" -ForegroundColor White
Write-Host "`n"

Write-Host "COSTOS ESTIMADOS (2500 pacientes/mes):" -ForegroundColor Cyan
Write-Host "  - Chat (Gemini): $65,000 COP/mes" -ForegroundColor White
Write-Host "  - OCR (GPT-4o): $12,500 COP/mes" -ForegroundColor White
Write-Host "  - TOTAL: $77,500 COP/mes" -ForegroundColor Green
Write-Host "  - AHORRO vs GPT-4o puro: 88% ($572,500/mes)" -ForegroundColor Green
Write-Host "`n"

Write-Host "PR\u00d3XIMOS PASOS:" -ForegroundColor Cyan
Write-Host "  1. Ejecuta: " -NoNewline -ForegroundColor White
Write-Host "python test_gemini_adapter.py" -ForegroundColor Yellow
Write-Host "  2. Prueba el chatbot con im\u00e1genes reales" -ForegroundColor White
Write-Host "  3. Verifica sistema de reintentos OCR" -ForegroundColor White
Write-Host "`n"
