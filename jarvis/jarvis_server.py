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
            "gemini_model": "gemini-2.5-pro",
            "voice_mode": "gemini_tts",
            "tts_voice": "Charon"}

CONFIG     = load_config()
HA_TOKEN   = CONFIG.get("ha_token","") or os.environ.get("SUPERVISOR_TOKEN","")
HA_URL     = CONFIG.get("ha_url","http://homeassistant:8123").rstrip("/")
GEMINI_KEY = CONFIG.get("gemini_api_key","")
GEMINI_MDL = CONFIG.get("gemini_model","gemini-2.5-pro")
VOICE_MODE = CONFIG.get("voice_mode","gemini_tts")     # gemini_tts | browser
TTS_VOICE  = CONFIG.get("tts_voice","Charon")          # Charon=tief, Orus, Enceladus
GEMINI_BASE= "https://generativelanguage.googleapis.com/v1beta"

async def handle_index(req):
    with open("/usr/share/jarvis/index.html") as f:
        return web.Response(text=f.read(), content_type="text/html")

async def handle_startup_sound(req):
    path = "/usr/share/jarvis/startup.mp3"
    if os.path.exists(path):
        return web.Response(body=open(path,"rb").read(), content_type="audio/mpeg")
    return web.Response(status=404)

async def handle_config(req):
    return web.json_response({
        "has_gemini":   bool(GEMINI_KEY),
        "gemini_model": GEMINI_MDL,
        "voice_mode":   VOICE_MODE,
        "tts_voice":    TTS_VOICE,
    })

async def handle_ha_proxy(req):
    try:
        path = req.match_info.get("path","")
        h = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type":"application/json"}
        if req.method == "GET":
            r = requests.get(f"{HA_URL}/api/{path}", headers=h, timeout=5)
        else:
            r = requests.post(f"{HA_URL}/api/{path}", headers=h, json=await req.json(), timeout=5)
        return web.Response(text=r.text, content_type="application/json", status=r.status_code)
    except Exception as e:
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

async def handle_tts(req):
    """
    JARVIS-Stimme via Gemini TTS.
    Nutzt gemini-2.5-flash-preview-tts mit tiefer, ruhiger Stimme +
    Stil-Prompt für den charakteristischen JARVIS-Ton.
    Liefert PCM-Audio das im Browser zu WAV verpackt wird.
    """
    if not GEMINI_KEY or VOICE_MODE == "browser":
        return web.json_response({"browser_tts": True})
    try:
        body = await req.json()
        text = body.get("text","")
        # Stil-Anweisung für JARVIS-Charakter: ruhig, präzise, britisch, leicht herablassend-höflich
        styled = (f"Say in a calm, composed, refined British accent with the measured, "
                  f"precise diction of a sophisticated AI butler, slightly lower pitch, "
                  f"unhurried and confident: {text}")
        payload = {
            "contents": [{"parts": [{"text": styled}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": TTS_VOICE}
                    }
                }
            }
        }
        url = f"{GEMINI_BASE}/models/gemini-2.5-flash-preview-tts:generateContent?key={GEMINI_KEY}"
        r   = requests.post(url, json=payload, timeout=30)
        if r.status_code != 200:
            log.warning(f"Gemini TTS HTTP {r.status_code}: {r.text[:200]} – fallback to browser")
            return web.json_response({"browser_tts": True})
        data = r.json()
        # Audio liegt base64-codiert (PCM 24kHz) in inlineData
        parts = data.get("candidates",[{}])[0].get("content",{}).get("parts",[])
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                return web.json_response({
                    "audio": inline["data"],
                    "mime":  inline.get("mimeType") or inline.get("mime_type","audio/pcm"),
                    "format":"pcm_l16_24000"
                })
        log.warning("Keine Audio-Daten in TTS-Antwort – fallback")
        return web.json_response({"browser_tts": True})
    except Exception as e:
        log.error(f"TTS Fehler: {e}")
        return web.json_response({"browser_tts": True})

async def main():
    app = web.Application(client_max_size=15*1024*1024)
    app.router.add_get("/",                  handle_index)
    app.router.add_get("/api/config",        handle_config)
    app.router.add_get("/api/startup_sound", handle_startup_sound)
    app.router.add_get("/api/ha/{path:.*}",  handle_ha_proxy)
    app.router.add_post("/api/ha/{path:.*}", handle_ha_proxy)
    app.router.add_post("/api/gemini",       handle_gemini)
    app.router.add_post("/api/tts",          handle_tts)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8766).start()
    log.info(f"J.A.R.V.I.S. läuft auf :8766 | Modell {GEMINI_MDL} | Stimme {TTS_VOICE} ({VOICE_MODE})")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
