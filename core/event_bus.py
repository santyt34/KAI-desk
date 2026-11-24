"""
core/event_bus.py
=================
Lightweight synchronous/async event bus for decoupled inter-module
communication.  Uses thread-safe callbacks so audio workers can emit events
that the UI thread consumes without direct coupling.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Type alias
_Handler = Callable[..., Any]


class EventBus:
    """
    Simple pub/sub bus.

    Usage::

        bus = EventBus()

        @bus.on("on_wake")
        def handle_wake():
            print("KAI woke up!")

        bus.emit("on_wake")
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[_Handler]] = defaultdict(list)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def on(self, event: str) -> Callable[[_Handler], _Handler]:
        """Decorator to register a handler for *event*."""

        def decorator(fn: _Handler) -> _Handler:
            self.subscribe(event, fn)
            return fn

        return decorator

    def subscribe(self, event: str, handler: _Handler) -> None:
        """Register *handler* to be called when *event* is emitted."""
        with self._lock:
            if handler not in self._handlers[event]:
                self._handlers[event].append(handler)
                logger.debug("EventBus: subscribed %s → %s", event, handler.__name__)

    def unsubscribe(self, event: str, handler: _Handler) -> None:
        """Remove *handler* from *event*."""
        with self._lock:
            handlers = self._handlers.get(event, [])
            if handler in handlers:
                handlers.remove(handler)

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    def emit(self, event: str, **kwargs: Any) -> None:
        """
        Call all handlers registered for *event* synchronously.
        Each handler receives **kwargs as keyword arguments.
        Exceptions in handlers are logged but do not propagate.
        """
        with self._lock:
            handlers = list(self._handlers.get(event, []))

        for handler in handlers:
            try:
                handler(**kwargs)
            except Exception:
                logger.exception(
                    "EventBus: unhandled exception in handler %s for event '%s'",
                    getattr(handler, "__name__", repr(handler)),
                    event,
                )

    async def emit_async(self, event: str, **kwargs: Any) -> None:
        """
        Async variant: awaits coroutine handlers, calls sync handlers normally.
        """
        with self._lock:
            handlers = list(self._handlers.get(event, []))

        for handler in handlers:
            try:
                result = handler(**kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception(
                    "EventBus: async handler %s raised for event '%s'",
                    getattr(handler, "__name__", repr(handler)),
                    event,
                )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def clear(self, event: str | None = None) -> None:
        """Remove all handlers for *event*, or all events if None."""
        with self._lock:
            if event is None:
                self._handlers.clear()
            else:
                self._handlers.pop(event, None)


# ---------------------------------------------------------------------------
# Predefined events (documentation only – bus accepts any string)
# ---------------------------------------------------------------------------
#
#  on_wake            → KAI wake-word detected          kwargs: {}
#  on_state_change    → UI state changed                kwargs: state=str
#  on_transcript      → STT finished                   kwargs: text=str
#  on_response        → LLM produced a response        kwargs: text=str, action=dict
#  on_timer_done      → Countdown/Pomodoro expired     kwargs: label=str
#  on_habit_logged    → Habit entry recorded           kwargs: habit=str, streak=int
#  on_tts_start       → TTS synthesis started          kwargs: text=str
#  on_tts_done        → TTS playback finished          kwargs: {}
#  on_error           → Any module error               kwargs: source=str, message=str
#  on_quit            → Application shutdown requested kwargs: {}
#
# ---------------------------------------------------------------------------

# Global singleton – import and use this everywhere
bus = EventBus()
