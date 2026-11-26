"""
actions/file_organizer.py
=========================
Desktop File Organiser for Troko-Desk.
- Scans loose files on the Desktop and provides a categorised preview.
- Requires explicit confirmation ("Ordenar ahora" / "sí, ordénalo") before moving.
- Full undo history (undo_last_move) without permanent deletion.
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
from core.event_bus import bus
from core.state_machine import TrokoState, state_machine

logger = logging.getLogger(__name__)

# Extension to category map
_CATEGORIES: dict[str, str] = {
    # Images
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images",
    ".gif": "Images", ".bmp": "Images", ".svg": "Images", ".webp": "Images",
    # Documents
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".txt": "Documents", ".odt": "Documents", ".rtf": "Documents",
    # Spreadsheets
    ".xls": "Spreadsheets", ".xlsx": "Spreadsheets", ".csv": "Spreadsheets",
    # Presentations
    ".ppt": "Presentations", ".pptx": "Presentations",
    # Videos
    ".mp4": "Videos", ".mkv": "Videos", ".avi": "Videos", ".mov": "Videos",
    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio", ".ogg": "Audio",
    # Code
    ".py": "Code", ".js": "Code", ".ts": "Code", ".html": "Code",
    ".css": "Code", ".json": "Code", ".xml": "Code", ".bat": "Code", ".ps1": "Code",
    # Archives
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives", ".tar": "Archives",
    # Executables
    ".exe": "Executables", ".msi": "Executables",
}


def _category(path: Path) -> str:
    return _CATEGORIES.get(path.suffix.lower(), "Misc")


def _load_history() -> list[dict]:
    path = settings.undo_history_path
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Could not read undo history – starting fresh")
    return []


def _save_history(history: list[dict]) -> None:
    settings.undo_history_path.parent.mkdir(parents=True, exist_ok=True)
    settings.undo_history_path.write_text(
        json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def scan_desktop(source_dir: Optional[Path] = None) -> list[dict]:
    source = source_dir or settings.desktop_path
    if not source.exists():
        return []

    planned = []
    for item in source.iterdir():
        if item.is_file() and not item.name.startswith(".") and not item.name.lower().endswith(".lnk"):
            cat = _category(item)
            dest_dir = settings.organized_root / cat
            dest_file = dest_dir / item.name
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
                "filename": item.name,
            })
    return planned


def execute_moves(planned: list[dict]) -> list[dict]:
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
    history = _load_history()
    if not history:
        return "No hay movimientos para deshacer."

    batch = history.pop()
    reverted = []
    failed = []

    for move in reversed(batch["moves"]):
        src = Path(move["dst"])
        dst = Path(move["src"])
        try:
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                reverted.append(dst.name)
            else:
                failed.append(src.name)
        except Exception:
            failed.append(src.name)

    _save_history(history)
    state_machine.feedback("Deshecho", success=True)
    return f"🔄 Revertidos {len(reverted)} archivo(s) al escritorio."


# ---------------------------------------------------------------------------
# Action Dispatcher Handlers
# ---------------------------------------------------------------------------

@register("organize_desktop")
async def _action_organize(args: dict) -> str:
    confirm = args.get("confirm", False)
    planned = scan_desktop()

    if not planned:
        return "El escritorio ya está limpio y organizado. No hay archivos sueltos."

    if not confirm:
        # Show preview and trigger notch confirmation bar
        summary_lines = [f"- {p['filename']} → [{p['category']}]" for p in planned[:10]]
        summary = "\n".join(summary_lines)
        if len(planned) > 10:
            summary += f"\n… y {len(planned) - 10} más."

        bus.emit(
            "on_request_confirmation",
            title=f"¿Ordenar {len(planned)} archivos?",
            callback_data={"action": "organize_desktop", "planned": planned},
        )
        state_machine.feedback(f"{len(planned)} archivos", success=True)
        return (
            f"📁 **Vista previa de organización ({len(planned)} archivos):**\n"
            f"{summary}\n\n"
            f"💡 Para aplicar di *'ordenar ahora'* o presiona Confirmar en la isla."
        )

    executed = execute_moves(planned)
    state_machine.transition(TrokoState.HABIT_LIMPIEZA)
    state_machine.feedback("Listo", success=True)
    return f"✨ ¡Listo! Se organizaron {len(executed)} archivos en '{settings.organized_root}'. Puedes decir 'deshacer' si lo deseas."


@register("undo_last_move")
async def _action_undo(_args: dict) -> str:
    return undo_last_move()
