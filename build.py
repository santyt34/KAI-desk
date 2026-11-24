"""
build.py
========
Script de construcción para KAI-Desk.
Ejecutar con:  python build.py

Pasos:
  1. Verifica el entorno
  2. Copia el .env.example si no existe .env
  3. Llama a PyInstaller con KAI.spec
  4. Muestra el resultado y tamaño del bundle
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def check_env() -> None:
    print("=" * 55)
    print("  KAI-Desk – Builder")
    print("=" * 55)
    print(f"Python: {sys.version}")
    print(f"Root  : {ROOT}")

    pyinstaller = shutil.which("pyinstaller") or str(
        ROOT / ".venv" / "Scripts" / "pyinstaller.exe"
    )
    if not Path(pyinstaller).exists():
        print("[ERROR] PyInstaller not found. Run:")
        print("  pip install pyinstaller")
        sys.exit(1)
    print(f"PyInstaller: {pyinstaller}")
    return pyinstaller


def build(pyinstaller: str) -> None:
    print("\n[1/3] Cleaning previous build…")
    for folder in ("build", "dist"):
        p = ROOT / folder
        if p.exists():
            shutil.rmtree(p)
            print(f"  Removed {p}")

    print("\n[2/3] Running PyInstaller…")
    result = subprocess.run(
        [pyinstaller, str(ROOT / "KAI.spec"), "--noconfirm"],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("\n[ERROR] PyInstaller failed. Check output above.")
        sys.exit(result.returncode)

    print("\n[3/3] Build complete!")
    dist_dir = ROOT / "dist" / "KAI"
    if dist_dir.exists():
        total = sum(f.stat().st_size for f in dist_dir.rglob("*") if f.is_file())
        print(f"  Output : {dist_dir}")
        print(f"  Size   : {total / 1_048_576:.1f} MB")
        exe = dist_dir / "KAI.exe"
        if exe.exists():
            print(f"  Exe    : {exe}")
        print("\n✅ Done! Launch with:")
        print(f"  .\\dist\\KAI\\KAI.exe")
    else:
        print("  dist\\KAI folder not found – check PyInstaller log.")


if __name__ == "__main__":
    pyinstaller = check_env()
    build(pyinstaller)
