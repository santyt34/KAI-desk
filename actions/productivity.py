"""
actions/productivity.py
=======================
Countdown timers, Pomodoro cycles and reminders.
Timers run in daemon threads and emit EventBus events when done,
triggering KAI's alert animation and an optional sound.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from ai.action_dispatcher import register
from config.settings import settings
from core.event_bus import bus
from core.state_machine import KAIState, state_machine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Timer management
# ---------------------------------------------------------------------------

@dataclass
class _Timer:
    label: str
    minutes: int
    _stop: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"timer-{self.label}"
        )
        self._thread.start()

    def cancel(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        seconds = self.minutes * 60
        logger.info("Timer started: '%s' (%d min)", self.label, self.minutes)
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._stop.is_set():
                logger.info("Timer cancelled: '%s'", self.label)
                return
            time.sleep(0.5)
        logger.info("Timer done: '%s'", self.label)
        state_machine.transition(KAIState.ALERT)
        bus.emit("on_timer_done", label=self.label)
        _play_alert()


_active_timers: dict[str, _Timer] = {}
_timer_lock = threading.Lock()


def _play_alert() -> None:
    """Play a short system beep or sound file."""
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)  # type: ignore[attr-defined]
    except Exception:
        logger.debug("winsound not available for alert beep")


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def set_timer(minutes: int, label: str = "Timer") -> str:
    """Create and start a countdown timer."""
    if minutes <= 0:
        raise ValueError("La duración debe ser mayor a 0 minutos.")
    if minutes > 180:
        raise ValueError("El temporizador no puede ser mayor a 180 minutos.")

    with _timer_lock:
        if label in _active_timers:
            _active_timers[label].cancel()
        t = _Timer(label=label, minutes=minutes)
        _active_timers[label] = t

    t.start()
    return f"⏱ Temporizador '{label}' iniciado por {minutes} min."


def start_pomodoro() -> str:
    """Start a full Pomodoro work+break cycle."""
    work = settings.pomodoro_work_minutes
    brk = settings.pomodoro_break_minutes

    state_machine.transition(KAIState.POMODORO)

    def _cycle():
        logger.info("Pomodoro: work phase (%d min)", work)
        bus.emit("on_state_change", state=KAIState.POMODORO.value, previous="")
        time.sleep(work * 60)
        bus.emit("on_timer_done", label=f"🍅 ¡Pomodoro completado! Descansa {brk} min.")
        _play_alert()
        state_machine.transition(KAIState.ALERT)
        time.sleep(brk * 60)
        bus.emit("on_timer_done", label="Fin del descanso. ¡A trabajar!")
        state_machine.transition(KAIState.IDLE)

    threading.Thread(target=_cycle, daemon=True, name="pomodoro").start()
    return f"🍅 Pomodoro iniciado: {work} min trabajo, {brk} min descanso."


def cancel_timer(label: str = "Timer") -> str:
    with _timer_lock:
        t = _active_timers.pop(label, None)
    if t:
        t.cancel()
        return f"Temporizador '{label}' cancelado."
    return f"No hay temporizador activo con nombre '{label}'."


# ---------------------------------------------------------------------------
# Action dispatcher handlers
# ---------------------------------------------------------------------------

@register("set_timer")
async def _action_set_timer(args: dict) -> str:
    minutes: int = int(args.get("minutes", 0))
    label: str = args.get("label", "Timer")
    is_pomodoro: bool = args.get("pomodoro", False)

    if is_pomodoro:
        return start_pomodoro()
    return set_timer(minutes, label)
