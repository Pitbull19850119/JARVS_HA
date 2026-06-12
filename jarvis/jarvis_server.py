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
GEMINI_KEY   = CONFIG.get("gemini_api_key","")
GEMINI_MDL   = CONFIG.get("gemini_model","gemini-2.5-pro")
GEMINI_BASE  = "https://generativelanguage.googleapis.com/v1beta"

# Determine which HA endpoint + token to use.
# Priority: user-supplied token (full access) → supervisor proxy (limited)
if USER_TOKEN:
    HA_BASE  = USER_URL
    HA_TOKEN = USER_TOKEN
    log.info(f"HA-Zugriff über benutzer-Token: {HA_BASE}")
elif SUPERVISOR:
    HA_BASE  = "http://supervisor/core"
    HA_TOKEN = SUPERVISOR
    log.info("HA-Zugriff über Supervisor-Proxy")
else:
    HA_BASE  = USER_URL
    HA_TOKEN = ""
    log.warning("Kein HA-Token! Bitte ha_token in den Add-on Optionen eintragen.")

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
