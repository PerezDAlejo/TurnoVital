from app.config import mapear_tipo_fisioterapia

CASES = {
    "primera vez de valoracion": "PRIMERAVEZ",
    "Primera": "PRIMERAVEZ",
    "seguimiento de terapia": "CONTROL",
    "control": "CONTROL",
    "acondicionamiento fisico": "ACONDICIONAMIENTO",
    "fortalecimiento y ejercicio": "ACONDICIONAMIENTO",
    "hidroterapia de algo": "PRIMERAVEZ",  # forbidden fallback
    "neurologica": "PRIMERAVEZ",
    "texto ambiguo": "CONTROL",
}

def test_mapear_tipo_fisioterapia():
    for desc, esperado in CASES.items():
        assert mapear_tipo_fisioterapia(desc) == esperado, f"{desc} -> {mapear_tipo_fisioterapia(desc)} != {esperado}"

if __name__ == "__main__":
    test_mapear_tipo_fisioterapia()
    print("✅ test_mapear_tipo_fisioterapia: OK (" + str(len(CASES)) + " casos)")
