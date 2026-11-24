"""
audio/wake_word.py
==================
Passive wake-word detection running in a background daemon thread.
Default engine: Vosk (offline, free, no API key).
Optional: pvporcupine (Picovoice) if installed and key configured.

When the wake-word is detected the EventBus emits "on_wake".
"""

from __future__ import annotations

import json
import logging
import queue
import sys
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """
    Listens continuously on the default microphone for the wake-word
    configured in settings.wake_word.

    Usage::

        detector = WakeWordDetector()
        detector.start()
        # ... runs until detector.stop()
    """

    def __init__(self) -> None:
        from config.settings import settings
        from core.event_bus import bus

        self._wake_words = [
            settings.wake_word.lower(),
            getattr(settings, "wake_word_alias", "kai").lower(),
        ]
        self._bus = bus
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the wake-word listener in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("WakeWordDetector already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="wake-word-detector"
        )
        self._thread.start()
        logger.info("WakeWordDetector started (word='%s')", self._wake_word)

    def stop(self) -> None:
        """Signal the detector thread to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("WakeWordDetector stopped")

    # ------------------------------------------------------------------
    # Detection loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main detection loop – tries Vosk first, falls back to keyword search."""
        try:
            self._run_vosk()
        except ImportError:
            logger.warning("Vosk not available – wake-word detection disabled")
        except Exception:
            logger.exception("WakeWordDetector crashed")

    def _find_model_path(self) -> Optional[str]:
        from config.settings import settings

        # 1. Configured path
        if settings.vosk_model_path:
            p = Path(settings.vosk_model_path)
            if p.exists():
                return str(p)

        # 2. Search candidates (current dir, app dir, exe dir)
        search_dirs = [
            Path.cwd(),
            Path(__file__).parent.parent,
        ]
        if getattr(sys, "frozen", False):
            search_dirs.append(Path(sys.executable).parent)
            if hasattr(sys, "_MEIPASS"):
                search_dirs.append(Path(sys._MEIPASS))

        for base in search_dirs:
            # Check direct folders
            for candidate in base.glob("vosk-model*"):
                if candidate.is_dir():
                    return str(candidate)
            model_sub = base / "model"
            if model_sub.is_dir():
                return str(model_sub)

        return None

    def _run_vosk(self) -> None:
        import sounddevice as sd
        from vosk import KaldiRecognizer, Model, SetLogLevel

        SetLogLevel(-1)  # silence vosk's own logging

        model_path = self._find_model_path()
        try:
            if model_path:
                logger.info("Loading Vosk model from path: %s", model_path)
                model = Model(model_path=model_path)
            else:
                logger.info("Attempting to load Vosk model by language 'es' / 'en-us'")
                try:
                    model = Model(lang="es")
                except Exception:
                    model = Model(lang="en-us")
        except Exception as exc:
            logger.error(
                "Vosk model could not be loaded: %s. "
                "Ensure a vosk-model folder is placed in the project root.",
                exc,
            )
            return

        sample_rate = 16000
        rec = KaldiRecognizer(model, sample_rate)
        rec.SetWords(True)
        audio_queue: queue.Queue[bytes] = queue.Queue()

        def _callback(indata, frames, time_info, status):
            if status:
                logger.debug("sounddevice status: %s", status)
            audio_queue.put(bytes(indata))

        logger.info("Vosk wake-word listener ready (sample_rate=%d)", sample_rate)

        with sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=_callback,
        ):
            while not self._stop_event.is_set():
                try:
                    data = audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text: str = result.get("text", "").lower()
                    if any(w in text for w in self._wake_words):
                        logger.info("Wake-word detected in: '%s'", text)
                        self._bus.emit("on_wake")
                        # Drain queue to avoid stale audio reaching STT
                        while not audio_queue.empty():
                            audio_queue.get_nowait()
