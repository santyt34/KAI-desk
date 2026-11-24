"""
core/state_machine.py
=====================
Troko's mood / gesture / operational state machine.
Drives procedural eye rendering, expressive overlays and habit scenes.
Transitions are posted through the EventBus so UI remains 100% decoupled.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Union

from core.event_bus import bus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# States Definition
# ---------------------------------------------------------------------------


class TrokoState(str, Enum):
    """
    Complete state catalog for Troko-Desk:
    - 7 Operational states
    - 12 Emotions
    - 15 Habit scenes
    - 1 Celebration scene
    """

    # --- 7 Operational States ----------------------------------------------
    REPOSO = "reposo"              # idle
    ESCUCHA = "escucha"            # listening
    PIENSA = "piensa"              # thinking
    HABLA = "habla"                # speaking
    ALERTA = "alerta"              # alert
    NOTIFICACION = "notificacion"  # notification badge
    SUENO = "sueno"                # sleeping

    # --- 12 Expressive Emotions --------------------------------------------
    CONTENTO = "contento"          # happy
    ENAMORADO = "enamorado"        # in love / heart eyes
    SORPRESA = "sorpresa"          # surprise / wide eyes
    ORGULLOSO = "orgulloso"        # proud
    GUINO = "guino"                # wink
    BOSTEZO = "bostezo"            # yawn
    MAREADO = "mareado"            # dizzy / spiral eyes
    TRISTE = "triste"              # sad
    ENFADADO = "enfadado"          # angry
    TIMIDO = "timido"              # shy / heavy blush
    CURIOSO = "curioso"            # curious / tilted gaze
    TRAVIESO = "travieso"          # mischievous

    # --- 15 Habit Scenes ---------------------------------------------------
    HABIT_POMODORO = "pomodoro"         # typing on laptop with countdown
    HABIT_AGUA = "agua"                 # drinking water glass 6/8
    HABIT_LECTURA = "lectura"           # turning pages of book
    HABIT_EJERCICIO = "ejercicio"       # lifting weights with sweat drops
    HABIT_MEDITACION = "meditacion"     # zen breathing sun
    HABIT_CAMINAR = "caminar"           # animated walking steps
    HABIT_ESTUDIO = "estudio"           # lightbulb idea glowing
    HABIT_DORMIR = "dormir_temprano"    # crescent moon & night stars
    HABIT_COMIDA = "comida_saludable"   # sparkling apple
    HABIT_POSTURA = "postura"           # spine alignment stretch
    HABIT_PAUSA_VISUAL = "pausa_visual" # 20-20-20 eye rest guide
    HABIT_AGRADECIMIENTO = "agradecimiento" # journal & quill writing
    HABIT_RESPIRACION = "respiracion"   # 4-4-4 breathing circle
    HABIT_LIMPIEZA = "limpieza"         # sparkling tidiness
    HABIT_DESCONEXION = "desconexion"   # screen off zen leaf

    # --- Celebration -------------------------------------------------------
    FESTEJO = "festejo"            # confetti victory explosion


# Backward compatibility aliases
KAIState = TrokoState

# Aliases map for flexible transitions (Spanish / English / short names)
_STATE_ALIASES: dict[str, TrokoState] = {
    # Operational
    "idle": TrokoState.REPOSO,
    "reposo": TrokoState.REPOSO,
    "listening": TrokoState.ESCUCHA,
    "escucha": TrokoState.ESCUCHA,
    "thinking": TrokoState.PIENSA,
    "piensa": TrokoState.PIENSA,
    "speaking": TrokoState.HABLA,
    "habla": TrokoState.HABLA,
    "alert": TrokoState.ALERTA,
    "alerta": TrokoState.ALERTA,
    "notification": TrokoState.NOTIFICACION,
    "notificacion": TrokoState.NOTIFICACION,
    "sleeping": TrokoState.SUENO,
    "sueno": TrokoState.SUENO,
    "sleep": TrokoState.SUENO,

    # 12 Emotions
    "happy": TrokoState.CONTENTO,
    "contento": TrokoState.CONTENTO,
    "in_love": TrokoState.ENAMORADO,
    "enamorado": TrokoState.ENAMORADO,
    "love": TrokoState.ENAMORADO,
    "surprise": TrokoState.SORPRESA,
    "sorpresa": TrokoState.SORPRESA,
    "proud": TrokoState.ORGULLOSO,
    "orgulloso": TrokoState.ORGULLOSO,
    "wink": TrokoState.GUINO,
    "guino": TrokoState.GUINO,
    "guiño": TrokoState.GUINO,
    "yawn": TrokoState.BOSTEZO,
    "bostezo": TrokoState.BOSTEZO,
    "dizzy": TrokoState.MAREADO,
    "mareado": TrokoState.MAREADO,
    "sad": TrokoState.TRISTE,
    "triste": TrokoState.TRISTE,
    "angry": TrokoState.ENFADADO,
    "enfadado": TrokoState.ENFADADO,
    "enojado": TrokoState.ENFADADO,
    "shy": TrokoState.TIMIDO,
    "timido": TrokoState.TIMIDO,
    "tímido": TrokoState.TIMIDO,
    "curious": TrokoState.CURIOSO,
    "curioso": TrokoState.CURIOSO,
    "mischievous": TrokoState.TRAVIESO,
    "travieso": TrokoState.TRAVIESO,

    # Habits
    "hydration": TrokoState.HABIT_AGUA,
    "water": TrokoState.HABIT_AGUA,
    "workout": TrokoState.HABIT_EJERCICIO,
    "reading": TrokoState.HABIT_LECTURA,
    "meditation": TrokoState.HABIT_MEDITACION,
    "focus": TrokoState.HABIT_POMODORO,
    "celebration": TrokoState.FESTEJO,
}

# Auto return to REPOSO (seconds)
_AUTO_RETURN_SECONDS: dict[TrokoState, float] = {
    TrokoState.ESCUCHA: 30.0,
    TrokoState.PIENSA: 60.0,
    TrokoState.HABLA: 20.0,
    TrokoState.ALERTA: 8.0,
    TrokoState.NOTIFICACION: 5.0,
    TrokoState.SUENO: 0,           # Manual wake
    TrokoState.CONTENTO: 4.0,
    TrokoState.ENAMORADO: 5.0,
    TrokoState.SORPRESA: 4.0,
    TrokoState.ORGULLOSO: 5.0,
    TrokoState.GUINO: 3.5,
    TrokoState.BOSTEZO: 4.5,
    TrokoState.MAREADO: 5.0,
    TrokoState.TRISTE: 5.0,
    TrokoState.ENFADADO: 4.5,
    TrokoState.TIMIDO: 5.0,
    TrokoState.CURIOSO: 4.5,
    TrokoState.TRAVIESO: 4.5,
    TrokoState.FESTEJO: 7.0,

    # Habits stay for interaction unless dismissed or auto 8s
    TrokoState.HABIT_POMODORO: 0,  # Managed by pomodoro loop
    TrokoState.HABIT_AGUA: 12.0,
    TrokoState.HABIT_LECTURA: 10.0,
    TrokoState.HABIT_EJERCICIO: 10.0,
    TrokoState.HABIT_MEDITACION: 12.0,
}


@dataclass
class StateMachine:
    """Thread-safe state machine for Troko."""

    _current: TrokoState = field(default=TrokoState.REPOSO, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _return_timer: Optional[threading.Timer] = field(default=None, init=False)
    _sleep_start_time: Optional[datetime] = field(default=None, init=False)

    @property
    def current(self) -> TrokoState:
        with self._lock:
            return self._current

    @property
    def sleep_start_time(self) -> Optional[datetime]:
        with self._lock:
            return self._sleep_start_time

    def transition(self, target: Union[TrokoState, str], force: bool = False, **meta) -> bool:
        """
        Transition to a new state. Accepts enum or string (auto-normalized).
        """
        if isinstance(target, str):
            key = target.lower().strip()
            new_state = _STATE_ALIASES.get(key)
            if new_state is None:
                try:
                    new_state = TrokoState(key)
                except ValueError:
                    logger.warning("Unknown state target: %s", target)
                    return False
        else:
            new_state = target

        with self._lock:
            if self._current == new_state and not force:
                return False

            old_state = self._current
            self._current = new_state

            if self._return_timer is not None:
                self._return_timer.cancel()
                self._return_timer = None

            # Track sleep duration for wake reports
            if new_state == TrokoState.SUENO:
                self._sleep_start_time = datetime.now()
            elif old_state == TrokoState.SUENO and new_state != TrokoState.SUENO:
                sleep_start = self._sleep_start_time
                self._sleep_start_time = None
                if sleep_start:
                    bus.emit("on_wake_from_sleep", started=sleep_start.isoformat())

            duration = _AUTO_RETURN_SECONDS.get(new_state, 6.0 if "habit" in str(new_state) else 0)
            if duration > 0:
                self._return_timer = threading.Timer(duration, self._auto_return)
                self._return_timer.daemon = True
                self._return_timer.start()

        logger.debug("State transition: %s → %s", old_state.value, new_state.value)
        bus.emit("on_state_change", state=new_state.value, previous=old_state.value, **meta)
        return True

    def _auto_return(self) -> None:
        with self._lock:
            if self._current not in (TrokoState.REPOSO, TrokoState.SUENO, TrokoState.HABIT_POMODORO):
                self._current = TrokoState.REPOSO
                self._return_timer = None
        logger.debug("State: auto-return → reposo")
        bus.emit("on_state_change", state=TrokoState.REPOSO.value, previous="auto")

    def sleep(self) -> None:
        self.transition(TrokoState.SUENO)

    def wake(self) -> None:
        self.transition(TrokoState.REPOSO)

    def feedback(self, text: str = "Listo", success: bool = True) -> None:
        """Trigger a brief checkmark or notification feedback badge."""
        bus.emit("on_feedback_badge", text=text, success=success)
        self.transition(TrokoState.NOTIFICACION)


state_machine = StateMachine()
