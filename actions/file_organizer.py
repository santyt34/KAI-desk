"""
actions/file_organizer.py
=========================
Desktop file organiser with preview mode and undo history.

Scans a directory (default: Desktop) for loose files, categorises them by
extension and moves them into sub-folders under settings.organized_root.
Every move is recorded in undo_history.json so it can be reversed without
permanent deletion.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from ai.action_dispatcher import register
from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extension → category map
# ---------------------------------------------------------------------------

_CATEGORIES: dict[str, str] = {
    # Images
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images",
    ".gif": "Images", ".bmp": "Images", ".svg": "Images", ".webp": "Images",
    # Documents
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".txt": "Documents", ".odt": "Documents", ".rtf": "Documents",
    # Spreadsheets
    ".xls": "Spreadsheets", ".xlsx": "Spreadsheets", ".csv": "Spreadsheets",
    ".ods": "Spreadsheets",
    # Presentations
    ".ppt": "Presentations", ".pptx": "Presentations", ".odp": "Presentations",
    # Videos
    ".mp4": "Videos", ".mkv": "Videos", ".avi": "Videos",
    ".mov": "Videos", ".wmv": "Videos",
    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio",
    ".aac": "Audio", ".ogg": "Audio",
    # Code
    ".py": "Code", ".js": "Code", ".ts": "Code", ".html": "Code",
    ".css": "Code", ".json": "Code", ".xml": "Code", ".sh": "Code",
    ".bat": "Code", ".ps1": "Code",
    # Archives
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives",
    ".tar": "Archives", ".gz": "Archives",
    # Executables
    ".exe": "Executables", ".msi": "Executables", ".dmg": "Executables",
}


def _category(path: Path) -> str:
    return _CATEGORIES.get(path.suffix.lower(), "Misc")


# ---------------------------------------------------------------------------
# Undo history helpers
# ---------------------------------------------------------------------------

def _load_history() -> list[dict]:
    path = settings.undo_history_path
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Could not read undo history – starting fresh")
    return []


def _save_history(history: list[dict]) -> None:
    settings.undo_history_path.write_text(
        json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def scan_desktop(source_dir: Optional[Path] = None) -> list[dict]:
    """
    Return a list of planned moves without executing them.
    Each entry: {"src": str, "dst": str, "category": str}
    """
    source = source_dir or settings.desktop_path
    if not source.exists():
        logger.error("Desktop path does not exist: %s", source)
        return []

    planned = []
    for item in source.iterdir():
        if item.is_file() and not item.name.startswith("."):
            cat = _category(item)
            dest_dir = settings.organized_root / cat
            dest_file = dest_dir / item.name
            # Handle name collisions
            if dest_file.exists():
                stem = item.stem
                suffix = item.suffix
                counter = 1
                while dest_file.exists():
                    dest_file = dest_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            planned.append({
                "src": str(item),
                "dst": str(dest_file),
                "category": cat,
            })

    return planned


def execute_moves(planned: list[dict]) -> list[dict]:
    """
    Execute the planned moves and record them in undo history.
    Returns the list of actually-executed moves.
    """
    if not planned:
        return []

    executed = []
    history = _load_history()
    batch = {
        "timestamp": datetime.now().isoformat(),
        "moves": [],
    }

    for move in planned:
        src = Path(move["src"])
        dst = Path(move["dst"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dst))
            batch["moves"].append({"src": str(src), "dst": str(dst)})
            executed.append(move)
            logger.info("Moved: %s → %s", src.name, dst)
        except Exception:
            logger.exception("Failed to move: %s", src)

    if batch["moves"]:
        history.append(batch)
        _save_history(history)

    return executed


def undo_last_move() -> str:
    """
    Revert the last batch of file moves.
    Returns a human-readable summary.
    """
    history = _load_history()
    if not history:
        return "No hay movimientos para deshacer."

    batch = history.pop()
    reverted = []
    failed = []

    for move in reversed(batch["moves"]):
        src = Path(move["dst"])   # current location
        dst = Path(move["src"])   # original location
        try:
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                reverted.append(dst.name)
            else:
                logger.warning("File not found for undo: %s", src)
                failed.append(src.name)
        except Exception:
            logger.exception("Undo failed for: %s", src)
            failed.append(src.name)

    _save_history(history)

    parts = []
    if reverted:
        parts.append(f"Revertidos {len(reverted)} archivo(s).")
    if failed:
        parts.append(f"No se pudo revertir: {', '.join(failed)}.")
    return " ".join(parts) or "Undo completo."


# ---------------------------------------------------------------------------
# Action dispatcher handlers
# ---------------------------------------------------------------------------

@register("organize_desktop")
async def _action_organize(args: dict) -> str:
    preview: bool = args.get("preview", True)
    planned = scan_desktop()

    if not planned:
        return "El escritorio ya está organizado o no hay archivos sueltos."

    summary_lines = [f"- {p['category']}: {Path(p['src']).name}" for p in planned]
    summary = "\n".join(summary_lines[:20])
    if len(planned) > 20:
        summary += f"\n… y {len(planned) - 20} más."

    if preview:
        return f"Vista previa ({len(planned)} archivos):\n{summary}"

    executed = execute_moves(planned)
    return f"Organizado {len(executed)} archivo(s) en {settings.organized_root}.\n{summary}"


@register("undo_last_move")
async def _action_undo(_args: dict) -> str:
    return undo_last_move()
