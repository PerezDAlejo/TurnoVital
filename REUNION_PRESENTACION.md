# Reunión de Progreso – Asistente de Agendamiento Inteligente

## 0. Datos Rápidos (Executive Snapshot)
Estado general: ✅ Base funcional interna | ⚠️ Integración externa pendiente (API Key Saludtools) | 🚀 Listo para acelerar apenas se destrabe credencial.

Valor ya creado:
- Motor conversacional estructurado listo para interpretar intención y datos clave del paciente.
- Cliente Saludtools alineado 100% a documentación oficial (eventType / actionType / body) listo para “encender” en cuanto haya credenciales.
- Arquitectura alternativa Serverless preparada para reducir costos operativos y escalar automáticamente.
- Esquema de datos ampliado (historial, auditoría, memoria conversacional, futura gestión de adjuntos) que evita refactorizaciones costosas después.
- Lógica de slots horarios y reglas de restricción (ej. fisioterapia) ya parametrizada.

Decisiones que buscamos hoy:
1. Autorización uso controlado de servicios de pago (OpenAI + AWS serverless bajo tope mensual sugerido).
2. Validación de alcance MVP y cronograma tentativo propuesto.
3. Aprobación de arquitectura serverless como camino base de despliegue.
4. Designación de punto(s) de contacto IPS para información operativa pendiente.

---

## 1. Objetivo de la Reunión
Presentar avances tangibles, explicar el bloqueo externo actual con transparencia, mostrar la evolución técnica pensada en eficiencia económica, y alinear próximos pasos con decisiones y datos que necesitamos de la IPS.

Mensaje clave: No hemos estado detenidos; transformamos la espera en inversión estratégica (arquitectura, robustez de datos y preparación de integración inmediata).

---

## 2. Recordatorio de la Necesidad / Problema Inicial
- Alto uso de tiempo administrativo para coordinar citas manualmente.
- Inconsistencia en captura de datos del paciente (riesgo de errores / re-trabajo).
- Necesidad de disponibilidad 24/7 para solicitudes básicas (consultas, creación, reprogramación, cancelación).
- Búsqueda de reducción de costos operativos y mejor experiencia paciente.

---

## 3. Línea de Tiempo (Mes 1)
| Semana | Hito Principal | Comentario |
|--------|----------------|------------|
| 1 | Diseño de flujo conversacional y estructura de intents | Definición de formato JSON de salida IA. |
| 2 | Cliente inicial Saludtools + pruebas mock | Pendiente sandbox funcional. |
| 3 | Acceso portal sandbox parcialmente; bloqueo API Key (“Ups…”) | Se escalan intentos; se documenta error. |
| 3–4 | Refactor cliente a estándar oficial + ampliación esquema DB | Previniendo retrabajo futuro. |
| 4 | Arquitectura serverless + módulos memoria y slots | Optimización costo + preparación escalabilidad. |

Nota: El retraso en credenciales es externo; el proyecto se mantuvo avanzando con cimientos sólidos.

---

## 4. Qué Ya Está Construido (Capacidades Tangibles)
1. Motor conversacional con salida estructurada (intención, datos de cita, confirmaciones).
2. Módulo de memoria conversacional (contexto multi-turnos, base para personalización futura).
3. Cliente Saludtools preparado (autenticación, eventos de citas/pacientes) adaptado a nomenclatura oficial.
4. Lógica de slots y agrupación de horarios (mañana, mediodía, tarde) con reglas de configuración.
5. Configuración de especialistas, tipos de cita y restricciones de servicios sensibles.
6. Esquema de base de datos extendido: historial de citas, auditoría de acciones, conversaciones, mensajes, adjuntos futuros.
7. Infraestructura serverless lista (plantilla SAM + adaptador Lambda) para despliegue económico.

---

## 5. Arquitectura: Actual vs Propuesta Serverless
| Aspecto | Servidor Tradicional | Serverless (Propuesto) | Beneficio Clave |
|---------|----------------------|------------------------|------------------|
| Costo Operativo | Pago continuo (24/7) | Pago por ejecución | Reducción de costos ociosos |
| Escalabilidad | Manual / dimensionar picos | Automática bajo demanda | Responde a picos sin sobrepago |
| Mantenimiento | Parches y uptime propio | Delegado (AWS) | Menos carga operativa |
| Riesgo Financiero Inicial | Mayor costo hundido | Coste incremental bajo | Ideal fase de validación |
| Time-to-Market | Configuración infra | Plantilla lista | Acelera salida |

