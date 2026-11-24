# KAI – AI Desktop Assistant

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" />
  <img src="https://img.shields.io/badge/PyQt6-6.7-green?logo=qt" />
  <img src="https://img.shields.io/badge/Ollama-local--first-purple" />
  <img src="https://img.shields.io/badge/Windows-10%2F11-blue?logo=windows" />
  <img src="https://img.shields.io/badge/license-MIT-orange" />
</p>

**KAI** is a modular, lightweight AI desktop assistant with a floating animated island UI, offline-first voice control and real Windows automation — all running locally by default.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🏝 **Animated island UI** | Frameless, transparent, always-on-top window anchored at the top of the screen. 60 FPS eye animation with natural blink, smooth pupil tracking and state-driven expressions. |
| 🗣 **Voice pipeline** | Passive wake-word detection ("KAI") via Vosk + VAD-based recording + faster-whisper transcription — 100 % offline. |
| 🤖 **Hybrid AI** | Local-first via Ollama (e.g. `qwen2.5:3b`). Optional OpenAI-compatible fallback for `hybrid` / `online` modes. Strict JSON tool-calling with safe parser fallback. |
| 🗂 **Desktop organiser** | Categorises loose files, shows a preview, moves them and maintains a full undo history (no permanent deletion). |
| ⏱ **Pomodoro & timers** | Countdown timers and full Pomodoro cycles with visual + audio alerts. |
| 📈 **Habit tracker** | Logs daily habits, calculates streaks and triggers themed eye gestures. |
| 🚀 **App launcher** | Opens allow-listed apps and paths safely. |
| 🔇 **TTS** | edge-tts (default) or piper (optional offline) with mute toggle from the tray icon. |

---

## 🗂 Project structure

```
KAI/
├── main.py                # Entry point
├── config/
│   ├── settings.py        # Pydantic-settings config
│   └── tools_schema.json  # LLM tool definitions
├── core/
│   ├── event_bus.py       # Decoupled pub/sub events
│   ├── state_machine.py   # Mood/gesture state machine
│   └── logger.py          # Rotating file + rich console logging
├── ui/
│   ├── island_window.py   # Floating Qt island
│   ├── eye_renderer.py    # 60 FPS animated eyes
│   └── tray_menu.py       # System tray icon & menu
├── audio/
│   ├── wake_word.py       # Vosk wake-word listener
│   ├── stt_whisper.py     # faster-whisper VAD+STT
│   └── tts_speaker.py     # edge-tts / piper TTS
├── ai/
│   ├── llm_router.py      # Ollama + OpenAI hybrid router
│   ├── prompts.py         # System prompt & message builder
│   └── action_dispatcher.py # Tool routing & validation
├── actions/
│   ├── file_organizer.py  # Desktop scan, move, undo
│   ├── app_launcher.py    # Open apps & paths
│   ├── productivity.py    # Timers & Pomodoro
│   └── habits_tracker.py  # Habit log & streaks
├── storage/
│   ├── db.py              # SQLite connection + migrations
│   └── undo_history.json  # File-move undo log
└── tests/
    ├── test_file_organizer.py
    └── test_action_dispatcher.py
```

---

## 🚀 Quick start

### 1. Prerequisites

- Python 3.12 (Windows 10/11)
- [Ollama](https://ollama.com) installed and running
- Pull a model: `ollama pull qwen2.5:3b`

### 2. Install

```powershell
# Clone & enter the project
git clone https://github.com/santyt34/KAI-desk.git
cd KAI-desk

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure

```powershell
# Copy and edit the example env
Copy-Item .env.example .env
notepad .env
```

Key settings in `.env`:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5:3b` | Local Ollama model |
| `LLM_MODE` | `local` | `local` / `hybrid` / `online` |
| `WAKE_WORD` | `kai` | Wake-word to listen for |
| `WHISPER_MODEL` | `base` | STT model size (`tiny` / `base` / `small`) |
| `TTS_ENGINE` | `edge-tts` | Voice output engine |
| `ALLOWED_APPS` | `notepad,…` | Comma-separated app allow list |

### 4. Run

```powershell
# Full mode (voice + UI + AI)
python main.py

# Text-only mode (no mic needed)
python main.py --text

# Self-check / smoke test
python main.py --test

# Disable TTS
python main.py --no-tts

# Skip wake-word listener
python main.py --no-wake
```

---

## 🎙 Using KAI

| Method | How |
|---|---|
| **Voice** | Say "KAI" → KAI wakes, listens, responds |
| **Text** | Tray icon → *Type a command…* |
| **Sleep/Wake** | Double-click the island or tray → *Sleep / Wake* |
| **Mute TTS** | Tray icon → *Mute voice* |

### Example commands

```
"KAI, organiza mi escritorio"
"KAI, abre Notepad"
"KAI, ponme un temporizador de 25 minutos"
"KAI, inicia un Pomodoro"
"KAI, registra mi hábito de agua"
"KAI, ¿cuál es mi racha de ejercicio?"
"KAI, deshaz el último movimiento"
```

---

## 🧪 Tests

```powershell
pytest tests/ -v
```

---

## 🔧 Architecture notes

### Event flow

```
Mic ──► WakeWordDetector ──► bus("on_wake")
                                │
                                ▼
                          WhisperSTT.listen_once()
                                │
                          bus("on_transcript", text=…)
                                │
                          AIPipeline._process()
                           ├── LLMRouter.chat()      ← Ollama / OpenAI
                           └── ActionDispatcher.dispatch()
                                │
                          bus("on_response")
                           ├── TTSSpeaker.speak()
                           └── state_machine.transition(HAPPY)
                                │
                          IslandWindow ◄── bus("on_state_change")
```

### Adding a new tool

1. Add the tool definition to `config/tools_schema.json`.
2. Create an async handler and decorate it with `@register("tool_name")` in the appropriate `actions/*.py` module.
3. Import the module in `main.py` (the import triggers the decorator).

---

## 📦 Key dependencies

| Package | Purpose |
|---|---|
| `PyQt6` | UI framework |
| `faster-whisper` | Offline STT |
| `vosk` | Offline wake-word |
| `ollama` / `httpx` | Local LLM via Ollama REST API |
| `edge-tts` | Online TTS (low-latency) |
| `pydantic-settings` | Typed, validated config |
| `pywin32` | Windows system access |
| `rich` | Pretty console logging |

---

## 📄 License

MIT © 2024 — KAI-Desk contributors
