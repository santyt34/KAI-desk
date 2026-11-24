"""
core/state_machine.py
=====================
KAI's mood / gesture state machine.
States drive eye animations and UI expressions in eye_renderer.py.
Transitions are posted through the EventBus so the UI stays decoupled.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from core.event_bus import bus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------


class KAIState(str, Enum):
    """All possible mood/gesture states for KAI's eye interface."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    HAPPY = "happy"
    SLEEPING = "sleeping"
    ALERT = "alert"
    # Habit-related gestures
    POMODORO = "pomodoro"
    HYDRATION = "hydration"
    WORKOUT = "workout"


# ---------------------------------------------------------------------------
# Transition rules
# ---------------------------------------------------------------------------

# (from_state, to_state) → allowed?  None means wildcard.
# Keep permissive by default; add guards here if needed.
_ALWAYS_ALLOWED_TARGETS: set[KAIState] = {
    KAIState.IDLE,
    KAIState.ALERT,
}

# How long (seconds) to stay in a transient state before auto-returning to IDLE
_AUTO_RETURN_SECONDS: dict[KAIState, float] = {
    KAIState.LISTENING: 30.0,
    KAIState.THINKING: 60.0,
    KAIState.HAPPY: 4.0,
    KAIState.ALERT: 8.0,
    KAIState.POMODORO: 0,      # managed by productivity.py
    KAIState.HYDRATION: 6.0,
    KAIState.WORKOUT: 6.0,
}


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


@dataclass
class StateMachine:
    """
    Thread-safe state machine for KAI's visual state.

    Example::

        sm = StateMachine()
        sm.transition(KAIState.LISTENING)
        print(sm.current)  # KAIState.LISTENING
    """

    _current: KAIState = field(default=KAIState.IDLE, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _return_timer: Optional[threading.Timer] = field(default=None, init=False)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current(self) -> KAIState:
        """Current state (thread-safe read)."""
        with self._lock:
            return self._current

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def transition(self, new_state: KAIState, force: bool = False) -> bool:
        """
        Attempt to transition to *new_state*.

        Returns True if the transition happened, False if it was a no-op
        (same state) or blocked.
        """
        with self._lock:
            if self._current == new_state and not force:
                return False

            old_state = self._current
            self._current = new_state

            # Cancel any pending auto-return timer
            if self._return_timer is not None:
                self._return_timer.cancel()
                self._return_timer = None

            # Schedule auto-return for transient states
            duration = _AUTO_RETURN_SECONDS.get(new_state, 0)
            if duration > 0:
                self._return_timer = threading.Timer(
                    duration, self._auto_return
                )
                self._return_timer.daemon = True
                self._return_timer.start()

        logger.debug("State: %s → %s", old_state.value, new_state.value)
        bus.emit("on_state_change", state=new_state.value, previous=old_state.value)
        return True

    def _auto_return(self) -> None:
        """Called by the timer to return to IDLE after a transient state."""
        with self._lock:
            if self._current not in (KAIState.IDLE, KAIState.SLEEPING, KAIState.POMODORO):
                self._current = KAIState.IDLE
                timer_ref = self._return_timer
                self._return_timer = None
        logger.debug("State: auto-return → idle")
        bus.emit("on_state_change", state=KAIState.IDLE.value, previous="auto")

    def sleep(self) -> None:
        """Transition to SLEEPING (manual, no auto-return)."""
        with self._lock:
            if self._return_timer:
                self._return_timer.cancel()
                self._return_timer = None
            old = self._current
            self._current = KAIState.SLEEPING
        bus.emit("on_state_change", state=KAIState.SLEEPING.value, previous=old.value)

    def wake(self) -> None:
        """Wake from sleep back to IDLE."""
        self.transition(KAIState.IDLE)

    def __repr__(self) -> str:
        return f"<StateMachine state={self._current.value}>"


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

state_machine = StateMachine()
