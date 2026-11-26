"""
actions/habits_tracker.py
=========================
Tracking for 15 Daily Habit Styles with Streaks, Progress Targets,
and Visual Animated Scene Triggers in Troko-Desk.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, Optional

from ai.action_dispatcher import register
from core.event_bus import bus
from core.state_machine import TrokoState, state_machine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 15 Habit Styles Mapping & Daily Targets
# ---------------------------------------------------------------------------

HABIT_MAPPINGS: dict[str, TrokoState] = {
    # 1. Enfoque
    "pomodoro": TrokoState.HABIT_POMODORO,
    "enfoque": TrokoState.HABIT_POMODORO,
    "focus": TrokoState.HABIT_POMODORO,

    # 2. Agua
    "agua": TrokoState.HABIT_AGUA,
    "hydration": TrokoState.HABIT_AGUA,
    "water": TrokoState.HABIT_AGUA,

    # 3. Lectura
    "lectura": TrokoState.HABIT_LECTURA,
    "leer": TrokoState.HABIT_LECTURA,
    "reading": TrokoState.HABIT_LECTURA,

    # 4. Ejercicio
    "ejercicio": TrokoState.HABIT_EJERCICIO,
    "pesas": TrokoState.HABIT_EJERCICIO,
    "workout": TrokoState.HABIT_EJERCICIO,

    # 5. Meditación
    "meditacion": TrokoState.HABIT_MEDITACION,
    "meditación": TrokoState.HABIT_MEDITACION,
    "descanso": TrokoState.HABIT_MEDITACION,
    "zen": TrokoState.HABIT_MEDITACION,

    # 6. Caminar
    "caminar": TrokoState.HABIT_CAMINAR,
    "pasos": TrokoState.HABIT_CAMINAR,
    "walk": TrokoState.HABIT_CAMINAR,

    # 7. Estudio
    "estudio": TrokoState.HABIT_ESTUDIO,
    "aprender": TrokoState.HABIT_ESTUDIO,
    "study": TrokoState.HABIT_ESTUDIO,

    # 8. Dormir temprano
    "dormir": TrokoState.HABIT_DORMIR,
    "dormir_temprano": TrokoState.HABIT_DORMIR,
    "sleep": TrokoState.HABIT_DORMIR,

    # 9. Comida saludable
    "comida": TrokoState.HABIT_COMIDA,
    "comida_saludable": TrokoState.HABIT_COMIDA,
    "fruta": TrokoState.HABIT_COMIDA,

    # 10. Postura
    "postura": TrokoState.HABIT_POSTURA,
    "estiramiento": TrokoState.HABIT_POSTURA,
    "stretch": TrokoState.HABIT_POSTURA,

    # 11. Pausa visual
    "pausa_visual": TrokoState.HABIT_PAUSA_VISUAL,
    "ojos": TrokoState.HABIT_PAUSA_VISUAL,
    "202020": TrokoState.HABIT_PAUSA_VISUAL,

    # 12. Agradecimiento
    "agradecimiento": TrokoState.HABIT_AGRADECIMIENTO,
    "diario": TrokoState.HABIT_AGRADECIMIENTO,
    "journal": TrokoState.HABIT_AGRADECIMIENTO,

    # 13. Respiración
    "respiracion": TrokoState.HABIT_RESPIRACION,
    "respiración": TrokoState.HABIT_RESPIRACION,
    "breath": TrokoState.HABIT_RESPIRACION,

    # 14. Limpieza
    "limpieza": TrokoState.HABIT_LIMPIEZA,
    "orden": TrokoState.HABIT_LIMPIEZA,
    "clean": TrokoState.HABIT_LIMPIEZA,

    # 15. Desconexión digital
    "desconexion": TrokoState.HABIT_DESCONEXION,
    "desconexión": TrokoState.HABIT_DESCONEXION,
    "offline": TrokoState.HABIT_DESCONEXION,
}

HABIT_TARGETS: dict[str, int] = {
    "agua": 8,           # 8 glasses
    "pomodoro": 4,       # 4 sessions
    "lectura": 1,        # 1 chapter/session
    "ejercicio": 1,      # 1 workout
    "meditacion": 1,     # 1 session
    "caminar": 10000,    # 10,000 steps
    "estudio": 1,
    "dormir_temprano": 1,
    "comida_saludable": 3,
    "postura": 4,
    "pausa_visual": 5,
    "agradecimiento": 1,
    "respiracion": 3,
    "limpieza": 1,
    "desconexion": 1,
}


# ---------------------------------------------------------------------------
# Database Schema Check & Migration
# ---------------------------------------------------------------------------

def _ensure_habit_columns(db) -> None:
    try:
        db.execute("ALTER TABLE habits ADD COLUMN amount INTEGER DEFAULT 1;")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core Operations
# ---------------------------------------------------------------------------

def log_habit(habit_key: str, amount: int = 1, notes: str = "") -> dict:
    from storage.db import DB

    h_name = habit_key.lower().strip()
    scene_state = HABIT_MAPPINGS.get(h_name, TrokoState.HABIT_AGUA)
    canonical = h_name

    with DB() as db:
        _ensure_habit_columns(db)
        today = date.today().isoformat()

        row = db.execute(
            "SELECT id, amount FROM habits WHERE habit_name = ? AND log_date = ?",
            (canonical, today),
        ).fetchone()

        target = HABIT_TARGETS.get(canonical, 1)

        if row is not None:
            new_amount = (row["amount"] or 1) + amount
            db.execute(
                "UPDATE habits SET amount = ?, notes = ? WHERE id = ?",
                (new_amount, notes, row["id"]),
            )
            current_count = new_amount
        else:
            db.execute(
                "INSERT INTO habits (habit_name, log_date, notes, amount) VALUES (?, ?, ?, ?)",
                (canonical, today, notes, amount),
            )
            current_count = amount

        streak = _calculate_streak(db, canonical)

    # Check for Goal Reached Celebration
    goal_reached = current_count >= target
    if goal_reached and (current_count - amount) < target:
        # Trigger confetti celebration!
        state_machine.transition(TrokoState.FESTEJO)
        state_machine.feedback("¡Meta Cumplida!", success=True)
    else:
        # Show specific animated scene
        state_machine.transition(scene_state)
        state_machine.feedback("Anotado", success=True)

    bus.emit("on_habit_logged", habit=canonical, streak=streak, count=current_count)

    return {
        "habit": canonical,
        "current_count": current_count,
        "target": target,
        "streak": streak,
        "goal_reached": goal_reached,
    }


def get_today_progress(habit_key: str, target: int = 8) -> dict:
    from storage.db import DB
    h_name = habit_key.lower().strip()
    today = date.today().isoformat()
    with DB() as db:
        _ensure_habit_columns(db)
        row = db.execute(
            "SELECT amount FROM habits WHERE habit_name = ? AND log_date = ?",
            (h_name, today),
        ).fetchone()
        cur = (row["amount"] if row and row["amount"] is not None else 6)
        streak = _calculate_streak(db, h_name)
    tgt = HABIT_TARGETS.get(h_name, target)
    return {"habit": h_name, "current_count": cur, "target": tgt, "streak": streak}


def undo_last_habit(habit_key: str) -> str:
    from storage.db import DB

    h_name = habit_key.lower().strip()
    today = date.today().isoformat()

    with DB() as db:
        _ensure_habit_columns(db)
        row = db.execute(
            "SELECT id, amount FROM habits WHERE habit_name = ? AND log_date = ?",
            (h_name, today),
        ).fetchone()

        if not row:
            return f"No hay registros de hoy para '{habit_key}'."

        cur = row["amount"] or 1
        if cur <= 1:
            db.execute("DELETE FROM habits WHERE id = ?", (row["id"],))
            new_val = 0
        else:
            new_val = cur - 1
            db.execute("UPDATE habits SET amount = ? WHERE id = ?", (new_val, row["id"]))

    state_machine.feedback("Deshecho", success=True)
    return f"Hábito '{habit_key}' actualizado a {new_val} hoy."


def get_streak(habit_key: str) -> dict:
    from storage.db import DB

    h_name = habit_key.lower().strip()
    with DB() as db:
        _ensure_habit_columns(db)
        streak = _calculate_streak(db, h_name)
        rows = db.execute(
            "SELECT log_date, amount FROM habits WHERE habit_name = ? ORDER BY log_date DESC LIMIT 7",
            (h_name,),
        ).fetchall()

    history = [f"{r['log_date']} ({r['amount'] or 1})" for r in rows]
    target = HABIT_TARGETS.get(h_name, 1)
    return {"habit": h_name, "streak": streak, "target": target, "recent": history}


def _calculate_streak(db, habit_name: str) -> int:
    rows = db.execute(
        "SELECT DISTINCT log_date FROM habits WHERE habit_name = ? ORDER BY log_date DESC",
        (habit_name,),
    ).fetchall()

    if not rows:
        return 0

    streak = 0
    expected = date.today()
    for row in rows:
        try:
            log_d = date.fromisoformat(row["log_date"])
        except ValueError:
            continue
        if log_d == expected:
            streak += 1
            expected -= timedelta(days=1)
        elif log_d == expected - timedelta(days=1):
            # Already checked
            continue
        else:
            break

    return streak


# ---------------------------------------------------------------------------
# Action Dispatcher Handlers
# ---------------------------------------------------------------------------

@register("log_habit")
async def _action_log_habit(args: dict) -> str:
    habit = args.get("habit_name", "agua").strip()
    amount = int(args.get("amount", 1))
    notes = args.get("notes", "")

    res = log_habit(habit, amount, notes)
    if res["goal_reached"]:
        return (
            f"🎉 ¡Felicidades! Completaste tu meta diaria de '{res['habit']}' "
            f"({res['current_count']}/{res['target']}). Racha: {res['streak']} días."
        )
    return (
        f"✅ {res['habit'].capitalize()}: {res['current_count']}/{res['target']} hoy. "
        f"Racha: {res['streak']} día(s). ¡Anotado!"
    )


@register("get_habit_streak")
async def _action_get_streak(args: dict) -> str:
    habit = args.get("habit_name", "agua").strip()
    res = get_streak(habit)
    hist = ", ".join(res["recent"]) or "ninguno"
    return f"📈 Hábito '{habit}': Racha {res['streak']} día(s). Meta diaria: {res['target']}. Reciente: {hist}"
