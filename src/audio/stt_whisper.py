"""
audio/stt_whisper.py
====================
Voice-activity-detection (VAD) + transcription with faster-whisper.
Runs in a worker thread.  Publishes "on_transcript" on the EventBus when done.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

# --- VAD parameters -------------------------------------------------------
_SAMPLE_RATE    = 16_000
_BLOCK_SIZE     = 512          # frames per callback (~32 ms)
_SILENCE_THRESH = 0.0035       # Sensitive RMS threshold for laptop/headset mics
_SILENCE_SECS   = 1.1          # seconds of silence to end recording
_MAX_RECORD_SECS = 15          # safety cap
_PRE_BUFFER_BLOCKS = 12        # keep N blocks before speech starts


class WhisperSTT:
    """
    Records one utterance after being activated, transcribes it with
    faster-whisper and emits the result to the EventBus.

    Usage::

        stt = WhisperSTT()
        stt.load_model()          # call once at startup
        stt.listen_once()         # start recording (non-blocking)
    """

    def __init__(self) -> None:
        from config.settings import settings
        from core.event_bus import bus
        from core.state_machine import KAIState, state_machine

        self._settings = settings
        self._bus = bus
        self._state_machine = state_machine
        self._KAIState = KAIState

        self._model = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """Load faster-whisper model (blocking – call once at startup)."""
        from faster_whisper import WhisperModel

        device = self._settings.whisper_device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        logger.info(
            "Loading Whisper model '%s' on device '%s'…",
            self._settings.whisper_model,
            device,
        )
        compute = "float16" if device == "cuda" else "int8"
        self._model = WhisperModel(
            self._settings.whisper_model,
            device=device,
            compute_type=compute,
        )
        logger.info("Whisper model loaded")

    # ------------------------------------------------------------------
    # Recording + transcription
    # ------------------------------------------------------------------

    def listen_once(self) -> None:
        """
        Start a one-shot recording+transcription in a background thread.
        Result is emitted via EventBus "on_transcript".
        """
        if self._thread and self._thread.is_alive():
            logger.debug("STT already listening – ignoring duplicate request")
            return
        self._thread = threading.Thread(
            target=self._record_and_transcribe, daemon=True, name="stt-worker"
        )
        self._thread.start()

    def _record_and_transcribe(self) -> None:
        self._state_machine.transition(self._KAIState.LISTENING)
        try:
            audio = self._record_utterance()
            if audio is None or len(audio) == 0:
                logger.debug("No audio captured")
                self._state_machine.transition(self._KAIState.IDLE)
                return

            self._state_machine.transition(self._KAIState.THINKING)
            text = self._transcribe(audio)
            if text:
                logger.info("STT: '%s'", text)
                self._bus.emit("on_transcript", text=text)
            else:
                logger.debug("Empty transcript")
                self._state_machine.transition(self._KAIState.IDLE)
        except Exception:
            logger.exception("STT worker error")
            self._state_machine.transition(self._KAIState.IDLE)

    def _record_utterance(self) -> Optional[np.ndarray]:
        """Record until silence detected or max duration reached."""
        audio_q: queue.Queue[np.ndarray] = queue.Queue()
        pre_buffer = []

        def _cb(indata: np.ndarray, frames: int, time_info, status):
            chunk = indata[:, 0].copy()
            audio_q.put(chunk)

        recorded: list[np.ndarray] = []
        speech_started = False
        silence_start: Optional[float] = None
        start_time = time.monotonic()

        with sd.InputStream(
            samplerate=_SAMPLE_RATE,
            blocksize=_BLOCK_SIZE,
            channels=1,
            dtype="float32",
            callback=_cb,
        ):
            while True:
                try:
                    chunk = audio_q.get(timeout=0.1)
                except queue.Empty:
                    continue

                rms = float(np.sqrt(np.mean(chunk ** 2)))
                now = time.monotonic()

                if not speech_started:
                    pre_buffer.append(chunk)
                    if len(pre_buffer) > _PRE_BUFFER_BLOCKS:
                        pre_buffer.pop(0)
                    if rms > _SILENCE_THRESH:
                        speech_started = True
                        recorded.extend(pre_buffer)
                        pre_buffer.clear()
                        logger.debug("Speech detected (rms=%.4f)", rms)
                    elif now - start_time >= 5.0:
                        logger.debug("No speech detected within 5 seconds – returning to idle")
                        break
                else:
                    recorded.append(chunk)
                    if rms < _SILENCE_THRESH:
                        if silence_start is None:
                            silence_start = now
                        elif now - silence_start >= _SILENCE_SECS:
                            logger.debug("Silence detected – stopping recording")
                            break
                    else:
                        silence_start = None

                if now - start_time >= _MAX_RECORD_SECS:
                    logger.debug("Max recording duration reached")
                    break

        return np.concatenate(recorded) if recorded else None

    def _transcribe(self, audio: np.ndarray) -> str:
        if self._model is None:
            raise RuntimeError("Whisper model not loaded. Call load_model() first.")

        segments, _info = self._model.transcribe(
            audio,
            language=None,  # auto-detect
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
