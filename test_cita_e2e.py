import requests
import datetime

# Configura la URL de tu API local
API_URL = "http://127.0.0.1:8000"

def print_response(label, r):
    print(f"[TEST] {label}: {r.status_code} {r.text}")
    try:
        r.raise_for_status()
    except Exception as e:
        print(f"[ERROR] {label}: {e}")
        exit(1)

# Datos de prueba

documento = "999999999"
nombre = "Test User"
telefono = "3001234567"
email = "testuser@example.com"
descripcion = "Cita de prueba automatizada"
preferencia = "whatsapp"

# Fecha de cita: 2 horas en el futuro
fecha_deseada = (datetime.datetime.utcnow() + datetime.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")

# 1. Agendar cita
print("[TEST] Agendando cita...")
data = {
    "nombre": nombre,
    "documento": documento,
    "telefono": telefono,
    "email": email,
    "descripcion": descripcion,
    "fecha_deseada": fecha_deseada,
    "preferencia_contacto": preferencia
}
r = requests.post(f"{API_URL}/agendar", json=data)
print_response("Respuesta agendar", r)
assert r.status_code == 200, "Error al agendar cita"

# 2. Consultar cita
print("[TEST] Consultando cita...")
r = requests.get(f"{API_URL}/citas", params={"documento": documento})
print_response("Respuesta consultar", r)
assert r.status_code == 200, "Error al consultar cita"
assert descripcion in r.text, "La cita no aparece en la consulta"

# 3. Cancelar cita
print("[TEST] Cancelando cita...")
citas = r.json().get("citas", [])
fecha_cita = None
for c in citas:
    if c["descripcion"] == descripcion:
        fecha_cita = c["fecha"]
        break
assert fecha_cita, "No se encontró la cita para cancelar"

cancel_data = {"documento": documento, "fecha": fecha_cita}
r = requests.delete(f"{API_URL}/eliminar", json=cancel_data)
print_response("Respuesta cancelar", r)
assert r.status_code == 200, "Error al cancelar cita"

# 4. Verificar que la cita fue cancelada
print("[TEST] Verificando cancelación...")
r = requests.get(f"{API_URL}/citas", params={"documento": documento})
print_response("Respuesta post-cancelación", r)
assert descripcion not in r.text, "La cita aún aparece después de cancelar"

print("[TEST] Prueba de ciclo de cita exitosa ✅")
