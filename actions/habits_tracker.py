"""
actions/habits_tracker.py
=========================
Daily habit tracking with streak calculation and UI gesture triggers.
Data is persisted in SQLite via storage/db.py.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from ai.action_dispatcher import register
from core.event_bus import bus
from core.state_machine import KAIState, state_machine

logger = logging.getLogger(__name__)

# Habit name → KAI gesture state mapping
_HABIT_GESTURE: dict[str, KAIState] = {
    "hydration": KAIState.HYDRATION,
    "agua":      KAIState.HYDRATION,
    "workout":   KAIState.WORKOUT,
    "ejercicio": KAIState.WORKOUT,
    "pomodoro":  KAIState.POMODORO,
}


# ---------------------------------------------------------------------------
# Core logic (uses DB)
# ---------------------------------------------------------------------------


def log_habit(habit_name: str, notes: str = "") -> dict:
    """
    Record today's completion of *habit_name*.
    Returns {"habit": str, "streak": int, "already_logged": bool}.
    """
    from storage.db import DB

    with DB() as db:
        today = date.today().isoformat()
        # Avoid duplicate entries for the same day
        existing = db.execute(
            "SELECT id FROM habits WHERE habit_name = ? AND log_date = ?",
            (habit_name.lower(), today),
        ).fetchone()

        already_logged = existing is not None
        if not already_logged:
            db.execute(
                "INSERT INTO habits (habit_name, log_date, notes) VALUES (?, ?, ?)",
                (habit_name.lower(), today, notes),
            )

        streak = _calculate_streak(db, habit_name.lower())

    # Trigger visual gesture
    gesture = _HABIT_GESTURE.get(habit_name.lower())
    if gesture:
        state_machine.transition(gesture)
    bus.emit("on_habit_logged", habit=habit_name, streak=streak)

    return {"habit": habit_name, "streak": streak, "already_logged": already_logged}


def get_streak(habit_name: str) -> dict:
    """Return current streak and last-7-days history for *habit_name*."""
    from storage.db import DB

    with DB() as db:
        streak = _calculate_streak(db, habit_name.lower())
        rows = db.execute(
            "SELECT log_date FROM habits WHERE habit_name = ? ORDER BY log_date DESC LIMIT 7",
            (habit_name.lower(),),
        ).fetchall()

    history = [row["log_date"] for row in rows]
    return {"habit": habit_name, "streak": streak, "last_7_days": history}


def _calculate_streak(db, habit_name: str) -> int:
    """Count consecutive days (ending today) a habit was logged."""
    rows = db.execute(
        "SELECT DISTINCT log_date FROM habits WHERE habit_name = ? ORDER BY log_date DESC",
        (habit_name,),
    ).fetchall()

    if not rows:
        return 0

    streak = 0
    expected = date.today()
    for row in rows:
        log_d = date.fromisoformat(row["log_date"])
        if log_d == expected:
            streak += 1
            expected -= timedelta(days=1)
        else:
            break

    return streak


# ---------------------------------------------------------------------------
# Action dispatcher handlers
# ---------------------------------------------------------------------------


@register("log_habit")
async def _action_log_habit(args: dict) -> str:
    habit = args.get("habit_name", "").strip()
    notes = args.get("notes", "")
    if not habit:
        raise ValueError("Se requiere el nombre del hábito.")

    result = log_habit(habit, notes)
    if result["already_logged"]:
        return f"✅ Ya registraste '{habit}' hoy. Racha: {result['streak']} día(s)."
    return f"✅ ¡'{habit}' registrado! Racha actual: {result['streak']} día(s). ¡Sigue así!"


@register("get_habit_streak")
async def _action_get_streak(args: dict) -> str:
    habit = args.get("habit_name", "").strip()
    if not habit:
        raise ValueError("Se requiere el nombre del hábito.")

    result = get_streak(habit)
    history_str = ", ".join(result["last_7_days"]) or "ninguno"
    return (
        f"📈 Hábito '{habit}':\n"
        f"  Racha actual: {result['streak']} día(s)\n"
        f"  Últimos 7 días: {history_str}"
    )
