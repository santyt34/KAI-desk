"""
config/settings.py
==================
Centralised configuration for KAI-Desk.
Reads from environment variables (and .env file) with sane defaults.
All other modules import `settings` from here – never read os.environ directly.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

# Load .env at import time (safe to call multiple times)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)


class _Settings(BaseSettings):
    """Typed, validated application settings."""

    # --- General -----------------------------------------------------------
    app_name: str = "KAI"
    app_version: str = "0.1.0"

    # --- AI / LLM ----------------------------------------------------------
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    # "local" | "hybrid" | "online"
    llm_mode: str = "local"

    # --- Wake-word ---------------------------------------------------------
    wake_word: str = "kai"
    wake_word_sensitivity: float = 0.5
    vosk_model_path: str = ""

    # --- STT ---------------------------------------------------------------
    whisper_model: str = "base"
    whisper_device: str = "auto"

    # --- TTS ---------------------------------------------------------------
    tts_engine: str = "edge-tts"
    tts_voice: str = "es-MX-DaliaNeural"
    tts_enabled: bool = True

    # --- UI ----------------------------------------------------------------
    ui_fps: int = 60
    ui_width: int = 360
    ui_height: int = 80
    ui_opacity: float = 0.95
    ui_accent_color: str = "#7F5AF0"

    # --- Storage -----------------------------------------------------------
    storage_dir: Path = Path("storage")
    db_path: Path = Path("storage/kai.db")
    undo_history_path: Path = Path("storage/undo_history.json")
    log_dir: Path = Path("logs")
    log_level: str = "INFO"

    # --- Desktop Organizer -------------------------------------------------
    desktop_path: Path = Path.home() / "Desktop"
    organized_root: Path = Path.home() / "Documents" / "KAI_Organized"

    # --- Productivity ------------------------------------------------------
    pomodoro_work_minutes: int = 25
    pomodoro_break_minutes: int = 5

    # --- Allowed apps (comma-separated string → list) ----------------------
    allowed_apps: str = "notepad,calculator,explorer,chrome,code,spotify"

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()

    @property
    def allowed_apps_list(self) -> list[str]:
        return [a.strip().lower() for a in self.allowed_apps.split(",") if a.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton instance used by all modules
settings = _Settings()

# Ensure required directories exist at startup
for _dir in (settings.storage_dir, settings.log_dir, settings.organized_root):
    _dir.mkdir(parents=True, exist_ok=True)
