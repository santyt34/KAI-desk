"""
scripts/generate_assets.py
==========================
Asset and spritesheet generation utility for Troko-Desk.
Renders procedural vector emotion frames and habit scenes to PNG assets
if static assets are desired on disk, or verifies runtime vector rendering.
Runs headless using QOffscreenSurface / QImage.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath

from core.state_machine import TrokoState


def ensure_app():
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(["troko_gen", "-platform", "offscreen"])
    return app


def render_scene_frame(state: TrokoState, width: int = 380, height: int = 84) -> QImage:
    """Renders one vector procedural frame for a given Troko state into a QImage."""
    img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Notch body
    body_path = QPainterPath()
    r = min(height / 2.0, 36.0)
    body_path.addRoundedRect(QRectF(2, 2, width - 4, height - 4), r, r)
    painter.fillPath(body_path, QColor("#121420"))

    # Render state eyes/scene
    cy = height / 2.0
    spacing = width * 0.26
    lx = width / 2.0 - spacing
    rx = width / 2.0 + spacing

    # Eyes
    if state == TrokoState.CONTENTO:
        _draw_arc(painter, lx, cy)
        _draw_arc(painter, rx, cy)
    elif state == TrokoState.ENAMORADO:
        _draw_heart(painter, lx, cy, 24)
        _draw_heart(painter, rx, cy, 24)
    elif state == TrokoState.HABIT_AGUA:
        # Vector water glass
        painter.setPen(QColor("#00E5FF"))
        painter.setBrush(QColor("#0091EA"))
        painter.drawRoundedRect(QRectF(width / 2.0 - 15, cy - 18, 30, 36), 4, 4)
    elif state == TrokoState.HABIT_POMODORO:
        # Vector tomato
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E53935"))
        painter.drawEllipse(QRectF(width / 2.0 - 16, cy - 16, 32, 32))
        painter.setBrush(QColor("#43A047"))
        painter.drawEllipse(QRectF(width / 2.0 - 4, cy - 20, 8, 6))
    else:
        # Standard oval eyes
        painter.setBrush(QColor("#7F5AF0"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(lx - 12, cy - 14, 24, 28))
        painter.drawEllipse(QRectF(rx - 12, cy - 14, 24, 28))

    painter.end()
    return img


def _draw_arc(painter: QPainter, cx: float, cy: float):
    path = QPainterPath()
    path.moveTo(cx - 15, cy + 2)
    path.quadTo(cx, cy - 16, cx + 15, cy + 2)
    painter.setPen(QColor("#7F5AF0"))
    painter.drawPath(path)


def _draw_heart(painter: QPainter, cx: float, cy: float, s: float):
    path = QPainterPath()
    path.moveTo(cx, cy + s * 0.3)
    path.cubicTo(cx - s, cy - s * 0.5, cx - s * 1.1, cy + s * 0.4, cx, cy + s * 1.2)
    path.cubicTo(cx + s * 1.1, cy + s * 0.4, cx + s, cy - s * 0.5, cx, cy + s * 0.3)
    painter.setBrush(QColor("#FF4081"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPath(path)


def generate_all_assets(output_dir: Path):
    ensure_app()
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Exporting Troko vector asset frames to {output_dir}...")

    states_to_render = [
        TrokoState.REPOSO,
        TrokoState.ESCUCHA,
        TrokoState.PIENSA,
        TrokoState.HABLA,
        TrokoState.ALERTA,
        TrokoState.CONTENTO,
        TrokoState.ENAMORADO,
        TrokoState.SORPRESA,
        TrokoState.ORGULLOSO,
        TrokoState.GUINO,
        TrokoState.BOSTEZO,
        TrokoState.MAREADO,
        TrokoState.TRISTE,
        TrokoState.ENFADADO,
        TrokoState.TIMIDO,
        TrokoState.CURIOSO,
        TrokoState.TRAVIESO,
        TrokoState.HABIT_POMODORO,
        TrokoState.HABIT_AGUA,
        TrokoState.HABIT_LECTURA,
        TrokoState.HABIT_EJERCICIO,
        TrokoState.HABIT_MEDITACION,
        TrokoState.FESTEJO,
    ]

    for st in states_to_render:
        img = render_scene_frame(st)
        target_file = output_dir / f"troko_{st.value}.png"
        img.save(str(target_file))
        print(f"  ✓ Saved: {target_file.name}", flush=True)

    print("All assets successfully generated!", flush=True)


if __name__ == "__main__":
    out = ROOT / "assets" / "generated"
    generate_all_assets(out)
    sys.exit(0)
