# -*- mode: python ; coding: utf-8 -*-
# ============================================================
# KAI-Desk – PyInstaller spec file
# Build:  .\.venv\Scripts\pyinstaller.exe KAI.spec
# Output: dist\KAI\KAI.exe  (one-folder) or dist\KAI.exe (one-file)
# ============================================================

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)   # project root

# ---------------------------------------------------------------------------
# Data files to bundle (src, dest_in_bundle)
# ---------------------------------------------------------------------------
datas = [
    # Project config & schema
    (str(ROOT / "config" / "tools_schema.json"),  "config"),
    (str(ROOT / ".env.example"),                   "."),
    # Vosk models directory (if present at build time)
    # (str(ROOT / "vosk-model-en-us-*"),           "."),
]

# Collect data files from third-party packages
datas += collect_data_files("vosk")
datas += collect_data_files("faster_whisper")
datas += collect_data_files("edge_tts")
datas += collect_data_files("PyQt6")

# ---------------------------------------------------------------------------
# Hidden imports (dynamic imports that PyInstaller misses)
# ---------------------------------------------------------------------------
hiddenimports = [
    # PyQt6
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.sip",
    # pydantic
    "pydantic",
    "pydantic_settings",
    "pydantic.deprecated.class_validators",
    # audio
    "sounddevice",
    "soundfile",
    "vosk",
    "faster_whisper",
    # AI
    "httpx",
    "ollama",
    "openai",
    # TTS
    "edge_tts",
    # utils
    "dotenv",
    "rich",
    "rich.logging",
    "rich.console",
    "aiofiles",
    "psutil",
    "schedule",
    # Windows
    "win32api",
    "win32con",
    "win32gui",
    "winsound",
    # project modules
    "config.settings",
    "core.event_bus",
    "core.state_machine",
    "core.logger",
    "ui.island_window",
    "ui.eye_renderer",
    "ui.tray_menu",
    "audio.wake_word",
    "audio.stt_whisper",
    "audio.tts_speaker",
    "ai.llm_router",
    "ai.prompts",
    "ai.action_dispatcher",
    "actions.file_organizer",
    "actions.app_launcher",
    "actions.productivity",
    "actions.habits_tracker",
    "storage.db",
]

hiddenimports += collect_submodules("vosk")
hiddenimports += collect_submodules("ctranslate2")
hiddenimports += collect_submodules("onnxruntime")

# ---------------------------------------------------------------------------
# Excludes – trim the bundle size
# ---------------------------------------------------------------------------
excludes = [
    "tkinter",
    "matplotlib",
    "PIL",
    "cv2",
    "IPython",
    "jupyter",
    "notebook",
    "test",
    "tests",
    "unittest",
    "pytest",
    "setuptools",
    "distutils",
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# ONE-FOLDER build (faster startup, easier to debug)
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/kai_icon.ico",   # uncomment when icon is ready
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="KAI",
)
