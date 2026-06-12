# J.A.R.V.I.S. for Home Assistant

**Just A Rather Very Intelligent System** – Iron Man inspired voice assistant.

## Features
- 🎙️ Wake Word "Hey JARVIS" (browser-based, no extra hardware)
- 🤖 AI responses via OpenAI GPT-4o (optional) or local mode
- 🏠 Full Home Assistant device control via voice
- 🌐 Internet search & general knowledge
- 🔊 JARVIS voice via OpenAI TTS (optional) or browser TTS
- ⚡ Iron Man Arc Reactor animated UI
- 🎬 Boot sequence, wave animations, speaking visualizer

## Installation

1. GitHub Repo hinzufügen in HA → Add-on Store → Benutzerdefinierte Repositories
2. **JARVIS** installieren und starten

## Konfiguration

| Option | Beschreibung |
|---|---|
| `ha_token` | Long-Lived Access Token aus HA Profil |
| `openai_api_key` | OpenAI API Key (optional – für GPT-4o + Stimme) |
| `wake_word` | Wake Word (Standard: "hey jarvis") |
| `tts_voice` | OpenAI TTS Stimme: `onyx` (tief, männlich) empfohlen |
| `language` | Sprache: `de-DE` oder `en-US` |

## Ohne OpenAI API Key
Funktioniert auch ohne – dann:
- Lokale Befehlserkennung (Licht, Alarm, Status, Zeit)
- Browser Web Speech API für Sprachausgabe
- Kein Internet-Wissen

## Sprachbefehle (Beispiele)
- *"Hey JARVIS, Licht im Wohnzimmer einschalten"*
- *"Hey JARVIS, Alarm scharf schalten"*
- *"Hey JARVIS, wie spät ist es?"*
- *"Hey JARVIS, Status aller Geräte"*
- *"Auf Wiedersehen JARVIS"* → JARVIS verabschiedet sich mit *"Bin stets zu Diensten, Sir."*
