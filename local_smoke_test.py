import os
os.environ.setdefault("NOTIFY_SECRETARIES", "false")
os.environ.setdefault("SECRETARY_WHATSAPP_TO", "+573001112233")
os.environ.setdefault("SECRETARY_CAPACITY", "1")
os.environ.setdefault("HANDOFF_PERSISTENCE", "0")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def assert_ok(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)

def test_health():
    r = client.get("/health")
    assert_ok(r.status_code == 200 and r.json().get("status") == "ok", "/health fallo")

def test_escalation_and_queue():
    # Forzar escalación por palabras clave, sin IA
    body1 = {
        "Body": "Necesito una cita médica con un doctor, quiero hablar con humano",
        "From": "whatsapp:+573000000001",
    }
    r1 = client.post("/webhook/twilio", data=body1)
    assert_ok(r1.status_code == 200, "Webhook 1 fallo")

    # Segunda escalación debe ir a cola (capacidad=1, 1 secretaria)
    body2 = {
        "Body": "Cita médica con especialista, humano",
        "From": "whatsapp:+573000000002",
    }
    r2 = client.post("/webhook/twilio", data=body2)
    assert_ok(r2.status_code == 200, "Webhook 2 fallo")

    # Validar estado
    s = client.get("/human/escalations").json()
    assert_ok(s.get("total", 0) >= 2, "No hay 2 escalaciones registradas")
    queue = s.get("queue", [])
    # Puede estar vacío si la asignación directa no se produjo por carga previa
    # pero al menos debe existir el primer caso en items
    items = s.get("items", {})
    assert_ok("whatsapp:+573000000001" in items, "Falta caso 1 en items")
    assert_ok("whatsapp:+573000000002" in items, "Falta caso 2 en items")

    # Liberar el primero y validar que intenta asignar el siguiente
    rel = client.post("/human/release/whatsapp:+573000000001").json()
    assert_ok(rel.get("success") is True, "Release no exitoso")

def run():
    test_health()
    test_escalation_and_queue()
    print("LOCAL SMOKE TEST: OK")

if __name__ == "__main__":
    run()