Impacto esperado: Mayor sostenibilidad económica y facilidad para justificar ROI en fases tempranas.

---

## 6. Beneficios Estratégicos ya Asegurados
- Base de datos preparada para analítica y auditoría (evita “parches” futuros).
- Diseño modular: permite sustituir piezas (proveedor IA o motor de horarios) sin reescribir todo.
- Preparación para métricas clave: tiempo de agendamiento, abandono, exactitud de intención.
- Gobernanza de costos mediante arquitectura orientada a uso real (serverless) + límites de tokens IA.

---

## 7. Bloqueo Externo Actual (API Key Saludtools)
Situación: Portal devuelve error genérico al generar API Key.
Acciones realizadas: intentos múltiples, documentación de error, preparación de cliente y pruebas mock.
Listo para: Crear / reprogramar / cancelar cita real inmediatamente tras recibir credencial.
Mitigación adoptada: Avance en módulos internos + alineación estricto a especificación oficial (evita reproceso).

---

## 8. Próximo Camino una vez Llegue la API Key
1. Prueba de humo de autenticación y evento cita (día 0–1 post credencial).
2. Flujos CRUD de cita reales (crear, modificar, cancelar) con validaciones de negocio.
3. Registro de interacción conversacional vinculado a cita real.
4. Panel mínimo de métricas (log consolidado en base de datos).
5. Ajustes UX y pulido de prompts para reducción de ambigüedades.

---

## 9. Cronograma Tentativo (Sujeto a entrega de credencial)
| Semana (desde desbloqueo) | Hitos | Resultado Esperado |
|---------------------------|-------|--------------------|
| 1 | Autenticación + CRUD cita real | Flujo básico operativo end-to-end |
| 2 | Memoria + validaciones restricciones en vivo | Experiencia continua & reglas activas |
| 3 | Métricas y logging avanzado | Observabilidad inicial |
| 4 | Piloto interno controlado | Datos reales de uso temprano |
| 5 | Ajustes + optimizaciones IA / costos | Estabilización |
| 6 | Piloto ampliado (10–20 pacientes) | Validación de adopción |

Cadencia de reuniones propuesta:
- Semanal (15–20 min): Estado + bloqueos.
- Quincenal (30–40 min): Demo funcional e indicadores.
- Reunión especial Go/No-Go previo a ampliación piloto.

---

## 10. KPIs Propuestos (Fase MVP / Piloto)
- Tiempo medio de agendamiento conversacional (< 90s objetivo).
- % citas completadas sin intervención humana (> 70% a semana 6).
- Tasa de abandono conversación (< 15%).
- Exactitud clasificación de intención (> 90%).
- Ahorro estimado horas administrativas (baseline vs post piloto).
- Costo por 100 interacciones (monitoreo para control presupuestario).

---

## 11. Riesgos y Mitigaciones
| Riesgo | Impacto | Mitigación | Estado |
|--------|---------|-----------|--------|
| Demora adicional credencial | Retraso cronograma | Mock listo + priorizar paralelo (métricas, prompts) | Activo |
| Cambios de alcance tardíos | Re-trabajo | Congelar alcance MVP hoy | Controlable |
| Costos IA no monitoreados | Sobrepresupuesto | Límites tokens + logging consumo | Mitigado |
| Aceptación paciente baja | Menor ROI | Piloto iterativo + refinamiento prompts | En curso |

---

## 12. Decisiones / Autorizaciones Solicitadas Hoy
1. Presupuesto mensual inicial (sugerir tope) para OpenAI + AWS (ej. monto moderado escalable bajo aprobación).
2. Confirmación de alcance MVP (crear, reprogramar, cancelar, consultar cita, listado simple horarios).
3. Aprobación uso arquitectura serverless como estándar despliegue.
4. Nombrar responsable(s) IPS para información operativa y resolución expedita de dudas.
5. Alineación sobre KPIs a medir en piloto.

