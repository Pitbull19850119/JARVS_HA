# J.A.R.V.I.S. for Home Assistant

**Just A Rather Very Intelligent System** – Iron Man inspirierter Sprachassistent mit Gemini Pro.

## Features
- 🎙️ Push-to-Talk Mikrofon + Wake Word „Hey JARVIS"
- 🧠 Google **Gemini Pro** für intelligente Antworten & Internetwissen
- 🔊 **Gemini TTS** mit tiefer, britischer JARVIS-Stimme (Charon)
- 🏠 Volle Home Assistant Gerätesteuerung per Sprache
- ⚡ Iron Man Arc-Reactor UI mit Boot-Sequenz
- 🎵 Original Startup-Sound beim Hochfahren
- 🎬 Zuhör- und Sprech-Animationen wie im Film

## Installation
1. GitHub Repo in HA → Add-on Store → Benutzerdefinierte Repositories
2. **JARVIS** installieren und starten

## Konfiguration

| Option | Beschreibung | Empfehlung |
|---|---|---|
| `ha_token` | Long-Lived Access Token aus HA Profil | erforderlich |
| `gemini_api_key` | Google Gemini API Key (aistudio.google.com) | erforderlich für KI |
| `gemini_model` | KI-Modell | `gemini-2.5-pro` (beste Qualität) |
| `voice_mode` | `gemini_tts` = Film-Stimme, `browser` = einfach | `gemini_tts` |
| `tts_voice` | Stimme: **Charon** (tief), Orus, Enceladus | `Charon` |

### Gemini API Key holen (kostenlos)
1. **aistudio.google.com** → „Get API key"
2. Key kopieren → in Add-on Konfiguration bei `gemini_api_key`

## Stimmen-Optionen
- **Charon** – tief, ruhig, am nächsten am Film-JARVIS ✅
- **Orus** – fest, autoritär
- **Enceladus** – sanft, gehaucht
- **Browser-Modus** – wenn kein Key: tiefe System-Stimme (rate 0.88, pitch 0.7)

## Sprachbefehle
- „Hey JARVIS, Licht im Wohnzimmer einschalten"
- „Hey JARVIS, Alarm scharf schalten"
- „Hey JARVIS, wie wird das Wetter morgen?" (mit Gemini)
- „Auf Wiedersehen JARVIS" → „Bin stets zu Diensten, Sir."
