from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from app.domain.reading import GlucoseReading, Trend
from app.domain.state import DisplayState
from app.ui.widget import GlucoseWidget


class Service(QObject):
    reading_changed = pyqtSignal(object)
    error_changed = pyqtSignal(object, str)


class WidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings = SimpleNamespace(x=0, y=0, low_threshold=4.5, high_threshold=10,
                                        urgent_low_threshold=3.1, idle_timeout_seconds=5,
                                        idle_opacity_percent=25, save_position=Mock())
        self.service = Service()
        for name in ("TrayController", "extend_frame", "set_click_through"):
            patcher = patch("app.ui.widget." + name)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.widget = GlucoseWidget(self.settings, self.service)
        self.addCleanup(self.widget.deleteLater)

    def reading(self, trend=Trend.FLAT, value=6, age=0, delta=None):
        return GlucoseReading(value, datetime.now(timezone.utc) - timedelta(minutes=age), trend, delta)

    def test_clock_ages_value_without_new_poll(self):
        self.widget._update_reading(self.reading(age=9))
        self.assertIn("9", self.widget._age_label())
        future = datetime.now(timezone.utc) + timedelta(minutes=2)
        with patch("app.ui.widget.datetime") as clock:
            clock.now.return_value = future
            self.widget._refresh_state()
        self.assertIs(self.widget._state, DisplayState.STALE)
        self.widget._fade_out()
        self.assertEqual(self.widget.windowOpacity(), 1)

    def test_critical_states_never_dim(self):
        for reading in (None, self.reading(value=2.5), self.reading(value=4),
                        self.reading(trend=Trend.DOUBLE_DOWN), self.reading(age=11)):
            self.widget._update_reading(reading)
            self.widget._fade_out()
            self.assertEqual(self.widget.windowOpacity(), 1)

    def test_unknown_and_double_arrows(self):
        from app.ui.theme import ARROWS
        for trend in (Trend.NONE, Trend.NOT_COMPUTABLE, Trend.RATE_OUT_OF_RANGE):
            self.widget._update_reading(self.reading(trend=trend))
            self.assertIs(self.widget._state, DisplayState.TREND_UNKNOWN)
            self.assertEqual(ARROWS[trend], "unknown")
        self.assertNotEqual(ARROWS[Trend.SINGLE_UP], ARROWS[Trend.DOUBLE_UP])

    def test_delta_has_one_direction(self):
        for delta, expected in [(None, "–"), (0, "± 0.0"), (0.3, "+0.3"), (-0.3, "−0.3")]:
            self.widget._update_reading(self.reading(delta=delta))
            self.assertEqual(self.widget._delta_text(), expected)
