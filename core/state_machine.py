"""
src/core/state_machine.py
=========================
KAI's mood, gesture and operational state machine.
Drives procedural eye rendering, expressive overlays and habit scenes.
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


class KAIState(str, Enum):
    """
    Catalog of states for KAI:
    - 7 Operational states
    - 12 Parametric emotions
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

    # English aliases for operational states
    IDLE = "reposo"
    LISTENING = "escucha"
    THINKING = "piensa"
    SPEAKING = "habla"
    ALERT = "alerta"
    NOTIFICATION = "notificacion"
    SLEEP = "sueno"

    # --- 12 Emotions -------------------------------------------------------
    CONTENTO = "contento"          # happy
    ENAMORADO = "enamorado"        # in love / hearts
    SORPRESA = "sorpresa"          # surprise / wide eyes
    ORGULLOSO = "orgulloso"        # proud
    GUINO = "guino"                # wink
    BOSTEZO = "bostezo"            # yawn
    MOLESTO = "molesto"            # annoyed / furrowed brow
    ESCUCHA_ACTIVA = "escucha"     # attentive listen
    MAREADO = "mareado"            # dizzy / spiral eyes
    FESTEJO = "festejo"            # celebration / confetti
    SALUDO = "saludo"              # greeting wave / spark
    ANIMO = "animo"                # encouraging cheer / glowing pulse

    # --- 15 Habit Scenes ---------------------------------------------------
    HABIT_POMODORO = "pomodoro"
    HABIT_AGUA = "agua"
    HABIT_LECTURA = "lectura"
    HABIT_EJERCICIO = "ejercicio"
    HABIT_MEDITACION = "meditacion"
    HABIT_CAMINAR = "caminar"
    HABIT_ESTUDIO = "estudio"
    HABIT_DORMIR = "dormir_temprano"
    HABIT_COMIDA = "comida_saludable"
    HABIT_POSTURA = "postura"
    HABIT_PAUSA_VISUAL = "pausa_visual"
    HABIT_AGRADECIMIENTO = "agradecimiento"
    HABIT_RESPIRACION = "respiracion"
    HABIT_LIMPIEZA = "limpieza"
    HABIT_DESCONEXION = "desconexion"


TrokoState = KAIState

_STATE_ALIASES: dict[str, KAIState] = {
    # Operational
    "idle": KAIState.REPOSO,
    "reposo": KAIState.REPOSO,
    "listening": KAIState.ESCUCHA,
    "escucha": KAIState.ESCUCHA,
    "thinking": KAIState.PIENSA,
    "piensa": KAIState.PIENSA,
    "speaking": KAIState.HABLA,
    "habla": KAIState.HABLA,
    "alert": KAIState.ALERTA,
    "alerta": KAIState.ALERTA,
    "notification": KAIState.NOTIFICACION,
    "notificacion": KAIState.NOTIFICACION,
    "sleeping": KAIState.SUENO,
    "sueno": KAIState.SUENO,
    "sleep": KAIState.SUENO,

    # 12 Emotions
    "happy": KAIState.CONTENTO,
    "contento": KAIState.CONTENTO,
    "feliz": KAIState.CONTENTO,
    "in_love": KAIState.ENAMORADO,
    "enamorado": KAIState.ENAMORADO,
    "love": KAIState.ENAMORADO,
    "surprise": KAIState.SORPRESA,
    "sorpresa": KAIState.SORPRESA,
    "proud": KAIState.ORGULLOSO,
    "orgulloso": KAIState.ORGULLOSO,
    "wink": KAIState.GUINO,
    "guino": KAIState.GUINO,
    "guiño": KAIState.GUINO,
    "yawn": KAIState.BOSTEZO,
    "bostezo": KAIState.BOSTEZO,
    "annoyed": KAIState.MOLESTO,
    "molesto": KAIState.MOLESTO,
    "enfadado": KAIState.MOLESTO,
    "enojado": KAIState.MOLESTO,
    "dizzy": KAIState.MAREADO,
    "mareado": KAIState.MAREADO,
    "celebration": KAIState.FESTEJO,
    "festejo": KAIState.FESTEJO,
    "saludo": KAIState.SALUDO,
    "greeting": KAIState.SALUDO,
    "hola": KAIState.SALUDO,
    "animo": KAIState.ANIMO,
    "ánimo": KAIState.ANIMO,
    "cheer": KAIState.ANIMO,
    "triste": KAIState.MOLESTO,
    "timido": KAIState.CONTENTO,
    "curioso": KAIState.ESCUCHA,
    "travieso": KAIState.GUINO,

    # Habits
    "hydration": KAIState.HABIT_AGUA,
    "water": KAIState.HABIT_AGUA,
    "workout": KAIState.HABIT_EJERCICIO,
    "reading": KAIState.HABIT_LECTURA,
    "meditation": KAIState.HABIT_MEDITACION,
    "focus": KAIState.HABIT_POMODORO,
}

_AUTO_RETURN_SECONDS: dict[KAIState, float] = {
    KAIState.ESCUCHA: 30.0,
    KAIState.PIENSA: 60.0,
    KAIState.HABLA: 20.0,
    KAIState.ALERTA: 8.0,
    KAIState.NOTIFICACION: 5.0,
    KAIState.SUENO: 0,
    KAIState.CONTENTO: 4.0,
    KAIState.ENAMORADO: 5.0,
    KAIState.SORPRESA: 4.0,
    KAIState.ORGULLOSO: 5.0,
    KAIState.GUINO: 3.5,
    KAIState.BOSTEZO: 4.5,
    KAIState.MOLESTO: 4.5,
    KAIState.MAREADO: 5.0,
    KAIState.FESTEJO: 7.0,
    KAIState.SALUDO: 4.0,
    KAIState.ANIMO: 5.0,

    KAIState.HABIT_POMODORO: 0,
    KAIState.HABIT_AGUA: 12.0,
    KAIState.HABIT_LECTURA: 10.0,
    KAIState.HABIT_EJERCICIO: 10.0,
    KAIState.HABIT_MEDITACION: 12.0,
}


@dataclass
class StateMachine:
    _current: KAIState = field(default=KAIState.REPOSO, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _return_timer: Optional[threading.Timer] = field(default=None, init=False)
    _sleep_start_time: Optional[datetime] = field(default=None, init=False)

    @property
    def current(self) -> KAIState:
        with self._lock:
            return self._current

    @property
    def sleep_start_time(self) -> Optional[datetime]:
        with self._lock:
            return self._sleep_start_time

    def transition(self, target: Union[KAIState, str], force: bool = False, **meta) -> bool:
        if isinstance(target, str):
            key = target.lower().strip()
            new_state = _STATE_ALIASES.get(key)
            if new_state is None:
                try:
                    new_state = KAIState(key)
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

            if new_state == KAIState.SUENO:
                self._sleep_start_time = datetime.now()
            elif old_state == KAIState.SUENO and new_state != KAIState.SUENO:
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
            if self._current not in (KAIState.REPOSO, KAIState.SUENO, KAIState.HABIT_POMODORO):
                self._current = KAIState.REPOSO
                self._return_timer = None
        logger.debug("State: auto-return → reposo")
        bus.emit("on_state_change", state=KAIState.REPOSO.value, previous="auto")

    def sleep(self) -> None:
        self.transition(KAIState.SUENO)

    def wake(self) -> None:
        self.transition(KAIState.REPOSO)

    def feedback(self, text: str = "Listo", success: bool = True) -> None:
        bus.emit("on_feedback_badge", text=text, success=success)
        self.transition(KAIState.NOTIFICACION)


state_machine = StateMachine()
