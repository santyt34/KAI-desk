"""
actions/app_launcher.py
=======================
Opens applications, folders and system paths in a safe, allow-listed manner.
Validates targets against settings.allowed_apps before execution.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from ai.action_dispatcher import register
from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known app aliases → executable or shell command
# ---------------------------------------------------------------------------

_APP_MAP: dict[str, str] = {
    "notepad":     "notepad.exe",
    "calculator":  "calc.exe",
    "explorer":    "explorer.exe",
    "paint":       "mspaint.exe",
    "wordpad":     "wordpad.exe",
    "cmd":         "cmd.exe",
    "powershell":  "powershell.exe",
    "task manager":"taskmgr.exe",
    "chrome":      "chrome",
    "firefox":     "firefox",
    "code":        "code",
    "spotify":     "spotify",
    "discord":     "discord",
    "vlc":         "vlc",
    "winamp":      "winamp",
}


def _is_allowed(target: str) -> bool:
    """Return True if *target* is in the allow list."""
    allowed = settings.allowed_apps_list
    tl = target.lower().strip()
    return any(tl == a or tl.startswith(a) for a in allowed)


def launch(target: str) -> str:
    """
    Open *target* (app name or absolute path).
    Returns a human-readable result message.
    Raises PermissionError if the target is not allowed.
    """
    target = target.strip()
    tl = target.lower()

    # Check if it's a file/folder path
    path = Path(target)
    if path.exists():
        logger.info("Opening path: %s", path)
        os.startfile(str(path))  # type: ignore[attr-defined]
        return f"Abriendo: {path.name}"

    # Normalize via alias map
    alias = _APP_MAP.get(tl, target)

    if not _is_allowed(tl):
        raise PermissionError(
            f"'{target}' no está en la lista de aplicaciones permitidas. "
            f"Agrega '{tl}' a ALLOWED_APPS en .env para habilitarlo."
        )

    logger.info("Launching app: %s → %s", tl, alias)
    try:
        subprocess.Popen(
            [alias],
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        )
        return f"Abriendo {target}…"
    except FileNotFoundError:
        raise ValueError(f"No se encontró la aplicación '{target}'.")
    except Exception as exc:
        raise RuntimeError(f"Error al abrir '{target}': {exc}") from exc


# ---------------------------------------------------------------------------
# Action dispatcher handler
# ---------------------------------------------------------------------------

@register("open_app")
async def _action_open_app(args: dict) -> str:
    target = args.get("target", "").strip()
    if not target:
        raise ValueError("Se requiere el nombre de la aplicación o ruta.")
    return launch(target)
