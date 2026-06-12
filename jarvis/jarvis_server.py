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

async def handle_tts_engines(req):
    """Liste verfügbare TTS-Engines (Piper etc.) aus HA."""
    try:
        r = requests.get(f"{HA_BASE}/api/states", headers={"Authorization": f"Bearer {HA_TOKEN}"}, timeout=8)
        states = r.json()
        engines = []
        for s in states:
            eid = s["entity_id"]
            if eid.startswith("tts."):
                engines.append({
                    "entity_id": eid,
                    "name": s.get("attributes",{}).get("friendly_name", eid),
                })
        return web.json_response({"engines": engines})
    except Exception as e:
        log.error(f"TTS-Engines Fehler: {e}")
        return web.json_response({"engines": []})

async def handle_tts_speak(req):
    """
    Text via Piper (HA TTS) in Sprache wandeln.
    Nutzt tts.speak Service und gibt die Media-URL zurück.
    """
    try:
        body = await req.json()
        text   = body.get("text","")
        engine = body.get("engine","")     # z.B. tts.piper
        voice  = body.get("voice","")      # optionale Stimme
        if not engine:
            # Erste verfügbare TTS-Engine automatisch wählen
            r = requests.get(f"{HA_BASE}/api/states", headers={"Authorization": f"Bearer {HA_TOKEN}"}, timeout=8)
            for s in r.json():
                if s["entity_id"].startswith("tts."):
                    engine = s["entity_id"]; break
        if not engine:
            return web.json_response({"error":"Keine TTS-Engine gefunden"}, status=404)

        # tts.speak via HA - generiert Audio und gibt URL
        # Wir nutzen den älteren tts_get_url Ansatz für direkte Media-URL
        payload = {
            "engine_id": engine,
            "message": text,
        }
        if voice:
            payload["options"] = {"voice": voice}

        # API: POST /api/tts_get_url
        r = requests.post(f"{HA_BASE}/api/tts_get_url",
            headers={"Authorization": f"Bearer {HA_TOKEN}", "Content-Type":"application/json"},
            json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            url = data.get("url","")
            # Audio durch unseren Proxy laden (sonst CORS/Auth-Probleme)
            return web.json_response({"url": url, "path": data.get("path","")})
        log.warning(f"tts_get_url HTTP {r.status_code}: {r.text[:200]}")
        return web.json_response({"error": f"TTS HTTP {r.status_code}", "browser_fallback": True})
    except Exception as e:
        log.error(f"TTS-Speak Fehler: {e}")
        return web.json_response({"error": str(e), "browser_fallback": True})

async def handle_tts_audio(req):
    """Proxy für TTS-Audio-Dateien (umgeht Auth/CORS)."""
    try:
        path = req.query.get("path","")
        if not path:
            return web.Response(status=400)
        url = f"{HA_BASE}{path}" if path.startswith("/") else f"{HA_BASE}/{path}"
        r = requests.get(url, headers={"Authorization": f"Bearer {HA_TOKEN}"}, timeout=15)
        ct = r.headers.get("Content-Type","audio/mpeg")
        return web.Response(body=r.content, content_type=ct, status=r.status_code)
    except Exception as e:
        log.error(f"TTS-Audio Fehler: {e}")
        return web.Response(status=500)

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
    app.router.add_get("/api/tts_engines",   handle_tts_engines)
    app.router.add_post("/api/tts_speak",    handle_tts_speak)
    app.router.add_get("/api/tts_audio",     handle_tts_audio)
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
