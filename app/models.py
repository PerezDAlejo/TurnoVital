# app/models.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal
from datetime import datetime

class CitaRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre completo del paciente")
    documento: str = Field(..., pattern=r'^\d{6,15}$', description="Número de documento entre 6 y 15 dígitos")
    telefono: str = Field(..., pattern=r'^\d{10}$', description="Número de teléfono colombiano (10 dígitos)")
    email: EmailStr | None = None
    descripcion: str = Field(..., min_length=5, description="Motivo o tipo de cita o texto libre (usado para mapear tipo fisioterapia)")
    fecha_deseada: datetime
    preferencia_contacto: Literal['whatsapp', 'email'] = Field(..., description="Medio preferido para notificación")
    # Campos enriquecidos (opcionales) para nuevo flujo
    tipo_cita: Literal['PRIMERA VEZ', 'CONTROL', 'ACONDICIONAMIENTO'] | None = Field(None, description="Tipo canónico de cita")
    especialista: str | None = Field(None, description="Nombre de fisioterapeuta / especialista")
    franja: Literal['manana', 'mediodia', 'tarde'] | None = Field(None, description="Franja horaria preferida")
    plan_salud: Literal['prepago', 'particular'] | None = Field(None, description="Plan de salud (prepago/particular)")
    tiene_orden_medica: bool | None = Field(None, description="Indica si reporta tener orden médica")

    @field_validator('fecha_deseada')
    def validar_fecha(cls, v):
        if not v:
            raise ValueError("La fecha deseada es obligatoria")
        return v

class EditarCitaRequest(BaseModel):
    documento: str
    fecha_original: datetime
    nueva_fecha: datetime

class EliminarCitaRequest(BaseModel):
    documento: str
    fecha: datetime

class NotificacionRequest(BaseModel):
    documento: str
    mensaje: str
    medio: Literal['whatsapp', 'email']
    fecha_envio: datetime
