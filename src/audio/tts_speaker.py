"""
audio/tts_speaker.py
====================
Text-to-speech output with a FIFO queue for Troko-Desk.
Supported engines:
  - kokoro     (offline neural voice via ONNX)
  - edge-tts   (high quality online natural voices)
  - piper      (offline lightweight CLI)
  - none       (silent mode)

Transitions Troko's visual state to HABLA while speaking.
"""

from __future__ import annotations

import asyncio
import io
import logging
import queue
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_SENTINEL = None


class TTSSpeaker:
    def __init__(self) -> None:
        from config.settings import settings
        from core.event_bus import bus
        from core.state_machine import TrokoState, state_machine

        self._settings = settings
        self._bus = bus
        self._state_machine = state_machine
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._muted = not settings.tts_enabled
        self._thread: Optional[threading.Thread] = None

        bus.subscribe("on_tts_mute", self._on_mute)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._worker, daemon=True, name="tts-speaker")
        self._thread.start()
        logger.info("TTSSpeaker started (engine=%s)", self._settings.tts_engine)

    def stop(self) -> None:
        self._queue.put(_SENTINEL)
        if self._thread:
            self._thread.join(timeout=3.0)

    def speak(self, text: str) -> None:
        if text:
            self._queue.put(text)

    def clear(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _on_mute(self, muted: bool, **_) -> None:
        self._muted = muted

    def _worker(self) -> None:
        from core.state_machine import TrokoState

        while True:
            text = self._queue.get()
            if text is _SENTINEL:
                break
            if self._muted:
                continue

            try:
                self._bus.emit("on_tts_start", text=text)
                self._state_machine.transition(TrokoState.HABLA)
                self._synthesize(text)
                self._state_machine.transition(TrokoState.REPOSO)
                self._bus.emit("on_tts_done")
            except Exception:
                logger.exception("TTS synthesis failed for: %s", text[:60])
                self._state_machine.transition(TrokoState.REPOSO)

    def _synthesize(self, text: str) -> None:
        engine = self._settings.tts_engine.lower()
        if engine == "kokoro":
            if not self._kokoro_tts(text):
                # Fallback to edge-tts if kokoro is unavailable
                self._edge_tts(text)
        elif engine == "edge-tts":
            self._edge_tts(text)
        elif engine == "piper":
            self._piper_tts(text)
        else:
            logger.debug("TTS silent mode")

    def _kokoro_tts(self, text: str) -> bool:
        """Attempt Kokoro ONNX offline synthesis."""
        try:
            from kokoro_onnx import Kokoro
            import sounddevice as sd
            from pathlib import Path

            model_dir = Path(self._settings.kokoro_model_dir)
            model_path = model_dir / "kokoro-v0_19.onnx"
            voices_path = model_dir / "voices.json"

            if not model_path.exists():
                return False

            kokoro = Kokoro(str(model_path), str(voices_path))
            samples, sample_rate = kokoro.create(text, voice="af_sarah", speed=1.0, lang="es")
            sd.play(samples, sample_rate)
            sd.wait()
            return True
        except Exception as exc:
            logger.debug("Kokoro TTS not available: %s", exc)
            return False

    def _edge_tts(self, text: str) -> None:
        try:
            import edge_tts
            import sounddevice as sd
            import soundfile as sf
        except ImportError:
            logger.error("edge-tts / sounddevice / soundfile not installed")
            return

        voice = self._settings.tts_voice

        async def _run():
            communicate = edge_tts.Communicate(text, voice)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            buf.seek(0)
            return buf

        loop = asyncio.new_event_loop()
        try:
            audio_buf = loop.run_until_complete(_run())
        finally:
            loop.close()

        audio_buf.seek(0)
        try:
            data, samplerate = sf.read(audio_buf, dtype="float32")
            sd.play(data, samplerate)
            sd.wait()
        except Exception as exc:
            logger.error("Audio playback error: %s", exc)

    def _piper_tts(self, text: str) -> None:
        import subprocess
        try:
            result = subprocess.run(
                ["piper", "--output-raw"],
                input=text.encode(),
                capture_output=True,
                timeout=25,
            )
            if result.returncode == 0 and result.stdout:
                import sounddevice as sd
                import numpy as np
                audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
                sd.play(audio, samplerate=22050)
                sd.wait()
        except Exception as exc:
            logger.error("Piper TTS error: %s", exc)
