"""
src/actions/emotions.py
=======================
Handles explicit emotion and gesture requests for KAI.
Supports all 12 parametric emotions:
1. Contento (feliz, happy)
2. Enamorado (love, amor)
3. Sorpresa (surprise, wow)
4. Orgulloso (proud)
5. Guiño (wink)
6. Bostezo (yawn)
7. Molesto (enojado, enfadado, angry, annoyed)
8. Escucha (escuchando, listen, listening)
9. Mareado (dizzy, spiral)
10. Festejo (celebrar, party, celebration)
11. Saludo (hola, greet, hello)
12. Ánimo (animo, cheer, vamos)
"""

from __future__ import annotations

import logging
from ai.action_dispatcher import register
from core.state_machine import TrokoState, state_machine

logger = logging.getLogger(__name__)

EMOTION_NAMES: dict[str, TrokoState] = {
    # 1. Contento
    "contento": TrokoState.CONTENTO,
    "feliz": TrokoState.CONTENTO,
    "alegre": TrokoState.CONTENTO,
    "happy": TrokoState.CONTENTO,
    # 2. Enamorado
    "enamorado": TrokoState.ENAMORADO,
    "amor": TrokoState.ENAMORADO,
    "love": TrokoState.ENAMORADO,
    # 3. Sorpresa
    "sorpresa": TrokoState.SORPRESA,
    "sorprendido": TrokoState.SORPRESA,
    "surprise": TrokoState.SORPRESA,
    "wow": TrokoState.SORPRESA,
    # 4. Orgulloso
    "orgulloso": TrokoState.ORGULLOSO,
    "proud": TrokoState.ORGULLOSO,
    # 5. Guiño
    "guino": TrokoState.GUINO,
    "guiño": TrokoState.GUINO,
    "wink": TrokoState.GUINO,
    # 6. Bostezo
    "bostezo": TrokoState.BOSTEZO,
    "yawn": TrokoState.BOSTEZO,
    "cansado": TrokoState.BOSTEZO,
    # 7. Molesto
    "molesto": TrokoState.MOLESTO,
    "enojado": TrokoState.MOLESTO,
    "enfadado": TrokoState.MOLESTO,
    "angry": TrokoState.MOLESTO,
    "annoyed": TrokoState.MOLESTO,
    # 8. Escucha
    "escucha": TrokoState.ESCUCHA,
    "escuchando": TrokoState.ESCUCHA,
    "listen": TrokoState.ESCUCHA,
    "listening": TrokoState.ESCUCHA,
    # 9. Mareado
    "mareado": TrokoState.MAREADO,
    "dizzy": TrokoState.MAREADO,
    # 10. Festejo
    "festejo": TrokoState.FESTEJO,
    "celebrar": TrokoState.FESTEJO,
    "celebracion": TrokoState.FESTEJO,
    "party": TrokoState.FESTEJO,
    # 11. Saludo
    "saludo": TrokoState.SALUDO,
    "hola": TrokoState.SALUDO,
    "saludar": TrokoState.SALUDO,
    "greet": TrokoState.SALUDO,
    "hello": TrokoState.SALUDO,
    # 12. Ánimo
    "animo": TrokoState.ANIMO,
    "ánimo": TrokoState.ANIMO,
    "cheer": TrokoState.ANIMO,
    "vamos": TrokoState.ANIMO,
    "fuerza": TrokoState.ANIMO,
}


@register("set_emotion")
async def _action_set_emotion(args: dict) -> str:
    key = args.get("emotion", "contento").lower().strip()
    target_state = EMOTION_NAMES.get(key, TrokoState.CONTENTO)

    state_machine.transition(target_state)
    state_machine.feedback(key.capitalize(), success=True)
    return f"✨ Emoción activada: {target_state.value}"
