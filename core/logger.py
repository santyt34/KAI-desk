"""
core/logger.py
==============
Structured, rotating file + rich console logger for KAI-Desk.
Call `setup_logging()` once at startup; every module then uses
`logging.getLogger(__name__)` normally.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from rich.logging import RichHandler

from config.settings import settings


def setup_logging() -> None:
    """
    Configure root logger with:
    - Rich console handler (coloured, with tracebacks).
    - Rotating file handler under settings.log_dir.
    """
    log_dir: Path = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, settings.log_level, logging.INFO)

    root = logging.getLogger()
    root.setLevel(log_level)

    # Avoid adding duplicate handlers if called more than once
    if root.handlers:
        return

    # --- Console via Rich ---------------------------------------------------
    console_handler = RichHandler(
        level=log_level,
        show_path=False,
        rich_tracebacks=True,
        markup=True,
    )
    console_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
    root.addHandler(console_handler)

    # --- Rotating file handler ----------------------------------------------
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "kai.log",
        maxBytes=5 * 1024 * 1024,   # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(file_handler)

    # Silence noisy third-party loggers
    for noisy in ("urllib3", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging initialised – level=%s  log_dir=%s", settings.log_level, log_dir
    )
