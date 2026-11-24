"""
audio/tts_speaker.py
====================
Text-to-speech output with a simple FIFO queue.
Supported engines:
  - edge-tts   (online, default – low latency, high quality)
  - piper      (offline – install separately)
  - none       (silent mode)

The speaker runs its own daemon thread and respects a mute flag.
"""

from __future__ import annotations

import asyncio
import io
import logging
import queue
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_SENTINEL = None   # signals the worker to stop


class TTSSpeaker:
    """
    Queues text strings and speaks them in order.

    Usage::

        speaker = TTSSpeaker()
        speaker.start()
        speaker.speak("Hola, soy KAI.")
        speaker.stop()
    """

    def __init__(self) -> None:
        from config.settings import settings
        from core.event_bus import bus

        self._settings = settings
        self._bus = bus
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._muted = not settings.tts_enabled
        self._thread: Optional[threading.Thread] = None

        # Listen for mute toggle
        bus.subscribe("on_tts_mute", self._on_mute)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="tts-speaker"
        )
        self._thread.start()
        logger.info("TTSSpeaker started (engine=%s)", self._settings.tts_engine)

    def stop(self) -> None:
        self._queue.put(_SENTINEL)
        if self._thread:
            self._thread.join(timeout=5.0)

    def speak(self, text: str) -> None:
        """Enqueue *text* for speech synthesis."""
        if text:
            self._queue.put(text)

    def clear(self) -> None:
        """Discard all pending speech."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_mute(self, muted: bool, **_) -> None:
        self._muted = muted

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _worker(self) -> None:
        while True:
            text = self._queue.get()
            if text is _SENTINEL:
                break
            if self._muted:
                logger.debug("TTS muted – skipping: %s", text[:50])
                continue
            try:
                self._bus.emit("on_tts_start", text=text)
                self._synthesize(text)
                self._bus.emit("on_tts_done")
            except Exception:
                logger.exception("TTS synthesis failed for: %s", text[:80])

    def _synthesize(self, text: str) -> None:
        engine = self._settings.tts_engine.lower()
        if engine == "edge-tts":
            self._edge_tts(text)
        elif engine == "piper":
            self._piper_tts(text)
        else:
            logger.debug("TTS engine 'none' – silent")

    # ------------------------------------------------------------------
    # edge-tts (async, run in a fresh event loop in this thread)
    # ------------------------------------------------------------------

    def _edge_tts(self, text: str) -> None:
        try:
            import edge_tts
            import sounddevice as sd
            import soundfile as sf
        except ImportError:
            logger.error("edge-tts or sounddevice not installed")
            return

        voice = self._settings.tts_voice

        async def _run():
            communicate = edge_tts.Communicate(text, voice)
            audio_buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buf.write(chunk["data"])
            audio_buf.seek(0)
            return audio_buf

        loop = asyncio.new_event_loop()
        try:
            audio_buf = loop.run_until_complete(_run())
        finally:
            loop.close()

        # Play via soundfile + sounddevice
        audio_buf.seek(0)
        try:
            data, samplerate = sf.read(audio_buf, dtype="float32")
            sd.play(data, samplerate)
            sd.wait()
        except Exception:
            logger.exception("Audio playback failed")

    # ------------------------------------------------------------------
    # piper TTS (optional, offline)
    # ------------------------------------------------------------------

    def _piper_tts(self, text: str) -> None:
        try:
            import subprocess
            result = subprocess.run(
                ["piper", "--output-raw"],
                input=text.encode(),
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                import sounddevice as sd
                import numpy as np
                audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
                sd.play(audio, samplerate=22050)
                sd.wait()
            else:
                logger.error("Piper TTS failed: %s", result.stderr.decode())
        except FileNotFoundError:
            logger.error("'piper' executable not found in PATH")
        except Exception:
            logger.exception("Piper TTS error")
