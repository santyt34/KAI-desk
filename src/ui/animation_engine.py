"""
src/ui/animation_engine.py
==========================
60 FPS Procedural Animation & Particle Engine for KAI.
Handles:
- Easing interpolation curves (cubic, elastic, bounce, smooth lerp).
- Particle systems (blush, hearts, stars, sweat drops, confetti, waves, sparks, zzz).
- Real-time frame ticker and feedback badges.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient


# ---------------------------------------------------------------------------
# Easing Curves
# ---------------------------------------------------------------------------


def ease_out_quad(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)


def ease_in_out_quad(t: float) -> float:
    return 2.0 * t * t if t < 0.5 else 1.0 - math.pow(-2.0 * t + 2.0, 2.0) / 2.0


def ease_out_cubic(t: float) -> float:
    return 1.0 - math.pow(1.0 - t, 3.0)


def ease_out_back(t: float, s: float = 1.70158) -> float:
    return 1.0 + (s + 1.0) * math.pow(t - 1.0, 3.0) + s * math.pow(t - 1.0, 2.0)


def ease_out_elastic(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    c4 = (2.0 * math.pi) / 3.0
    return math.pow(2.0, -10.0 * t) * math.sin((t * 10.0 - 0.75) * c4) + 1.0


def ease_out_bounce(t: float) -> float:
    n1 = 7.5625
    d1 = 2.75
    if t < 1.0 / d1:
        return n1 * t * t
    elif t < 2.0 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


# ---------------------------------------------------------------------------
# Particle Primitive
# ---------------------------------------------------------------------------


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    life: float = 1.0          # 1.0 (fresh) down to 0.0 (dead)
    decay: float = 0.02
    color: QColor = field(default_factory=lambda: QColor("#FFFFFF"))
    rotation: float = 0.0
    v_rot: float = 0.0
    kind: str = "circle"       # heart, star, sweat, confetti, zzz, wave, spark, circle


# ---------------------------------------------------------------------------
# Animation Engine
# ---------------------------------------------------------------------------


class AnimationEngine:
    """
    Drives 60 FPS visual details and micro-animations for KAI:
    - Particle physics & lifecycles.
    - Floating hearts, glowing stars, sweat drops, confetti bursts, sparks.
    - Smooth blush on cheeks.
    - Action confirmation badge (green check + short feedback text).
    """

    def __init__(self) -> None:
        self.particles: List[Particle] = []
        self.blush_intensity: float = 0.0
        self.target_blush: float = 0.0

        # Action feedback badge
        self.badge_active: bool = False
        self.badge_text: str = "Listo"
        self.badge_time: float = 0.0
        self.badge_duration: float = 1.8
        self.badge_success: bool = True

    # ------------------------------------------------------------------
    # Trigger Helpers
    # ------------------------------------------------------------------

    def set_blush(self, intensity: float) -> None:
        self.target_blush = max(0.0, min(1.0, intensity))

    def spawn_hearts(self, origin_x: float, origin_y: float, count: int = 5) -> None:
        for _ in range(count):
            p = Particle(
                x=origin_x + random.uniform(-18, 18),
                y=origin_y + random.uniform(-6, 6),
                vx=random.uniform(-0.9, 0.9),
                vy=random.uniform(-1.9, -0.9),
                size=random.uniform(10.0, 18.0),
                decay=random.uniform(0.012, 0.024),
                color=QColor(255, random.randint(90, 140), random.randint(160, 200), 240),
                rotation=random.uniform(-22, 22),
                v_rot=random.uniform(-1.2, 1.2),
                kind="heart",
            )
            self.particles.append(p)

    def spawn_stars(self, origin_x: float, origin_y: float, count: int = 6) -> None:
        for _ in range(count):
            p = Particle(
                x=origin_x + random.uniform(-35, 35),
                y=origin_y + random.uniform(-25, 25),
                vx=random.uniform(-0.6, 0.6),
                vy=random.uniform(-0.9, 0.5),
                size=random.uniform(8.0, 15.0),
                decay=random.uniform(0.015, 0.032),
                color=QColor(255, 235, 80, 245),
                rotation=random.uniform(0, 360),
                v_rot=random.uniform(4.0, 9.0),
                kind="star",
            )
            self.particles.append(p)

    def spawn_sparks(self, origin_x: float, origin_y: float, count: int = 8) -> None:
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1.2, 3.2)
            p = Particle(
                x=origin_x,
                y=origin_y,
                vx=speed * math.cos(angle),
                vy=speed * math.sin(angle),
                size=random.uniform(4.0, 7.0),
                decay=random.uniform(0.03, 0.06),
                color=QColor("#A882FF"),
                kind="spark",
            )
            self.particles.append(p)

    def spawn_sweat_drops(self, origin_x: float, origin_y: float, count: int = 2) -> None:
        for _ in range(count):
            p = Particle(
                x=origin_x + random.uniform(-10, 10),
                y=origin_y + random.uniform(-4, 4),
                vx=random.uniform(0.4, 1.1),
                vy=random.uniform(0.9, 2.2),
                size=random.uniform(7.0, 12.0),
                decay=random.uniform(0.018, 0.035),
                color=QColor(90, 190, 255, 230),
                kind="sweat",
            )
            self.particles.append(p)

    def spawn_confetti(self, w: float, h: float, count: int = 40) -> None:
        colors = [
            QColor("#FF4081"), QColor("#00E676"), QColor("#FFD600"),
            QColor("#00B0FF"), QColor("#A882FF"), QColor("#FF6D00"),
            QColor("#FFFFFF")
        ]
        for _ in range(count):
            p = Particle(
                x=w / 2.0 + random.uniform(-w * 0.42, w * 0.42),
                y=h * 0.25 + random.uniform(-12, 15),
                vx=random.uniform(-2.8, 2.8),
                vy=random.uniform(-4.5, -1.2),
                size=random.uniform(5.0, 9.0),
                decay=random.uniform(0.008, 0.016),
                color=random.choice(colors),
                rotation=random.uniform(0, 360),
                v_rot=random.uniform(-9.0, 9.0),
                kind="confetti",
            )
            self.particles.append(p)

    def spawn_zzz(self, origin_x: float, origin_y: float) -> None:
        if random.random() < 0.16:
            p = Particle(
                x=origin_x + random.uniform(-6, 16),
                y=origin_y,
                vx=random.uniform(0.4, 0.9),
                vy=random.uniform(-0.95, -0.45),
                size=random.uniform(10.0, 17.0),
                decay=0.013,
                color=QColor(190, 210, 255, 215),
                kind="zzz",
            )
            self.particles.append(p)

    def trigger_feedback_badge(self, text: str = "Listo", success: bool = True) -> None:
        self.badge_active = True
        self.badge_text = text
        self.badge_time = 0.0
        self.badge_success = success

    # ------------------------------------------------------------------
    # Update Cycle (Called every frame at ~60 FPS)
    # ------------------------------------------------------------------

    def update(self, dt: float = 0.016) -> None:
        self.blush_intensity += (self.target_blush - self.blush_intensity) * 0.10

        alive: List[Particle] = []
        for p in self.particles:
            p.x += p.vx
            p.y += p.vy
            p.rotation += p.v_rot
            p.life -= p.decay

            if p.kind == "confetti":
                p.vy += 0.16
                p.vx *= 0.98
            elif p.kind == "sweat":
                p.vy += 0.07
            elif p.kind == "spark":
                p.vx *= 0.92
                p.vy *= 0.92

            if p.life > 0.0:
                alive.append(p)
        self.particles = alive

        if self.badge_active:
            self.badge_time += dt
            if self.badge_time >= self.badge_duration:
                self.badge_active = False

    # ------------------------------------------------------------------
    # Render Overlays
    # ------------------------------------------------------------------

    def render_blush(self, painter: QPainter, left_x: float, right_x: float, y: float, w: float = 26, h: float = 12) -> None:
        if self.blush_intensity <= 0.02:
            return

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        alpha = int(140 * self.blush_intensity)
        color = QColor(255, 100, 140, alpha)

        for cx in (left_x, right_x):
            rect = QRectF(cx - w / 2, y - h / 2, w, h)
            grad = QRadialGradient(rect.center(), w / 2)
            grad.setColorAt(0.0, color)
            grad.setColorAt(1.0, QColor(255, 100, 140, 0))
            painter.setBrush(grad)
            painter.drawEllipse(rect)

        painter.restore()

    def render_particles(self, painter: QPainter) -> None:
        if not self.particles:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for p in self.particles:
            alpha = int(255 * max(0.0, min(1.0, p.life)))
            c = QColor(p.color)
            c.setAlpha(alpha)

            painter.save()
            painter.translate(p.x, p.y)
            painter.rotate(p.rotation)

            if p.kind == "heart":
                self._draw_heart(painter, p.size, c)
            elif p.kind == "star":
                self._draw_star(painter, p.size, c)
            elif p.kind == "sweat":
                self._draw_sweat(painter, p.size, c)
            elif p.kind == "confetti":
                painter.setBrush(c)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(QRectF(-p.size / 2, -p.size / 4, p.size, p.size / 2))
            elif p.kind == "zzz":
                self._draw_zzz(painter, p.size, c)
            elif p.kind == "spark":
                painter.setBrush(c)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(-p.size / 2, -p.size / 2, p.size, p.size))
            else:
                painter.setBrush(c)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(-p.size / 2, -p.size / 2, p.size, p.size))

            painter.restore()

        painter.restore()

    def render_feedback_badge(self, painter: QPainter, rect: QRectF) -> None:
        if not self.badge_active:
            return

        t = self.badge_time / self.badge_duration
        if t < 0.2:
            scale = ease_out_back(t / 0.2)
            alpha = 1.0
        elif t > 0.8:
            scale = 1.0
            alpha = max(0.0, (1.0 - t) / 0.2)
        else:
            scale = 1.0
            alpha = 1.0

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        badge_w = 120.0
        badge_h = 32.0
        cx = rect.center().x()
        cy = rect.center().y()

        painter.translate(cx, cy)
        painter.scale(scale, scale)

        badge_rect = QRectF(-badge_w / 2, -badge_h / 2, badge_w, badge_h)

        bg_col = QColor("#0D111A")
        bg_col.setAlpha(int(235 * alpha))
        painter.setBrush(bg_col)

        border_col = QColor("#00E676" if self.badge_success else "#FF5252")
        border_col.setAlpha(int(240 * alpha))
        painter.setPen(QPen(border_col, 1.8))
        painter.drawRoundedRect(badge_rect, badge_h / 2, badge_h / 2)

        check_cx = badge_rect.left() + 20
        check_cy = badge_rect.center().y()
        painter.setPen(QPen(border_col, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        path = QPainterPath()
        path.moveTo(check_cx - 6, check_cy)
        path.lineTo(check_cx - 1, check_cy + 5)
        path.lineTo(check_cx + 7, check_cy - 5)
        painter.drawPath(path)

        text_col = QColor("#FFFFFF")
        text_col.setAlpha(int(245 * alpha))
        painter.setPen(text_col)
        font = painter.font()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        text_rect = QRectF(check_cx + 10, badge_rect.top(), badge_w - 38, badge_h)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.badge_text)

        painter.restore()

    def _draw_heart(self, painter: QPainter, size: float, color: QColor) -> None:
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        s = size / 2.0
        path.moveTo(0, s * 0.4)
        path.cubicTo(-s, -s * 0.6, -s * 1.2, s * 0.4, 0, s * 1.3)
        path.cubicTo(s * 1.2, s * 0.4, s, -s * 0.6, 0, s * 0.4)
        painter.drawPath(path)

    def _draw_star(self, painter: QPainter, size: float, color: QColor) -> None:
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        r_outer = size / 2.0
        r_inner = r_outer * 0.45
        path = QPainterPath()
        points = 4
        for i in range(points * 2):
            angle = i * (math.pi / points) - math.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)

    def _draw_sweat(self, painter: QPainter, size: float, color: QColor) -> None:
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        w = size * 0.6
        h = size
        path.moveTo(0, -h / 2)
        path.cubicTo(w / 2, -h * 0.1, w / 2, h / 2, 0, h / 2)
        path.cubicTo(-w / 2, h / 2, -w / 2, -h * 0.1, 0, -h / 2)
        painter.drawPath(path)

    def _draw_zzz(self, painter: QPainter, size: float, color: QColor) -> None:
        painter.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        s = size / 2.0
        path = QPainterPath()
        path.moveTo(-s * 0.6, -s * 0.7)
        path.lineTo(s * 0.6, -s * 0.7)
        path.lineTo(-s * 0.5, s * 0.7)
        path.lineTo(s * 0.6, s * 0.7)
        painter.drawPath(path)
