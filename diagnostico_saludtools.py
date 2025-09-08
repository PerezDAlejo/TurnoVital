"""Script de diagnóstico para descubrir el esquema correcto de eventos PATIENT SEARCH y CREATE en Saludtools.

Estrategia:
1. Autenticar usando claves del entorno.
2. Probar variantes de SEARCH con diferentes estructuras de paginación y filtros.
3. Probar variantes de CREATE con diferentes campos obligatorios potenciales.
4. Registrar resultados en consola en formato tabla y JSON resumido.

Uso:
  python diagnostico_saludtools.py --documento 12345678 --nombre "Juan" --apellido "Perez"

Variables de entorno requeridas:
  SALUDTOOLS_API_KEY, SALUDTOOLS_API_SECRET, SALUDTOOLS_BASE_URL (opcional, default prod)
"""
from __future__ import annotations
import os, json, argparse, time, itertools, random
import requests
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

ENV = (os.getenv("SALUDTOOLS_ENVIRONMENT") or os.getenv("ENVIRONMENT") or "testing").lower()

def resolve_base_url():
    override = os.getenv("SALUDTOOLS_BASE_URL")
    if override:
        return override.rstrip('/')
    if ENV in {"testing","test","qa","sandbox"}:
        return "https://saludtools.qa.carecloud.com.co/integration"
    if ENV in {"prod","production","live"}:
        return "https://saludtools.carecloud.com.co/integration"
    return "https://saludtools.qa.carecloud.com.co/integration"

BASE_URL = resolve_base_url()
API_KEY = os.getenv("SALUDTOOLS_API_KEY")
API_SECRET = os.getenv("SALUDTOOLS_API_SECRET") or os.getenv("SALUDTOOLS_SECRET")

def auth(retries: int = 3, backoff: float = 1.5):
    url = f"{BASE_URL}/authenticate/apikey/v1/"
    last_error = None
    for attempt in range(1, retries+1):
        try:
            r = requests.post(url, json={"key": API_KEY, "secret": API_SECRET}, timeout=30)
            data = r.json() if r.content else {}
            if r.status_code == 200 and data.get("access_token"):
                return data.get("access_token")
            last_error = f"status={r.status_code} body={data}"
        except Exception as e:
            last_error = str(e)
        if attempt < retries:
            time.sleep(backoff * attempt)
    raise SystemExit(f"Fallo auth tras {retries} intentos: {last_error}")

def post_event(token: str, payload: dict):
    url = f"{BASE_URL}/sync/event/v1/"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
    t0 = time.time()
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    elapsed = round((time.time() - t0)*1000)
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:400]}
    return {
        "status": r.status_code,
        "elapsed_ms": elapsed,
        "body": body,
    }

def build_search_variants(doc: str, doc_type_id: int = 1):
    base_combo = [
        ("SEARCH", {"documentNumber": doc, "documentTypeId": doc_type_id}),
        ("SEARCH", {"documentNumber": doc, "documentTypeId": doc_type_id, "page": 0, "size": 10}),
        ("SEARCH", {"filters": {"documentNumber": doc, "documentTypeId": doc_type_id}}),
        ("SEARCH", {"filters": {"documentNumber": doc, "documentTypeId": doc_type_id}, "pagination": {"page":0,"size":10}}),
        ("SEARCH", {"patient": {"documentNumber": doc, "documentTypeId": doc_type_id}}),
        ("SEARCH", {"data": {"documentNumber": doc, "documentTypeId": doc_type_id}}),
        ("SEARCH", {"data": {"filters": {"documentNumber": doc, "documentTypeId": doc_type_id}}}),
    ]
    # actionTypes alternativos sobre primera y tercera variante
    alt_actions = ["QUERY", "FIND", "GET", "LIST"]
    for alt in alt_actions:
        base_combo.append((alt, {"documentNumber": doc, "documentTypeId": doc_type_id}))
        base_combo.append((alt, {"filters": {"documentNumber": doc, "documentTypeId": doc_type_id}}))
    # Convertir a payloads
    variants = []
    for action, body in base_combo:
        variants.append({"eventType": "PATIENT", "actionType": action, "body": body})
    return variants

