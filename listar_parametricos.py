#!/usr/bin/env python3
"""Utilidad para listar parámetros clave desde Saludtools (tipos documento, clínicas).

Ejecutar: python listar_parametricos.py
Requiere variables de entorno SALUDTOOLS_API_KEY / SALUDTOOLS_API_SECRET configuradas.
"""
import asyncio
from dotenv import load_dotenv
from app.saludtools import SaludtoolsAPI

load_dotenv()

async def main():
    client = SaludtoolsAPI(environment="testing")
    ok = await client.authenticate()
    if not ok:
        print("No se pudo autenticar")
        return
    tipos_doc = await client.obtener_tipos_documento()
    print("\n=== Tipos de Documento ===")
    for t in tipos_doc:
        print(t)
    clinicas = await client.obtener_clinicas()
    print("\n=== Clínicas ===")
    if not clinicas:
        print("(Vacío o endpoint no disponible)")
    for c in clinicas:
        print(c)

if __name__ == "__main__":
    asyncio.run(main())
