"""
actions/emotions.py
===================
Handles explicit emotion and gesture requests for Troko-Desk.
Supports all 12 parametric emotions:
contento, enamorado, sorpresa, orgulloso, guiño, bostezo,
mareado, triste, enfadado, timido, curioso, travieso.
"""

from __future__ import annotations

import logging

from ai.action_dispatcher import register
from core.state_machine import TrokoState, state_machine

logger = logging.getLogger(__name__)

EMOTION_NAMES: dict[str, TrokoState] = {
    "contento": TrokoState.CONTENTO,
    "feliz": TrokoState.CONTENTO,
    "happy": TrokoState.CONTENTO,
    "enamorado": TrokoState.ENAMORADO,
    "love": TrokoState.ENAMORADO,
    "sorpresa": TrokoState.SORPRESA,
    "surprise": TrokoState.SORPRESA,
    "orgulloso": TrokoState.ORGULLOSO,
    "proud": TrokoState.ORGULLOSO,
    "guino": TrokoState.GUINO,
    "guiño": TrokoState.GUINO,
    "wink": TrokoState.GUINO,
    "bostezo": TrokoState.BOSTEZO,
    "yawn": TrokoState.BOSTEZO,
    "mareado": TrokoState.MAREADO,
    "dizzy": TrokoState.MAREADO,
    "triste": TrokoState.TRISTE,
    "sad": TrokoState.TRISTE,
    "enfadado": TrokoState.ENFADADO,
    "angry": TrokoState.ENFADADO,
    "timido": TrokoState.TIMIDO,
    "shy": TrokoState.TIMIDO,
    "curioso": TrokoState.CURIOSO,
    "curious": TrokoState.CURIOSO,
    "travieso": TrokoState.TRAVIESO,
    "playful": TrokoState.TRAVIESO,
}


@register("set_emotion")
async def _action_set_emotion(args: dict) -> str:
    key = args.get("emotion", "contento").lower().strip()
    target_state = EMOTION_NAMES.get(key, TrokoState.CONTENTO)

    state_machine.transition(target_state)
    state_machine.feedback(key.capitalize(), success=True)
    return f"✨ Emoción activada: {target_state.value}"