SEARCH_VARIANTS_DYNAMIC = True

CREATE_CORE = [
    ("documentNumber", lambda a: a.documento),
    ("documentTypeId",  lambda a: 1),
    ("firstName", lambda a: a.nombre),
    ("lastName", lambda a: a.apellido),
]

CREATE_OPTIONAL_FIELDS = [
    ("phoneNumber", lambda a: a.telefono or "3000000000"),
    ("email", lambda a: a.email or "test@example.com"),
    ("gender", "M"),
    ("active", True),
]

def build_field_value(field, provider, args):
    if callable(provider):
        return provider(args)
    return provider

def generate_create_variants(args):
    base_direct = {k: fn(args) for k, fn in CREATE_CORE}
    option_items = list(CREATE_OPTIONAL_FIELDS)
    variants = []
    # direct minimal
    variants.append({"eventType":"PATIENT","actionType":"CREATE","body": base_direct})
    # direct with 1..2 optional fields
    for r in range(1,3):
        for combo in itertools.combinations(option_items, r):
            body = dict(base_direct)
            for field, prov in combo:
                body[field] = build_field_value(field, prov, args)
            variants.append({"eventType":"PATIENT","actionType":"CREATE","body": body})
    # patient wrapper
    variants.append({"eventType":"PATIENT","actionType":"CREATE","body": {"patient": base_direct}})
    # data wrapper
    variants.append({"eventType":"PATIENT","actionType":"CREATE","body": {"data": base_direct}})
    # data.patient wrapper
    variants.append({"eventType":"PATIENT","actionType":"CREATE","body": {"data": {"patient": base_direct}}})
    # actionType alternativo REGISTER
    variants.append({"eventType":"PATIENT","actionType":"REGISTER","body": base_direct})
    return variants

def summarize(result):
    body = result["body"]
    msg = None
    if isinstance(body, dict):
        msg = body.get("message") or body.get("error") or body.get("detail")
    return msg or "(sin mensaje)"

def run(args):
    if not API_KEY or not API_SECRET:
        raise SystemExit("Faltan SALUDTOOLS_API_KEY / SALUDTOOLS_API_SECRET en entorno")
    token = auth()
    print(f"Auth OK (env={ENV}), token parcial: {token[:12]}...\n")

    print("== SEARCH Variants (2da ronda) ==")
    search_results = []
    variants_search = build_search_variants(args.documento)
    for idx, payload in enumerate(variants_search, 1):
        res = post_event(token, payload)
        search_results.append({"idx": idx, "payload": payload, **res})
        print(f"[{idx}] {payload['actionType']} keys={list(payload['body'].keys())} status={res['status']} msg={summarize(res)!r}")
        if res["status"] == 200:
            print("  -> SUCCESS, deteniendo pruebas de SEARCH\n")
            break

    print("\n== CREATE Variants (2da ronda) ==")
    create_results = []
    for idx, payload in enumerate(generate_create_variants(args), 1):
        res = post_event(token, payload)
        create_results.append({"idx": idx, "payload": payload, **res})
        print(f"[{idx}] status={res['status']} msg={summarize(res)!r}")
        if res["status"] in (200, 201):
            print("  -> SUCCESS, deteniendo pruebas de CREATE\n")
            break

    summary = {
        "search": [
            {"idx": r["idx"], "status": r["status"], "msg": summarize(r), "keys_body": list(r["payload"].get("body", {}).keys())}
            for r in search_results
        ],
        "create": [
            {"idx": r["idx"], "status": r["status"], "msg": summarize(r), "keys_body": list(r["payload"].get("body", {}).keys())}
            for r in create_results
        ],
    }
    print("\n== JSON Summary ==")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnóstico de payloads Saludtools PATIENT")
    parser.add_argument("--documento", help="Número documento a usar (default random 99xxxxxx)")
    parser.add_argument("--nombre", default="Test")
    parser.add_argument("--apellido", default="Paciente")
    parser.add_argument("--telefono")
    parser.add_argument("--email")
    args = parser.parse_args()
    if not args.documento:
        args.documento = str(99000000 + random.randint(1000, 8999))
    run(args)
