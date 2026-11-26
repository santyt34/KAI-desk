"""
actions/productivity.py
=======================
Countdown timers, Pomodoro cycles (25/5 min) and smart reminders.
Features:
- Live real-time countdown emitted to the island notch.
- Sound alerts on completion.
- Wake-up report that aggregates expired tasks/reminders during sleep.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ai.action_dispatcher import register
from config.settings import settings
from core.event_bus import bus
from core.state_machine import TrokoState, state_machine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sound Alert
# ---------------------------------------------------------------------------

def play_alert_sound() -> None:
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Countdown Timers
# ---------------------------------------------------------------------------

@dataclass
class _CountdownTimer:
    label: str
    total_seconds: int
    is_pomodoro: bool = False
    _stop: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: Optional[threading.Thread] = field(default=None, init=False)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"timer-{self.label}")
        self._thread.start()

    def cancel(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        remaining = self.total_seconds
        logger.info("Timer '%s' started (%ds)", self.label, remaining)

        while remaining > 0:
            if self._stop.is_set():
                logger.info("Timer '%s' cancelled", self.label)
                return

            if self.is_pomodoro:
                bus.emit("on_pomodoro_tick", seconds_left=remaining)

            time.sleep(1.0)
            remaining -= 1

        if self.is_pomodoro:
            bus.emit("on_pomodoro_tick", seconds_left=0)

        play_alert_sound()
        state_machine.transition(TrokoState.ALERTA)
        state_machine.feedback("¡Tiempo!", success=True)
        bus.emit("on_timer_done", label=self.label)


_active_timers: dict[str, _CountdownTimer] = {}
_timer_lock = threading.Lock()


def set_timer(minutes: int, label: str = "Temporizador") -> str:
    if minutes <= 0 or minutes > 240:
        raise ValueError("La duración debe estar entre 1 y 240 minutos.")

    with _timer_lock:
        if label in _active_timers:
            _active_timers[label].cancel()

        t = _CountdownTimer(label=label, total_seconds=minutes * 60, is_pomodoro=False)
        _active_timers[label] = t

    t.start()
    state_machine.feedback("Anotado", success=True)
    return f"⏱️ Temporizador '{label}' programado por {minutes} min."


def start_pomodoro() -> str:
    work_mins = settings.pomodoro_work_minutes
    break_mins = settings.pomodoro_break_minutes

    with _timer_lock:
        if "pomodoro" in _active_timers:
            _active_timers["pomodoro"].cancel()

        t = _CountdownTimer(label="pomodoro", total_seconds=work_mins * 60, is_pomodoro=True)
        _active_timers["pomodoro"] = t

    state_machine.transition(TrokoState.HABIT_POMODORO)
    state_machine.feedback("Enfoque 25m", success=True)
    t.start()
    return f"🍅 Pomodoro iniciado: {work_mins} min de enfoque y {break_mins} min de descanso."


# ---------------------------------------------------------------------------
# Wake-Up Report (Due Reminders During Sleep)
# ---------------------------------------------------------------------------

_expired_during_sleep: List[str] = []


def record_due_during_sleep(item: str) -> None:
    _expired_during_sleep.append(item)


def get_wake_report() -> str:
    global _expired_during_sleep
    if not _expired_during_sleep:
        return "☀️ ¡Buenos días! No hubo recordatorios pendientes mientras descansabas."

    report = "☀️ **Resumen al despertar:**\n" + "\n".join(f"- {item}" for item in _expired_during_sleep)
    _expired_during_sleep.clear()
    return report


def _on_wake_listener(started: str, **_) -> None:
    """When waking from sleep, announce overdue reminders."""
    report = get_wake_report()
    if "Resumen" in report:
        state_machine.transition(TrokoState.CONTENTO)
        bus.emit("on_response", text=report, action={"speech": "Hola, aquí tienes el resumen de lo que venció mientras dormías."})


bus.subscribe("on_wake_from_sleep", _on_wake_listener)


# ---------------------------------------------------------------------------
# Action Dispatcher Handlers
# ---------------------------------------------------------------------------

@register("set_timer")
async def _action_set_timer(args: dict) -> str:
    minutes = int(args.get("minutes", 25))
    label = args.get("label", "Temporizador")
    is_pomodoro = bool(args.get("pomodoro", False))

    if is_pomodoro or "pomodoro" in label.lower():
        return start_pomodoro()
    return set_timer(minutes, label)


@register("get_wake_report")
async def _action_wake_report(_args: dict) -> str:
    return get_wake_report()
