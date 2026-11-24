"""
tests/test_file_organizer.py
============================
Unit tests for the desktop file organiser.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_desktop(tmp_path: Path) -> Path:
    """Create a temporary desktop with sample files."""
    files = [
        "photo.jpg",
        "report.pdf",
        "budget.xlsx",
        "video.mp4",
        "script.py",
        "archive.zip",
        "unknown_file.xyz",
    ]
    for name in files:
        (tmp_path / name).write_text(f"content of {name}", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def tmp_organized(tmp_path: Path) -> Path:
    return tmp_path / "Organized"


@pytest.fixture(autouse=True)
def patch_settings(tmp_desktop, tmp_organized, tmp_path, monkeypatch):
    """Point settings to temp dirs so tests don't touch the real filesystem."""
    from config import settings as _settings_module
    monkeypatch.setattr(_settings_module.settings, "desktop_path", tmp_desktop)
    monkeypatch.setattr(_settings_module.settings, "organized_root", tmp_organized)
    monkeypatch.setattr(
        _settings_module.settings,
        "undo_history_path",
        tmp_path / "undo_history.json",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_scan_returns_all_loose_files(tmp_desktop):
    from actions.file_organizer import scan_desktop
    planned = scan_desktop(tmp_desktop)
    assert len(planned) == 7


def test_scan_assigns_correct_categories(tmp_desktop):
    from actions.file_organizer import scan_desktop
    planned = scan_desktop(tmp_desktop)
    by_name = {Path(p["src"]).name: p["category"] for p in planned}
    assert by_name["photo.jpg"] == "Images"
    assert by_name["report.pdf"] == "Documents"
    assert by_name["budget.xlsx"] == "Spreadsheets"
    assert by_name["video.mp4"] == "Videos"
    assert by_name["script.py"] == "Code"
    assert by_name["archive.zip"] == "Archives"
    assert by_name["unknown_file.xyz"] == "Misc"


def test_execute_moves_files(tmp_desktop, tmp_organized):
    from actions.file_organizer import execute_moves, scan_desktop
    planned = scan_desktop(tmp_desktop)
    executed = execute_moves(planned)

    assert len(executed) == 7
    # Desktop should now be empty of those files
    remaining = [f for f in tmp_desktop.iterdir() if f.is_file()]
    assert len(remaining) == 0
    # Organized folders created
    assert tmp_organized.exists()


def test_undo_reverts_last_batch(tmp_desktop, tmp_organized, tmp_path):
    from actions.file_organizer import execute_moves, scan_desktop, undo_last_move
    planned = scan_desktop(tmp_desktop)
    execute_moves(planned)

    # Verify files are gone from desktop
    assert not (tmp_desktop / "photo.jpg").exists()

    result = undo_last_move()
    assert "Revertidos" in result or "undo" in result.lower()

    # Files should be back on desktop
    assert (tmp_desktop / "photo.jpg").exists()


def test_undo_with_no_history(tmp_path, monkeypatch):
    from config import settings as _settings_module
    monkeypatch.setattr(
        _settings_module.settings,
        "undo_history_path",
        tmp_path / "empty_history.json",
    )
    from actions.file_organizer import undo_last_move
    result = undo_last_move()
    assert "No hay" in result


def test_name_collision_handling(tmp_desktop, tmp_organized):
    """Files with identical names get a numeric suffix, not overwritten."""
    from actions.file_organizer import execute_moves, scan_desktop

    # Create a collision by pre-placing a file
    (tmp_organized / "Images").mkdir(parents=True, exist_ok=True)
    (tmp_organized / "Images" / "photo.jpg").write_text("existing", encoding="utf-8")

    planned = scan_desktop(tmp_desktop)
    execute_moves(planned)

    # Both should exist: original and moved-with-suffix
    images_dir = tmp_organized / "Images"
    jpg_files = list(images_dir.glob("photo*.jpg"))
    assert len(jpg_files) >= 2
