from __future__ import annotations

from datetime import datetime, timezone
from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import (
    QBitmap,
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from app.config import (
    BORDER_ALPHA,
    CARD_HEIGHT,
    CARD_RADIUS,
    CARD_WIDTH,
    CARD_X,
    CARD_Y,
    FONTS,
    STATUS_ALPHA,
    SURFACE,
    UNIT_ALPHA,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from app.domain.reading import GlucoseReading, Trend
from app.domain.state import DisplayState, classify
from app.platform.win32 import extend_frame, set_click_through
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import ARROWS, CRITICAL, NEUTRAL, STYLES
from app.ui.tray import TrayController


class GlucoseWidget(QWidget):
    def __init__(self, settings, service) -> None:
        super().__init__()
        self._settings = settings
        self._service = service
        self._reading: GlucoseReading | None = None
        self._drag_offset: QPoint | None = None
        self._drag_enabled = False
        self._arrow_bounce_offset = 0.0
        self._font_families = self._load_fonts()
        self._fonts = {}
        self._metrics = {}
        self._state = DisplayState.NO_DATA
        self._error_message = "Verbinde …"
        self._settings_dialog = None
        self._tray = TrayController(self, service)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        if self._settings.x is not None and self._settings.y is not None:
            self.move(self._settings.x, self._settings.y)

        self._extend_frame_into_client_area()
        self._apply_card_mask()
        self._sync_window_interaction()

        self._service.reading_changed.connect(self._update_reading)
        self._service.error_changed.connect(self._update_error)

        self._arrow_animation = QPropertyAnimation(self, b"arrowBounceOffset")
        self._arrow_animation.setDuration(850)
        self._arrow_animation.setStartValue(0.0)
        self._arrow_animation.setKeyValueAt(0.5, 4.0)
        self._arrow_animation.setEndValue(0.0)
        self._arrow_animation.setLoopCount(-1)
        self._arrow_animation.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.setInterval(self._settings.idle_timeout_seconds * 1000)
        self.idle_timer.timeout.connect(self._fade_out)
        self.idle_timer.start()

        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.setWindowOpacity(1.0)
        self._age_timer = QTimer(self)
        self._age_timer.setInterval(1000)
        self._age_timer.timeout.connect(self._refresh_state)
        self._age_timer.start()
        QGuiApplication.instance().screenRemoved.connect(self._screen_removed)
        self._ensure_visible()

    @pyqtProperty(float)
    def arrowBounceOffset(self) -> float:
        return self._arrow_bounce_offset

    @arrowBounceOffset.setter
    def arrowBounceOffset(self, value: float) -> None:
        self._arrow_bounce_offset = value
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._extend_frame_into_client_area()
        self._apply_card_mask()
        self._sync_window_interaction()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        active_color = QColor(STYLES[self._state].color)
        card = QRectF(CARD_X, CARD_Y, CARD_WIDTH, CARD_HEIGHT)

        self._draw_outer_glow(painter, card, active_color)
        self._draw_card(painter, card)
        self._draw_ambient_blob(painter, card, active_color)
        self._draw_accent_bar(painter, card, active_color)
        self._draw_text(painter, card, active_color)
        self._draw_arrow_area(painter, card, active_color)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if not self._drag_enabled:
            event.ignore()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._fade_in()
            self.idle_timer.start()
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_enabled and self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_enabled and event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            self._settings.save_position(self.x(), self.y())
            event.accept()
        else:
            event.ignore()

    def _draw_outer_glow(self, painter: QPainter, card: QRectF, active_color: QColor) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        for expand, opacity in ((5, 0.025), (9, 0.02)):
            color = QColor(active_color)
            color.setAlphaF(opacity)
            painter.setBrush(color)
            painter.drawRoundedRect(card.adjusted(-expand, -expand, expand, expand), CARD_RADIUS + expand, CARD_RADIUS + expand)

    def _draw_card(self, painter: QPainter, card: QRectF) -> None:
        painter.setBrush(QBrush(QColor(SURFACE)))
        painter.setPen(QPen(QColor(255, 255, 255, BORDER_ALPHA), 1))
        painter.drawRoundedRect(card, CARD_RADIUS, CARD_RADIUS)
        if self._state in {DisplayState.LOW, DisplayState.URGENT_LOW, DisplayState.HIGH}:
            style = Qt.PenStyle.DashLine if self._state is DisplayState.HIGH else Qt.PenStyle.SolidLine
            painter.setPen(QPen(QColor(STYLES[self._state].color), 2, style))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(card.adjusted(1, 1, -1, -1), CARD_RADIUS, CARD_RADIUS)

    def _draw_ambient_blob(self, painter: QPainter, card: QRectF, active_color: QColor) -> None:
        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(card, CARD_RADIUS, CARD_RADIUS)
        painter.setClipPath(clip)
        painter.setPen(Qt.PenStyle.NoPen)

        center = QPointF(card.right() - 24, card.top() + 31)
        gradient = QRadialGradient(center, 82)
        inner = QColor(active_color)
        inner.setAlphaF(0.24)
        mid = QColor(active_color)
        mid.setAlphaF(0.11)
        outer = QColor(active_color)
        outer.setAlpha(0)
        gradient.setColorAt(0.0, inner)
        gradient.setColorAt(0.48, mid)
        gradient.setColorAt(1.0, outer)

        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QRectF(card.right() - 108, card.top() - 44, 156, 132))
        painter.restore()

    def _draw_accent_bar(self, painter: QPainter, card: QRectF, active_color: QColor) -> None:
        bar_width = 3
        bar_height = card.height() * 0.6
        bar_x = card.x()
        bar_y = card.y() + (card.height() - bar_height) / 2

        painter.setPen(Qt.PenStyle.NoPen)
        for expand, opacity in ((6, 0.03), (4, 0.08), (2, 0.15)):
            color = QColor(active_color)
            color.setAlphaF(opacity)
            painter.setBrush(color)
            painter.drawRoundedRect(
                QRectF(bar_x - expand, bar_y - expand, bar_width + expand, bar_height + expand * 2),
                2,
                2,
            )

        painter.setBrush(QColor(active_color))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_width, bar_height), 2, 2)

    def _draw_text(self, painter: QPainter, card: QRectF, active_color: QColor) -> None:
        value = self._value_text()
        label = self._age_label()
        text_x = card.x() + 18

        label_font = self._font("mono_regular", 9)
        value_font = self._font("display", 44, extra_bold=True)
        unit_font = self._font("mono_light", 10)

        value_fm = self._font_metrics("display", 44, True)
        label_baseline = card.y() + 24
        value_baseline = card.y() + 58

        painter.setFont(label_font)
        painter.setPen(QColor(255, 255, 255, STATUS_ALPHA))
        painter.drawText(QPointF(text_x, label_baseline), label)
        marker = STYLES[self._state].marker
        if marker:
            painter.setPen(QColor(active_color))
            painter.drawText(QPointF(card.right() - 83, label_baseline), marker)

        glow_color = QColor(active_color)
        glow_color.setAlphaF(0.15)
        painter.setFont(value_font)
        painter.setPen(glow_color)
        painter.drawText(QPointF(text_x, value_baseline + 2), value)

        painter.setPen(QColor(active_color))
        painter.drawText(QPointF(text_x, value_baseline), value)
        if self._state is DisplayState.STALE:
            painter.setPen(QPen(QColor(NEUTRAL), 2))
            painter.drawLine(QPointF(text_x, value_baseline - 15),
                             QPointF(text_x + value_fm.horizontalAdvance(value), value_baseline - 15))

        painter.setFont(unit_font)
        painter.setPen(QColor(255, 255, 255, UNIT_ALPHA))
        unit_x = text_x + value_fm.horizontalAdvance(value) + 5
        painter.drawText(QPointF(unit_x, value_baseline), "mmol/L")

    def _draw_arrow_area(self, painter: QPainter, card: QRectF, active_color: QColor) -> None:
        circle_radius = 20
        circle_cx = card.right() - 18 - circle_radius
        circle_cy = card.top() + card.height() / 2 - 5

        circle_color = QColor(active_color)
        circle_color.setAlphaF(0.12)
        painter.setBrush(circle_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(circle_cx, circle_cy), circle_radius, circle_radius)

        bounce = self._arrow_bounce_offset
        if self._state not in {DisplayState.STALE, DisplayState.NO_DATA}:
            self._draw_arrow(painter, QPointF(circle_cx, circle_cy + bounce), active_color)

        delta = self._delta_text()
        delta_font = self._font("mono_regular", 9)
        delta_fm = self._font_metrics("mono_regular", 9)
        delta_color = QColor(active_color)
        delta_color.setAlphaF(0.55)
        painter.setFont(delta_font)
        painter.setPen(delta_color)
        painter.drawText(QPointF(circle_cx - delta_fm.horizontalAdvance(delta) / 2, circle_cy + 33), delta)

    def _draw_arrow(self, painter: QPainter, center: QPointF, active_color: QColor) -> None:
        kind = ARROWS[self._reading.trend] if self._reading else "unknown"
        if kind == "unknown":
            painter.setFont(self._font("mono_regular", 20))
            painter.setPen(QColor(NEUTRAL))
            painter.drawText(QPointF(center.x() - 6, center.y() + 7), "?")
            return
        painter.setPen(QPen(QColor(active_color), 2.5, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx, cy = center.x(), center.y()
        if kind in {"up", "down", "double_up", "double_down"}:
            direction = -1 if kind.endswith("up") else 1
            for offset in ((-5, 5) if kind.startswith("double") else (0,)):
                x = cx + offset
                painter.drawLine(QPointF(x, cy - direction * 10), QPointF(x, cy + direction * 10))
                painter.drawLine(QPointF(x - 4, cy + direction * 5), QPointF(x, cy + direction * 10))
                painter.drawLine(QPointF(x + 4, cy + direction * 5), QPointF(x, cy + direction * 10))
        elif kind in {"diagonal_up", "diagonal_down"}:
            direction = -1 if kind.endswith("up") else 1
            painter.drawLine(QPointF(cx - 9, cy - direction * 9), QPointF(cx + 9, cy + direction * 9))
            painter.drawLine(QPointF(cx + 1, cy + direction * 9), QPointF(cx + 9, cy + direction * 9))
            painter.drawLine(QPointF(cx + 9, cy + direction), QPointF(cx + 9, cy + direction * 9))
        else:
            painter.drawLine(QPointF(cx - 10, cy), QPointF(cx + 10, cy))
            painter.drawLine(QPointF(cx + 4, cy - 6), QPointF(cx + 10, cy))
            painter.drawLine(QPointF(cx + 4, cy + 6), QPointF(cx + 10, cy))

    def _open_settings(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dialog = SettingsDialog(self._settings, self._service, self)
        self._settings_dialog = dialog
        dialog.finished.connect(self._settings_closed)
        dialog.open()

    def _settings_closed(self, *_):
        self._settings_dialog = None
        self.idle_timer.setInterval(self._settings.idle_timeout_seconds * 1000)
        self._refresh_state()
        self._fade_in()

    def _update_reading(self, reading: GlucoseReading | None) -> None:
        self._reading = reading
        self._refresh_state()

    def _update_error(self, kind, message: str) -> None:
        self._error_message = message
        self.update()

    def _refresh_state(self) -> None:
        state = classify(self._reading, self._settings.low_threshold, self._settings.high_threshold,
                         datetime.now(timezone.utc), urgent_low=self._settings.urgent_low_threshold)
        changed = state is not self._state
        self._state = state
        double = self._reading and self._reading.trend in {Trend.DOUBLE_UP, Trend.DOUBLE_DOWN}
        if double and state not in {DisplayState.STALE, DisplayState.NO_DATA}:
            if self._arrow_animation.state() != QPropertyAnimation.State.Running:
                self._arrow_animation.start()
        else:
            self._arrow_animation.stop()
            self._arrow_bounce_offset = 0.0
        if changed or state in CRITICAL:
            self._fade_in()
        self.update()

    def _value_text(self) -> str:
        return f"{self._reading.value_mmol:.1f}" if self._reading else "--"

    def _delta_text(self) -> str:
        if not self._reading or self._reading.delta_mmol is None or self._state is DisplayState.STALE:
            return "–"
        delta = self._reading.delta_mmol
        if abs(delta) < 0.05:
            return "± 0.0"
        return f"+{delta:.1f}" if delta > 0 else f"−{abs(delta):.1f}"

    def _age_label(self) -> str:
        if self._reading is None:
            return "GLUKOSE · KEINE DATEN" if self._error_message != "Verbinde …" else "GLUKOSE · VERBINDE …"
        minutes = max(0, int((datetime.now(timezone.utc) - self._reading.timestamp).total_seconds() // 60))
        return "GLUKOSE · JETZT" if minutes < 1 else f"GLUKOSE · VOR {minutes} MIN"

    def _screen_removed(self, *_):
        QTimer.singleShot(0, self._ensure_visible)

    def _ensure_visible(self):
        if any(screen.availableGeometry().contains(self.frameGeometry()) for screen in QGuiApplication.screens()):
            return
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.move(screen.availableGeometry().center() - self.rect().center())
            try:
                self._settings.save_position(self.x(), self.y())
            except OSError:
                pass

    def _fade_out(self) -> None:
        if self._state in CRITICAL:
            self.fade_anim.stop()
            self.setWindowOpacity(1.0)
            return
        self.fade_anim.stop()
        self.fade_anim.setDuration(800)
        self.fade_anim.setStartValue(self.windowOpacity())
        self.fade_anim.setEndValue(self._settings.idle_opacity_percent / 100)
        self.fade_anim.start()

    def _fade_in(self) -> None:
        if self._state in CRITICAL:
            self.fade_anim.stop()
            self.setWindowOpacity(1.0)
            self.idle_timer.stop()
            return
        self.fade_anim.stop()
        self.fade_anim.setDuration(200)
        self.fade_anim.setStartValue(self.windowOpacity())
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()
        self.idle_timer.start()

    def _font(self, key: str, size: int, extra_bold: bool = False) -> QFont:
        cache_key = (key, size, extra_bold)
        if cache_key in self._fonts:
            return self._fonts[cache_key]
        spec = FONTS[key]
        family = self._font_families.get(key) or spec.family or spec.fallback
        font = QFont(family)
        font.setPixelSize(size)
        if extra_bold:
            font.setWeight(QFont.Weight.ExtraBold)
        elif key.startswith("mono"):
            font.setWeight(QFont.Weight.Light if key.endswith("light") else QFont.Weight.Normal)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        self._fonts[cache_key] = font
        return font

    def _font_metrics(self, key, size, extra_bold=False):
        cache_key = (key, size, extra_bold)
        if cache_key not in self._metrics:
            self._metrics[cache_key] = QFontMetrics(self._font(key, size, extra_bold))
        return self._metrics[cache_key]

    def _load_fonts(self) -> dict[str, str]:
        from app.config import ASSETS_DIR
        families = {}
        for key, spec in FONTS.items():
            font_path = ASSETS_DIR / "fonts" / spec.file_name
            font_id = QFontDatabase.addApplicationFont(str(font_path)) if font_path.exists() else -1
            loaded = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            families[key] = loaded[0] if loaded else spec.fallback
        return families

    def _extend_frame_into_client_area(self):
        extend_frame(int(self.winId()))

    def _sync_window_interaction(self):
        set_click_through(int(self.winId()), not self._drag_enabled)

    def set_drag_enabled(self, enabled):
        self._drag_enabled = enabled
        self._drag_offset = None
        if self._tray.drag.isChecked() != enabled:
            self._tray.drag.setChecked(enabled)
        self._sync_window_interaction()
        if enabled:
            self._fade_in()

    def _apply_card_mask(self) -> None:
        mask = QBitmap(self.size())
        mask.fill(Qt.GlobalColor.color0)
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.GlobalColor.color1)
        painter.setPen(Qt.PenStyle.NoPen)
        glow_bounds = QRectF(CARD_X, CARD_Y, CARD_WIDTH, CARD_HEIGHT).adjusted(-18, -18, 18, 18)
        painter.drawRoundedRect(glow_bounds, CARD_RADIUS + 18, CARD_RADIUS + 18)
        painter.end()
        self.setMask(mask)

