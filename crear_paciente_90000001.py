#!/usr/bin/env python3
import asyncio
from dotenv import load_dotenv
from app.saludtools import SaludtoolsAPI

load_dotenv()

async def main():
    client = SaludtoolsAPI(environment='testing')
    await client.authenticate()
    doc='90000001'
    paciente = await client.crear_paciente({
        'firstName':'Paciente',
        'lastName':'Prueba Uno',
        'documentType':1,
        'documentNumber':doc,
        'phone':'573000000001',
        'email':'paciente1@example.com'
    })
    print('CREAR', paciente)
    read = await client.buscar_paciente_por_documento(doc)
    print('READ', read)

if __name__ == '__main__':
    asyncio.run(main())
