# One-Pager Ejecutivo – Asistente de Agendamiento Inteligente

## 1. Situación Actual
Base funcional interna lista (conversación, lógica de slots, esquema ampliado, cliente Saludtools adaptado). Único bloqueo externo: generación de API Key (error portal). Arquitectura serverless preparada para reducir costos y escalar bajo demanda.

## 2. Valor Generado Hasta Hoy
- Motor conversacional estructurado (intenciones + datos de cita).
- Cliente Saludtools refactorizado a especificación oficial (activación inmediata al recibir credencial).
- Arquitectura serverless (SAM + Lambda + API Gateway) lista.
- Esquema de datos ampliado: historial, auditoría, conversaciones, adjuntos futuros.
- Módulos de memoria conversacional y slots horarios parametrizados.
- Reglas de restricciones (ej. fisioterapia) incorporadas.

## 3. Beneficio Estratégico
Menor costo operativo (pago por uso), escalabilidad automática, base de datos preparada para métricas y auditoría, modularidad para ajustes futuros (IA, horarios, canales adicionales).

## 4. Camino Próximo (Post Credencial)
Semana 1: Autenticación y CRUD real de citas.
Semana 2: Memoria + validaciones en vivo.
Semana 3: Métricas y logging avanzado.
Semana 4: Piloto interno.
Semana 5: Ajustes / optimización costos.
Semana 6: Piloto ampliado (10–20 pacientes).

## 5. KPIs MVP
- < 90s tiempo medio agendamiento.
- > 70% citas sin intervención humana (semana 6).
- < 15% abandono.
- > 90% exactitud intención.
- Costo por 100 interacciones controlado y monitoreado.

## 6. Riesgo Principal
Demora credencial Saludtools. Mitigación: entorno mock y componentes listos; avance paralelo en métricas y prompts.

## 7. Decisiones Solicitadas Hoy
1. Autorización presupuesto controlado (OpenAI + AWS serverless).
2. Validar alcance MVP (crear, reprogramar, cancelar, consultar + horarios básicos).
3. Aprobar enfoque serverless como estándar.
4. Nombrar responsable IPS para insumos operativos.
5. Alinear KPIs finales a medir.

## 8. Información que Aún Requerimos
Horarios específicos por especialista, políticas de cancelación/reprogramación, códigos internos de tipos de cita, reglas de prioridad, límites de recursos, disclaimers legales, baseline (volumen diario, tiempo manual, no-show), canal de soporte y SLA.

## 9. Mensaje Final
Avance sólido pese a bloqueo externo. Cada componente ya construido reduce riesgo y costo futuro. Con credencial y autorizaciones hoy, piloto medible en ~6 semanas.

---
Contacto técnico: (tu nombre)
Fecha: (actualizar)
