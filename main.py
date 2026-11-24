"""
main.py
=======
KAI-Desk – Entry point.

Modes:
  python main.py              → full mode (UI + voice + AI)
  python main.py --text       → text-only mode (no microphone required)
  python main.py --no-tts     → disable text-to-speech
  python main.py --no-wake    → skip wake-word listener (useful for testing)
  python main.py --test       → run a quick self-check and exit
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import threading
from typing import Optional

# ---------------------------------------------------------------------------
# Bootstrap: logging must be set up before importing other modules
# ---------------------------------------------------------------------------
from core.logger import setup_logging

setup_logging()

import logging

logger = logging.getLogger(__name__)

from config.settings import settings
from core.event_bus import bus
from core.state_machine import TrokoState, state_machine


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="KAI – Modular AI Desktop Assistant",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--text",     action="store_true", help="Text-input mode (no mic)")
    parser.add_argument("--no-tts",   action="store_true", help="Disable voice output")
    parser.add_argument("--no-wake",  action="store_true", help="Skip wake-word listener")
    parser.add_argument("--test",     action="store_true", help="Run self-check and exit")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Self-check / smoke test
# ---------------------------------------------------------------------------


def _run_self_check() -> None:
    logger.info("Running KAI self-check…")
    errors = []

    # 1. Settings
    try:
        assert settings.app_name in ("Troko", "KAI")
        logger.info("  ✓ Settings loaded (%s)", settings.app_name)
    except Exception as exc:
        errors.append(f"Settings: {exc}")

    # 2. EventBus
    try:
        received = []
        bus.subscribe("test_event", lambda **kw: received.append(kw))
        bus.emit("test_event", value=42)
        assert received == [{"value": 42}]
        bus.clear("test_event")
        logger.info("  ✓ EventBus working")
    except Exception as exc:
        errors.append(f"EventBus: {exc}")

    # 3. StateMachine
    try:
        state_machine.transition(TrokoState.ESCUCHA)
        assert state_machine.current == TrokoState.ESCUCHA
        state_machine.transition(TrokoState.REPOSO)
        logger.info("  ✓ StateMachine transitions OK")
    except Exception as exc:
        errors.append(f"StateMachine: {exc}")

    # 4. DB
    try:
        from storage.db import DB
        with DB() as db:
            db.execute("SELECT 1")
        logger.info("  ✓ SQLite DB OK")
    except Exception as exc:
        errors.append(f"DB: {exc}")

    # 5. ActionDispatcher
    try:
        from ai.action_dispatcher import ActionDispatcher
        async def _test():
            d = ActionDispatcher()
            r = await d.dispatch({"tool": "answer", "args": {"text": "ok"}, "speech": "ok"})
            assert r == "ok"
        asyncio.run(_test())
        logger.info("  ✓ ActionDispatcher OK")
    except Exception as exc:
        errors.append(f"ActionDispatcher: {exc}")

    if errors:
        logger.error("Self-check FAILED:")
        for e in errors:
            logger.error("  ✗ %s", e)
        sys.exit(1)
    else:
        logger.info("Self-check PASSED ✓")
        sys.exit(0)


# ---------------------------------------------------------------------------
# AI pipeline (runs in a background asyncio loop)
# ---------------------------------------------------------------------------


class AIPipeline:
    """
    Bridges the EventBus (synchronous) with the async LLM + dispatcher.
    Runs in its own thread with a dedicated event loop.
    """

    def __init__(self, speaker=None) -> None:
        from ai.action_dispatcher import ActionDispatcher
        from ai.llm_router import LLMRouter
        from ai.prompts import build_messages

        self._router = LLMRouter()
        self._dispatcher = ActionDispatcher()
        self._build_messages = build_messages
        self._speaker = speaker
        self._loop = asyncio.new_event_loop()
        self._history: list[dict] = []

        bus.subscribe("on_transcript", self._on_transcript)

    def start(self) -> None:
        t = threading.Thread(
            target=self._loop.run_forever, daemon=True, name="ai-loop"
        )
        t.start()
        logger.info("AIPipeline asyncio loop started")

    def _on_transcript(self, text: str, **_) -> None:
        """Called from EventBus (any thread) – schedules async processing."""
        asyncio.run_coroutine_threadsafe(self._process(text), self._loop)

    async def _process(self, text: str) -> None:
        logger.info("Processing: '%s'", text)
        state_machine.transition(KAIState.THINKING)

        messages = self._build_messages(text, history=self._history)
        action = await self._router.chat(messages)

        # Update conversation history
        self._history.append({"role": "user", "content": text})
        self._history.append({
            "role": "assistant",
            "content": action.get("speech", "")
        })
        # Keep history bounded
        if len(self._history) > 20:
            self._history = self._history[-20:]

        result = await self._dispatcher.dispatch(action)

        # Emit result to bus
        bus.emit("on_response", text=result, action=action)

        # Speak
        if self._speaker and result:
            self._speaker.speak(result)

        # Trigger friendly positive state
        state_machine.transition(TrokoState.CONTENTO)
        logger.info("Response: '%s'", result[:100])


# ---------------------------------------------------------------------------
# Text-input dialogue (for --text mode or tray menu)
# ---------------------------------------------------------------------------


def _make_text_input_fn(pipeline: AIPipeline):
    """Return a callable that opens a Qt input dialog."""
    def _open_dialog():
        from PyQt6.QtWidgets import QInputDialog, QApplication
        text, ok = QInputDialog.getText(
            None, "KAI", "¿En qué te puedo ayudar?"
        )
        if ok and text.strip():
            bus.emit("on_transcript", text=text.strip())
    return _open_dialog


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()

    if args.test:
        _run_self_check()
        return

    logger.info("=" * 60)
    logger.info("  KAI v%s – Starting up", settings.app_version)
    logger.info("  Mode: %s | TTS: %s | Wake: %s",
                "text" if args.text else "voice",
                "off" if args.no_tts else settings.tts_engine,
                "off" if args.no_wake else "on")
    logger.info("=" * 60)

    # Import action modules to trigger @register decorators
    import actions.app_launcher    # noqa: F401
    import actions.file_organizer  # noqa: F401
    import actions.habits_tracker  # noqa: F401
    import actions.productivity    # noqa: F401
    import actions.email_drafts    # noqa: F401
    import actions.emotions        # noqa: F401

    # --- Qt Application ---------------------------------------------------
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # --- TTS --------------------------------------------------------------
    speaker = None
    if not args.no_tts:
        from audio.tts_speaker import TTSSpeaker
        speaker = TTSSpeaker()
        speaker.start()

    # --- AI Pipeline ------------------------------------------------------
    pipeline = AIPipeline(speaker=speaker)
    pipeline.start()

    # --- UI ---------------------------------------------------------------
    from ui.island_window import IslandWindow
    island = IslandWindow()
    island.show()

    text_input_fn = _make_text_input_fn(pipeline)

    from ui.tray_menu import TrayMenu
    tray = TrayMenu(island_window=island, text_input_fn=text_input_fn)
    tray.show()

    # --- STT / Wake-word --------------------------------------------------
    stt = None
    if not args.text:
        from audio.stt_whisper import WhisperSTT

        def _load_model_bg():
            nonlocal stt
            stt = WhisperSTT()
            try:
                stt.load_model()
                logger.info("Whisper model ready")
            except Exception:
                logger.exception("Failed to load Whisper model")

        threading.Thread(target=_load_model_bg, daemon=True, name="model-loader").start()

    if not args.no_wake and not args.text:
        def _start_wake_when_ready():
            import time
            # Wait for model to load (max 60s)
            for _ in range(120):
                if stt is not None:
                    break
                time.sleep(0.5)
            try:
                from audio.wake_word import WakeWordDetector
                detector = WakeWordDetector()

                def _on_wake(**_):
                    if stt:
                        stt.listen_once()

                bus.subscribe("on_wake", _on_wake)
                detector.start()
            except Exception:
                logger.exception("Wake-word detector failed to start")

        threading.Thread(target=_start_wake_when_ready, daemon=True, name="wake-starter").start()
    elif args.text:
        # In text mode, Ctrl+Enter from tray opens dialog
        logger.info("Text mode: use the tray menu → 'Type a command…'")

    # --- Graceful shutdown ------------------------------------------------
    def _on_quit(**_):
        logger.info("Shutting down KAI…")
        if speaker:
            speaker.stop()
        app.quit()

    bus.subscribe("on_quit", _on_quit)

    logger.info("KAI ready. Waiting for '~%s~'…", settings.wake_word)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
