#!/usr/bin/env python3
"""J.A.R.V.I.S. Home Assistant Add-on – Gemini Pro + Gemini TTS"""
import asyncio, json, logging, os, sys, base64, requests
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s [JARVIS] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("jarvis")

def load_config():
    p = "/data/options.json"
    if os.path.exists(p):
        cfg = json.load(open(p))
        log.info(f"Config geladen. Gemini: {'JA' if cfg.get('gemini_api_key') else 'NEIN'} | Modell: {cfg.get('gemini_model','?')}")
        return cfg
    return {"ha_token": os.environ.get("HA_TOKEN",""),
            "ha_url": os.environ.get("HA_URL","http://homeassistant:8123"),
            "gemini_api_key": os.environ.get("GEMINI_API_KEY",""),
            "gemini_model": "gemini-2.5-pro"}

CONFIG       = load_config()
SUPERVISOR   = os.environ.get("SUPERVISOR_TOKEN","")
USER_TOKEN   = CONFIG.get("ha_token","").strip()
USER_URL     = CONFIG.get("ha_url","http://homeassistant:8123").strip().rstrip("/")
GEMINI_KEY   = CONFIG.get("gemini_api_key","").strip()
GEMINI_MDL   = CONFIG.get("gemini_model","gemini-2.5-pro")
GEMINI_BASE  = "https://generativelanguage.googleapis.com/v1beta"

log.info(f"Gemini Key vorhanden: {'JA' if GEMINI_KEY else 'NEIN'} ({len(GEMINI_KEY)} Zeichen)")

def test_ha(base, token):
    """Teste ob eine HA-Verbindung funktioniert."""
    try:
        r = requests.get(f"{base}/api/", headers={"Authorization": f"Bearer {token}"}, timeout=5)
        return r.status_code == 200
    except Exception as e:
        log.info(f"  Test {base} fehlgeschlagen: {e}")
        return False

# Kandidaten in Prioritätsreihenfolge durchprobieren
CANDIDATES = []
if SUPERVISOR:
    CANDIDATES.append(("http://supervisor/core", SUPERVISOR, "Supervisor-Proxy"))
if USER_TOKEN:
    CANDIDATES.append((USER_URL, USER_TOKEN, "Benutzer-Token"))
    # Häufige interne URLs auch mit User-Token testen
    for alt in ["http://homeassistant:8123","http://homeassistant.local:8123",
                "http://172.30.32.1:8123","http://supervisor/core"]:
        if alt != USER_URL:
            CANDIDATES.append((alt, USER_TOKEN, f"Benutzer-Token @ {alt}"))

HA_BASE, HA_TOKEN = None, None
for base, token, label in CANDIDATES:
    log.info(f"Teste HA-Verbindung: {label} ({base})")
    if test_ha(base, token):
        HA_BASE, HA_TOKEN = base, token
        log.info(f"✓ HA verbunden über: {label} ({base})")
        break

if not HA_BASE:
    # Nichts hat funktioniert – nimm besten Kandidaten als Fallback
    if CANDIDATES:
        HA_BASE, HA_TOKEN = CANDIDATES[0][0], CANDIDATES[0][1]
        log.warning(f"⚠ Keine HA-Verbindung bestätigt. Nutze Fallback: {HA_BASE}")
    else:
        HA_BASE, HA_TOKEN = USER_URL, ""
        log.error("⚠ Kein HA-Token gefunden! Bitte ha_token eintragen ODER homeassistant_api nutzen.")

async def handle_index(req):
    with open("/usr/share/jarvis/index.html") as f:
        return web.Response(text=f.read(), content_type="text/html")

async def handle_startup_sound(req):
    path = "/usr/share/jarvis/startup.mp3"
    if os.path.exists(path):
        return web.Response(body=open(path,"rb").read(), content_type="audio/mpeg")
    return web.Response(status=404)

async def handle_startup_video(req):
    path = "/usr/share/jarvis/startup.mp4"
    if os.path.exists(path):
        return web.Response(body=open(path,"rb").read(), content_type="video/mp4")
    return web.Response(status=404)

async def handle_config(req):
    return web.json_response({
        "has_gemini":   bool(GEMINI_KEY),
        "gemini_model": GEMINI_MDL,
        "has_ha_token": bool(HA_TOKEN),
    })

async def handle_diag(req):
    """Diagnose-Endpunkt: zeigt Verbindungsstatus."""
    ha_ok = False
    ha_err = ""
    try:
        r = requests.get(f"{HA_BASE}/api/", headers={"Authorization": f"Bearer {HA_TOKEN}"}, timeout=5)
        ha_ok = r.status_code == 200
        ha_err = f"HTTP {r.status_code}"
    except Exception as e:
        ha_err = str(e)
    return web.json_response({
        "ha_base": HA_BASE,
        "ha_token_set": bool(HA_TOKEN),
        "ha_connection": ha_ok,
        "ha_error": ha_err,
        "supervisor_available": bool(SUPERVISOR),
        "gemini_set": bool(GEMINI_KEY),
        "gemini_model": GEMINI_MDL,
    })

async def handle_ha_proxy(req):
    path = req.match_info.get("path","")
    h = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type":"application/json"}
    try:
        if req.method == "GET":
            r = requests.get(f"{HA_BASE}/api/{path}", headers=h, timeout=8)
        else:
            body = await req.json()
            r = requests.post(f"{HA_BASE}/api/{path}", headers=h, json=body, timeout=8)
            log.info(f"HA {req.method} /api/{path} → {r.status_code} | body={body}")
        if r.status_code >= 400:
            log.warning(f"HA Fehler {r.status_code} bei /api/{path}: {r.text[:200]}")
        return web.Response(text=r.text, content_type="application/json", status=r.status_code)
    except Exception as e:
        log.error(f"HA Proxy Fehler bei /api/{path}: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def handle_gemini(req):
    """Chat completion via Gemini Pro."""
    if not GEMINI_KEY:
        return web.json_response({"error":"Kein Gemini API-Key"}, status=400)
    try:
        body = await req.json()
        url  = f"{GEMINI_BASE}/models/{GEMINI_MDL}:generateContent?key={GEMINI_KEY}"
        r    = requests.post(url, json=body, timeout=30)
        return web.Response(text=r.text, content_type="application/json", status=r.status_code)
    except Exception as e:
        log.error(f"Gemini Fehler: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def main():
    app = web.Application(client_max_size=15*1024*1024)
    app.router.add_get("/",                  handle_index)
    app.router.add_get("/api/config",        handle_config)
    app.router.add_get("/api/diag",          handle_diag)
    app.router.add_get("/api/startup_sound", handle_startup_sound)
    app.router.add_get("/api/startup_video", handle_startup_video)
    app.router.add_get("/api/ha/{path:.*}",  handle_ha_proxy)
    app.router.add_post("/api/ha/{path:.*}", handle_ha_proxy)
    app.router.add_post("/api/gemini",       handle_gemini)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8766).start()
    log.info(f"J.A.R.V.I.S. läuft auf :8766 | Modell {GEMINI_MDL}")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
