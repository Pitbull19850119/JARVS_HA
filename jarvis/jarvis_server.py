#!/usr/bin/env python3
"""J.A.R.V.I.S. Home Assistant Add-on – Minimal server, all logic in browser"""
import asyncio, json, logging, os, sys, requests
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s [JARVIS] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("jarvis")

def load_config():
    p = "/data/options.json"
    if os.path.exists(p):
        cfg = json.load(open(p))
        log.info(f"Config loaded, HA URL: {cfg.get('ha_url','')}")
        return cfg
    return {"ha_token": os.environ.get("HA_TOKEN",""),
            "ha_url": os.environ.get("HA_URL","http://homeassistant:8123"),
            "openai_api_key": os.environ.get("OPENAI_API_KEY",""),
            "tts_voice": "onyx"}

CONFIG = load_config()

# Use supervisor token if no explicit token given
HA_TOKEN = CONFIG.get("ha_token","") or os.environ.get("SUPERVISOR_TOKEN","")
HA_URL   = CONFIG.get("ha_url","http://homeassistant:8123").rstrip("/")
OAI_KEY  = CONFIG.get("openai_api_key","")
TTS_VOICE= CONFIG.get("tts_voice","onyx")

async def handle_index(req):
    with open("/usr/share/jarvis/index.html") as f:
        return web.Response(text=f.read(), content_type="text/html")

async def handle_config(req):
    return web.json_response({
        "ha_url": HA_URL, "has_openai": bool(OAI_KEY),
        "tts_voice": TTS_VOICE
    })

async def handle_ha_proxy(req):
    """Proxy HA API calls to avoid CORS issues."""
    try:
        path = req.match_info.get("path","")
        headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type":"application/json"}
        if req.method == "GET":
            r = requests.get(f"{HA_URL}/api/{path}", headers=headers, timeout=5)
        else:
            body = await req.json()
            r = requests.post(f"{HA_URL}/api/{path}", headers=headers, json=body, timeout=5)
        return web.Response(text=r.text, content_type="application/json", status=r.status_code)
    except Exception as e:
        log.error(f"HA proxy error: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def handle_ai(req):
    """Proxy to OpenAI chat."""
    if not OAI_KEY:
        return web.json_response({"error": "no_key"}, status=400)
    try:
        body = await req.json()
        r = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OAI_KEY}", "Content-Type":"application/json"},
            json=body, timeout=20)
        return web.Response(text=r.text, content_type="application/json")
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_tts(req):
    """Proxy to OpenAI TTS, return base64 audio."""
    if not OAI_KEY:
        return web.json_response({"error": "no_key"}, status=400)
    try:
        import base64
        body = await req.json()
        r = requests.post("https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {OAI_KEY}", "Content-Type":"application/json"},
            json={"model":"tts-1","input":body.get("text",""),"voice":TTS_VOICE}, timeout=20)
        r.raise_for_status()
        return web.json_response({"audio": base64.b64encode(r.content).decode()})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def main():
    app = web.Application(client_max_size=10*1024*1024)
    app.router.add_get("/",          handle_index)
    app.router.add_get("/api/config",handle_config)
    app.router.add_get("/api/ha/{path:.*}",  handle_ha_proxy)
    app.router.add_post("/api/ha/{path:.*}", handle_ha_proxy)
    app.router.add_post("/api/ai",   handle_ai)
    app.router.add_post("/api/tts",  handle_tts)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8766).start()
    log.info("J.A.R.V.I.S. server running on :8766")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
