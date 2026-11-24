"""
tests/test_email_and_habits.py
==============================
Tests for Troko's safe email drafting, wake reports, and habit goal tracking.
"""

from __future__ import annotations

import pytest
from actions.email_drafts import cancel_draft, confirm_send_email, create_draft
from actions.habits_tracker import get_streak, log_habit, undo_last_habit
from actions.productivity import get_wake_report, record_due_during_sleep
from core.state_machine import TrokoState, state_machine


def test_email_draft_creation_requires_confirmation():
    draft = create_draft(recipient="ana@empresa.com", body="Mañana confirmo la reunión.")
    assert draft["recipient"] == "ana@empresa.com"
    assert draft["status"] == "pending_review"

    # Confirming
    result = confirm_send_email()
    assert "Borrador confirmado" in result or "enviado" in result.lower()

    # Once confirmed, no draft is pending
    result_empty = confirm_send_email()
    assert "No hay ningún borrador" in result_empty


def test_email_draft_cancellation():
    create_draft(recipient="pedro@test.com", body="Prueba")
    result = cancel_draft()
    assert "cancelado" in result.lower()


def test_habits_progress_and_goal_celebration(tmp_path, monkeypatch):
    from config import settings as _settings_module
    monkeypatch.setattr(_settings_module.settings, "db_path", tmp_path / "test_habits.db")

    # Log 1 water
    res1 = log_habit("agua", amount=1)
    assert res1["habit"] == "agua"
    assert res1["current_count"] >= 1

    # Log up to goal (8 glasses)
    res_goal = log_habit("agua", amount=8)
    assert res_goal["goal_reached"] is True

    # Undo 1
    undo_res = undo_last_habit("agua")
    assert "actualizado" in undo_res.lower()


def test_wake_up_report():
    record_due_during_sleep("Revisar informe de ventas")
    report = get_wake_report()
    assert "Resumen al despertar" in report
    assert "Revisar informe de ventas" in report

    # Once read, it clears
    report_cleared = get_wake_report()
    assert "No hubo recordatorios" in report_cleared
