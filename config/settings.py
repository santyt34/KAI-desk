"""
config/settings.py
==================
Centralised configuration for Troko-Desk (KAI).
Reads from environment variables (and .env file) with sane defaults.
All other modules import `settings` from here – never read os.environ directly.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

# Load .env at import time
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)


class _Settings(BaseSettings):
    """Typed, validated application settings."""

    # --- General -----------------------------------------------------------
    app_name: str = "Troko"
    app_alias: str = "KAI"
    app_version: str = "0.2.0"

    # --- AI / LLM ----------------------------------------------------------
    # "local" | "hybrid" | "online"
    llm_mode: str = "local"
    # Local engine: "llama.cpp" | "ollama" | "onnx"
    local_llm_engine: str = "ollama"
    llama_model_path: str = "models/llama-3.2-3b-instruct-q4_k_m.gguf"
    llama_download_url: str = (
        "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/"
        "resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
    )

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # Optional online fallback
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # --- Wake-word ---------------------------------------------------------
    wake_word: str = "troko"
    wake_word_alias: str = "kai"
    wake_word_sensitivity: float = 0.5
    vosk_model_path: str = ""

    # --- STT ---------------------------------------------------------------
    whisper_model: str = "base"
    whisper_device: str = "auto"

    # --- TTS ---------------------------------------------------------------
    # "kokoro" | "edge-tts" | "piper" | "none"
    tts_engine: str = "edge-tts"
    tts_voice: str = "es-MX-DaliaNeural"
    tts_enabled: bool = True
    kokoro_model_dir: str = "models/kokoro"

    # --- UI & Animation ----------------------------------------------------
    ui_fps: int = 60
    ui_width: int = 380
    ui_height: int = 84
    ui_expanded_height: int = 150
    ui_opacity: float = 0.95
    ui_accent_color: str = "#7F5AF0"
    ui_theme_mode: str = "dark"

    # --- Storage & Persistence ---------------------------------------------
    storage_dir: Path = Path("storage")
    db_path: Path = Path("storage/troko.db")
    undo_history_path: Path = Path("storage/undo_history.json")
    log_dir: Path = Path("logs")
    log_level: str = "INFO"

    # --- Desktop Organizer -------------------------------------------------
    desktop_path: Path = Path.home() / "Desktop"
    organized_root: Path = Path.home() / "Documents" / "Troko_Organized"

    # --- Productivity & Habits ---------------------------------------------
    pomodoro_work_minutes: int = 25
    pomodoro_break_minutes: int = 5
    daily_water_target: int = 8

    # --- Email Drafts ------------------------------------------------------
    email_draft_mode: bool = True  # Safe mode: drafts need user confirmation
    mock_email_recipient: str = "test@example.com"

    # --- Allowed apps (comma-separated string) -----------------------------
    allowed_apps: str = "notepad,calculator,explorer,chrome,code,spotify,discord,edge,brave,wordpad,cmd,powershell"

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


settings = _Settings()

# Ensure directories exist
for _dir in (settings.storage_dir, settings.log_dir, settings.organized_root, Path("models"), Path("scripts")):
    _dir.mkdir(parents=True, exist_ok=True)
