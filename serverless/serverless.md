# Arquitectura Serverless Propuesta

## Objetivo
Reducir costos y operación eliminando servidor persistente (EC2/Lightsail) y n8n, migrando a arquitectura totalmente gestionada en AWS.

## Componentes
- API Gateway (HTTP/REST) + Lambda (FastAPI via Mangum)
- Secrets en AWS SAM (Parameters) -> opcional mover a AWS Secrets Manager
- Supabase se mantiene inicialmente para simplicidad (pacientes, citas, logs)
- (Opcional) Step Functions para flujos conversacionales complejos / recordatorios
- CloudWatch Logs & Metrics para monitoreo
- EventBridge (futuro) para recordatorios de citas / notificaciones

## Ventajas
- Pago por uso (escala a cero)
- Sin mantenimiento de servidor
- Despliegue reproducible (infra como código)
- Fácil extensión con otros servicios AWS

## Trade-offs
- Cold starts (mitigable con provisioned concurrency)
- Límite duración Lambda (30s por default; subir a 60 si necesario)
- Conexiones persistentes (usar patrones de conexión lazy si migras a RDS)

## Flujo
Paciente -> WhatsApp -> Twilio Webhook -> API Gateway -> Lambda (FastAPI) -> Saludtools / Supabase -> Respuesta

## Migración Incremental
1. Añadir handler Lambda (Mangum) sin romper ejecución local
2. Empaquetar dependencias y desplegar con SAM
3. Apuntar webhook Twilio a endpoint API Gateway dev
4. Test sandbox Saludtools
5. Ajustar timeouts / logging / tracing
6. Promover a stage prod

## Próximos Pasos
- Añadir `serverless/handler.py` con envoltura Mangum
- Ajustar README para sección serverless
- Script de despliegue SAM
- (Opcional) Pipeline CI/CD

## Variables sensibles
Manejar como Parameters (SAM) o Secrets Manager: OPENAI_API_KEY, SALUDTOOLS_API_KEY, SALUDTOOLS_API_SECRET, TWILIO_AUTH_TOKEN, SUPABASE_KEY.

---
