"""
tests/test_notch_panel.py
=========================
Unit tests for the expandable NotchPanel, arrow slide, and IslandWindow dashboard.
"""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from storage.db import add_task, get_tasks, toggle_task, delete_task
from ui.island_window import IslandWindow, COMPACT_WIDTH, COMPACT_HEIGHT, EXPANDED_WIDTH, EXPANDED_HEIGHT
from ui.notch_panel import NotchPanel


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["test", "-platform", "offscreen"])
    return app


def test_task_crud_storage():
    """Verify task database functions persist properly."""
    initial_count = len(get_tasks())
    new_t = add_task("Comprar pan para la semana")
    assert new_t.get("id") is not None
    assert new_t["title"] == "Comprar pan para la semana"
    assert new_t["completed"] is False

    tasks = get_tasks()
    assert len(tasks) == initial_count + 1
    target = next(t for t in tasks if t["id"] == new_t["id"])
    assert target["title"] == "Comprar pan para la semana"

    # Toggle
    toggle_task(new_t["id"], True)
    tasks_after_toggle = get_tasks()
    t_toggled = next(t for t in tasks_after_toggle if t["id"] == new_t["id"])
    assert t_toggled["completed"] is True

    # Delete
    delete_task(new_t["id"])
    tasks_after_del = get_tasks()
    assert len(tasks_after_del) == initial_count


def test_island_window_toggle_panel(qapp):
    """Verify IslandWindow starts compact and expands on toggle_panel."""
    win = IslandWindow()
    win.show()
    assert win._is_open is False
    assert win.width() == COMPACT_WIDTH
    assert win.height() == COMPACT_HEIGHT
    assert win.dashboard_panel.isHidden() is True
    assert win.btn_arrow.text() == "▼"

    # Open panel
    win.open_panel()
    assert win._is_open is True
    assert win.width() == EXPANDED_WIDTH
    assert win.height() == EXPANDED_HEIGHT
    assert win.dashboard_panel.isHidden() is False
    assert win.btn_arrow.text() == "▲"

    # Close panel
    win.close_panel()
    assert win._is_open is False
    assert win.width() == COMPACT_WIDTH
    assert win.height() == COMPACT_HEIGHT
    assert win.dashboard_panel.isHidden() is True
    assert win.btn_arrow.text() == "▼"
    win.close()


def test_notch_panel_views_switching(qapp):
    """Verify NotchPanel switches cleanly across all 5 sections."""
    panel = NotchPanel()
    assert panel.views_stack.currentIndex() == 0  # Inicio

    panel.switch_view(1)
    assert panel.views_stack.currentIndex() == 1  # Tareas

    panel.switch_view(2)
    assert panel.views_stack.currentIndex() == 2  # Hábitos

    panel.switch_view(3)
    assert panel.views_stack.currentIndex() == 3  # Enfoque

    panel.switch_view(4)
    assert panel.views_stack.currentIndex() == 4  # Mi PC