---

## 13. Información Operativa Aún Requerida de la IPS
- Horarios específicos por especialista (si difieren del general).
- Políticas de cancelación / reprogramación (ventanas mínimas, penalizaciones si existen).
- Lista oficial de tipos de cita y códigos internos.
- Reglas de prioridad (seguimiento, urgencias, first-visit vs control).
- Límites de capacidad por recurso físico (salas, equipos) si aplica.
- Mensajes legales / disclaimers o consentimientos requeridos.
- Baseline operacional: volumen diario actual, tiempo medio manual, tasa no-show.
- Canal y SLA deseado para incidencias (soporte técnico).

---

## 14. Próximas Acciones (Post-Reunión)
| Acción | Responsable | ETA |
|--------|-------------|-----|
| Entrega credencial válida / soporte API Key | Saludtools / IPS | ASAP |
| Validar alcance MVP y firmar acta breve | IPS + Desarrollo | 2 días |
| Ajustar configuración horarios finales | IPS | 3 días |
| Implementar CRUD real cita tras credencial | Desarrollo | Semana 1 |
| Configurar monitoreo costos IA | Desarrollo | Semana 2 |
| Preparar panel métricas inicial | Desarrollo | Semana 3 |

---

## 15. Cierre (Resumen en 3 Mensajes)
1. Avance sólido pese a bloqueo externo: base lista para “encender” integración real.
2. Arquitectura elegida maximiza eficiencia económica y escalabilidad desde inicio.
3. Con credencial y autorizaciones hoy, podemos llegar a piloto medible en ~6 semanas.

---

## 16. Apéndice: Argumento de Eficiencia (Serverless)
Pago estrictamente por solicitud procesada; permite correlacionar costo por cita agendada y proyectar ROI directamente (costo unitario = infra + tokens IA). Ajustes de prompts y caching potencial reducen consumo si crece el volumen.

---

## 17. Guion Breve de Presentación (Narrativa Oral)
1. “Iniciamos recordando el problema: tiempo administrativo y experiencia paciente mejorable.”
2. “Durante la espera de credenciales no nos detuvimos: construimos núcleo conversacional, datos robustos y optimizamos la futura estructura de costos.”
3. “La integración Saludtools está lista para activarse; el único elemento faltante es la API Key funcional.”
4. “Proponemos la arquitectura serverless para pagar sólo por uso y escalar sin fricción.”
5. “Tenemos hoja de ruta clara: en seis semanas desde el desbloqueo llegamos a piloto con métricas.”
6. “Solicitamos hoy las autorizaciones y datos operativos para acelerar sin más cuellos de botella.”
7. “Quedo atento a sus preguntas y a concretar las decisiones clave.”

---

## 18. Estilo Visual Sugerido para las Diapositivas
- Colores: Verde (progreso), Ámbar (bloqueo externo), Azul (decisiones), Gris claro (contexto).
- Cada slide con máximo 5–6 bullets, keywords en negrita.
- Incluir un diagrama simple (caja: WhatsApp → Bot Conversacional → API Saludtools → Base de Datos / Serverless Lambda).
- Usar íconos: reloj (cronograma), nube (serverless), candado (credencial), gráfico (KPIs).

---

## 19. Notas para la Exposición
- Tono: seguro, orientado a valor, sin entrar a código.
- Evitar tecnicismos innecesarios (decir “infraestructura que escala sola” en vez de detalles profundos AWS).
- Reforzar que cada semana se generó progreso reutilizable (no trabajo descartable).
- Preparar captura del error “Ups…” como evidencia si se pregunta por el bloqueo.

---

## 20. (Opcional) Presupuesto Referencial Inicial
Presentar en reunión si se solicita detalle (colocar valores reales cuando se confirmen):
- IA (OpenAI): tope X USD / mes MVP.
- AWS Lambda + API Gateway: estimado bajo volumen inicial (cifra base).
- Almacenamiento / Logs: marginal fase MVP.
Enfatizar: Ajustable dinámicamente, monitoreo quincenal.

---

¿Necesitas versión más corta (one-pager) o traducción ejecutiva? Puedo generarla después.
