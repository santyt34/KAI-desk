"""
src/ui/scene_generator.py
=========================
Procedural Vector Scene Generator and Player for 15 Habit Styles + Celebration in KAI.
Renders directly via QPainter vector paths at 60 FPS without external raster assets.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

ACCENT = QColor("#7F5AF0")
WHITE = QColor("#FFFFFF")
LILA_LIGHT = QColor("#A882FF")


class SceneGenerator:
    """
    Renders vector habit scenes within KAI's floating notch capsule.
    """

    def __init__(self) -> None:
        pass

    def render_scene(
        self,
        scene_name: str,
        painter: QPainter,
        cx: float,
        cy: float,
        w: float,
        h: float,
        time_elapsed: float,
        metadata: dict,
    ) -> None:
        s = scene_name.lower().replace("habit_", "")

        if s in ("pomodoro", "enfoque"):
            self._scene_pomodoro(painter, cx, cy, w, h, time_elapsed, metadata)
        elif s in ("agua", "hydration", "water"):
            self._scene_water(painter, cx, cy, w, h, time_elapsed, metadata)
        elif s in ("lectura", "reading"):
            self._scene_reading(painter, cx, cy, w, h, time_elapsed)
        elif s in ("ejercicio", "workout"):
            self._scene_workout(painter, cx, cy, w, h, time_elapsed)
        elif s in ("meditacion", "descanso", "zen"):
            self._scene_meditation(painter, cx, cy, w, h, time_elapsed)
        elif s in ("caminar", "walk"):
            self._scene_walking(painter, cx, cy, w, h, time_elapsed)
        elif s in ("estudio", "study"):
            self._scene_study(painter, cx, cy, w, h, time_elapsed)
        elif s in ("dormir_temprano", "dormir", "sleep"):
            self._scene_sleep(painter, cx, cy, w, h, time_elapsed)
        elif s in ("comida_saludable", "comida"):
            self._scene_healthy_food(painter, cx, cy, w, h, time_elapsed)
        elif s in ("postura", "stretch"):
            self._scene_posture(painter, cx, cy, w, h, time_elapsed)
        elif s in ("pausa_visual", "ojos", "202020"):
            self._scene_visual_pause(painter, cx, cy, w, h, time_elapsed)
        elif s in ("agradecimiento", "journal"):
            self._scene_journal(painter, cx, cy, w, h, time_elapsed)
        elif s in ("respiracion", "breath"):
            self._scene_breathing(painter, cx, cy, w, h, time_elapsed)
        elif s in ("limpieza", "orden"):
            self._scene_clean(painter, cx, cy, w, h, time_elapsed)
        elif s in ("desconexion", "offline"):
            self._scene_digital_detox(painter, cx, cy, w, h, time_elapsed)
        elif s in ("festejo", "celebration"):
            self._scene_celebration(painter, cx, cy, w, h, time_elapsed)
        else:
            self._scene_default(painter, cx, cy, w, h, time_elapsed)

    # 1. Pomodoro Focus
    def _scene_pomodoro(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float, meta: dict) -> None:
        rem_sec = meta.get("pomodoro_remaining_sec", 25 * 60)
        mins = rem_sec // 60
        secs = rem_sec % 60
        time_str = f"{mins:02d}:{secs:02d}"

        bx = cx - 65
        # Laptop base
        lp_y = cy + 16
        painter.setBrush(QColor("#2B2E42"))
        painter.setPen(QPen(ACCENT, 1.2))
        painter.drawRoundedRect(QRectF(bx - 22, lp_y, 44, 5), 2, 2)
        # Screen glow
        painter.setBrush(QColor("#80D8FF"))
        painter.drawRect(QRectF(bx - 16, lp_y - 14, 32, 14))

        # Typing hands animation
        offset = 3.0 * math.sin(t * 18.0)
        painter.setBrush(WHITE)
        painter.drawEllipse(QRectF(bx - 12, lp_y - 2 + offset, 5, 5))
        painter.drawEllipse(QRectF(bx + 7, lp_y - 2 - offset, 5, 5))

        # Countdown display
        font = painter.font()
        font.setPointSize(15)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 8, cy - 20, 140, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"🍅 {time_str}")

        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(LILA_LIGHT)
        painter.drawText(QRectF(cx + 12, cy + 5, 120, 18), "Enfoque KAI")

    # 2. Water / Hydration
    def _scene_water(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float, meta: dict) -> None:
        cur = meta.get("water_count", 6)
        target = meta.get("water_target", 8)
        frac = min(1.0, max(0.15, cur / float(target)))

        gx = cx - 50
        gw, gh = 26.0, 38.0
        rect = QRectF(gx - gw / 2, cy - gh / 2, gw, gh)

        # Glass
        painter.setPen(QPen(QColor("#80D8FF"), 1.8))
        painter.setBrush(QColor(18, 25, 40, 140))
        painter.drawRoundedRect(rect, 4, 4)

        # Water level
        liq_h = gh * frac
        liq_rect = QRectF(rect.left() + 2, rect.bottom() - liq_h, gw - 4, liq_h - 2)
        grad = QLinearGradient(0, liq_rect.top(), 0, liq_rect.bottom())
        grad.setColorAt(0.0, QColor("#00E5FF"))
        grad.setColorAt(1.0, QColor("#0091EA"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(liq_rect, 3, 3)

        # Text
        font = painter.font()
        font.setPointSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 5, cy - 18, 140, 22), f"💧 {cur}/{target} vasos")

        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#80D8FF"))
        painter.drawText(QRectF(cx + 10, cy + 5, 130, 18), "¡Excelente hidratación!")

    # 3. Reading
    def _scene_reading(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        bx = cx - 45
        curl = math.sin(t * 5.0) * 6.0
        painter.setPen(QPen(QColor("#D7CCC8"), 1.4))
        painter.setBrush(QColor("#FFF9C4"))
        painter.drawRoundedRect(QRectF(bx - 24, cy - 14, 22, 28), 2, 2)
        painter.drawRoundedRect(QRectF(bx + 2, cy - 14 + curl, 22, 28), 2, 2)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "📖 Leyendo...")

    # 4. Workout
    def _scene_workout(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        lift = math.sin(t * 6.0) * 8.0
        bx = cx - 45
        painter.setPen(QPen(QColor("#B0BEC5"), 3.0))
        painter.drawLine(int(bx - 26), int(cy - lift), int(bx + 26), int(cy - lift))
        painter.setBrush(QColor("#37474F"))
        painter.drawRoundedRect(QRectF(bx - 30, cy - lift - 8, 8, 16), 2, 2)
        painter.drawRoundedRect(QRectF(bx + 22, cy - lift - 8, 8, 16), 2, 2)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "💪 ¡Entrenando!")

    # 5. Meditation
    def _scene_meditation(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        breath = (math.sin(t * 1.5) + 1.0) / 2.0
        r = 16.0 + 9.0 * breath
        bx = cx - 45

        grad = QRadialGradient(bx, cy, r * 1.5)
        grad.setColorAt(0.0, QColor(255, 214, 0, int(180 * breath + 40)))
        grad.setColorAt(1.0, QColor(255, 171, 0, 0))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(bx - r * 1.5, cy - r * 1.5, r * 3, r * 3))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        phase = "Inhala..." if breath > 0.5 else "Exhala..."
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), f"🧘 {phase}")

    # 6. Walking
    def _scene_walking(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        s1 = math.sin(t * 8.0) * 5.0
        bx = cx - 45
        painter.setBrush(QColor("#00E676"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(bx - 14, cy + s1, 10, 6))
        painter.drawEllipse(QRectF(bx + 4, cy - s1, 10, 6))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "🚶 Caminata activa")

    # 7. Study
    def _scene_study(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        bx = cx - 45
        glow = (math.sin(t * 5.0) + 1.0) / 2.0
        painter.setBrush(QColor(255, 235, 59, int(150 + 105 * glow)))
        painter.setPen(QPen(QColor("#FBC02D"), 1.5))
        painter.drawEllipse(QRectF(bx - 12, cy - 13, 24, 22))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "💡 ¡Estudiando!")

    # 8. Sleep early
    def _scene_sleep(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        bx = cx - 45
        p1 = QPainterPath()
        p1.addEllipse(QRectF(bx - 13, cy - 13, 26, 26))
        p2 = QPainterPath()
        p2.addEllipse(QRectF(bx - 5, cy - 17, 24, 24))
        moon = p1.subtracted(p2)
        painter.setBrush(QColor("#FFF59D"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(moon)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "🌙 Hora de dormir")

    # 9. Healthy food
    def _scene_healthy_food(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        bx = cx - 45
        painter.setBrush(QColor("#E53935"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(bx - 12, cy - 9, 24, 21))
        painter.setBrush(QColor("#43A047"))
        painter.drawEllipse(QRectF(bx, cy - 16, 7, 5))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "🍎 Nutrición sana")

    # 10. Posture
    def _scene_posture(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        bx = cx - 45
        painter.setPen(QPen(QColor("#00E5FF"), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(int(bx), int(cy - 14), int(bx), int(cy + 14))
        painter.setBrush(QColor("#00E5FF"))
        painter.drawEllipse(QRectF(bx - 5, cy - 22, 10, 10))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "🧍 Postura recta")

    # 11. Visual pause
    def _scene_visual_pause(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        bx = cx - 45
        # Soft eye arcs
        path = QPainterPath()
        path.moveTo(bx - 14, cy)
        path.quadTo(bx - 7, cy + 8, bx, cy)
        path.moveTo(bx + 2, cy)
        path.quadTo(bx + 9, cy + 8, bx + 16, cy)
        painter.setPen(QPen(WHITE, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "👀 Pausa 20-20-20")

    # 12. Journal
    def _scene_journal(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        bx = cx - 45
        painter.setBrush(QColor("#FFCC80"))
        painter.setPen(QPen(QColor("#E65100"), 1.2))
        painter.drawRoundedRect(QRectF(bx - 12, cy - 14, 24, 28), 2, 2)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "📝 Diario y gratitud")

    # 13. Breathing
    def _scene_breathing(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        bx = cx - 45
        r = 10.0 + 8.0 * ((math.sin(t * 1.8) + 1.0) / 2.0)
        painter.setBrush(QColor(127, 90, 240, 160))
        painter.setPen(QPen(ACCENT, 2.0))
        painter.drawEllipse(QRectF(bx - r, cy - r, r * 2, r * 2))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "🌬️ Respira 4-4-4")

    # 14. Clean
    def _scene_clean(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        bx = cx - 45
        painter.setPen(QPen(QColor("#FFD600"), 2.2))
        painter.drawLine(int(bx - 9), int(cy + 9), int(bx + 9), int(cy - 9))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "✨ Orden y limpieza")

    # 15. Digital detox
    def _scene_digital_detox(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        bx = cx - 45
        painter.setBrush(QColor("#2E7D32"))
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.moveTo(bx, cy - 13)
        path.quadTo(bx + 13, cy, bx, cy + 13)
        path.quadTo(bx - 13, cy, bx, cy - 13)
        painter.drawPath(path)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 12, cy - 14, 140, 28), "🌿 Desconexión zen")

    # Celebration
    def _scene_celebration(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        font = painter.font()
        font.setPointSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "🎉 ¡META CUMPLIDA! 🎉")

    def _scene_default(self, painter: QPainter, cx: float, cy: float, w: float, h: float, t: float) -> None:
        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "✨ KAI Hábitos")


scene_generator = SceneGenerator()
