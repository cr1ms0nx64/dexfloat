from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.domain.reading import GlucoseReading, Trend
from app.domain.state import DisplayState as S, classify


class StateTests(unittest.TestCase):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def state(self, value=6.0, trend=Trend.FLAT, age=timedelta(0)):
        return classify(GlucoseReading(value, self.now - age, trend), 4.5, 10, self.now)

    def test_no_data(self):
        self.assertIs(classify(None, 4.5, 10, self.now), S.NO_DATA)

    def test_boundaries(self):
        for value, state in [(3.099, S.URGENT_LOW), (3.1, S.LOW), (4.499, S.LOW),
                             (4.5, S.IN_RANGE), (4.501, S.IN_RANGE), (9.999, S.IN_RANGE),
                             (10, S.IN_RANGE), (10.001, S.HIGH)]:
            with self.subTest(value=value):
                self.assertIs(self.state(value), state)

    def test_every_trend(self):
        expected = [S.TREND_UNKNOWN, S.RISING_FAST, S.RISING, S.RISING, S.IN_RANGE,
                    S.FALLING, S.FALLING, S.FALLING_FAST, S.TREND_UNKNOWN, S.TREND_UNKNOWN]
        for trend, state in zip(Trend, expected):
            with self.subTest(trend=trend):
                self.assertIs(self.state(trend=trend), state)

    def test_exact_stale_boundary_and_future(self):
        self.assertIs(self.state(age=timedelta(minutes=10) - timedelta(microseconds=1)), S.IN_RANGE)
        self.assertIs(self.state(2, Trend.DOUBLE_DOWN, timedelta(minutes=10)), S.STALE)
        self.assertIs(self.state(age=timedelta(seconds=-1)), S.STALE)

    def test_priority(self):
        for value, trend, state in [(2, Trend.DOUBLE_DOWN, S.URGENT_LOW),
                                    (4, Trend.DOUBLE_DOWN, S.LOW),
                                    (12, Trend.DOUBLE_DOWN, S.FALLING_FAST),
                                    (12, Trend.DOUBLE_UP, S.HIGH),
                                    (12, Trend.NONE, S.HIGH)]:
            self.assertIs(self.state(value, trend), state)

    def test_dexcom_mapping_preserves_unknown_and_single(self):
        for trend in Trend:
            self.assertIs(Trend.from_dexcom(trend.value), trend)
        for value, expected in [("None", Trend.NONE), ("NotComputable", Trend.NOT_COMPUTABLE),
                                ("RateOutOfRange", Trend.RATE_OUT_OF_RANGE),
                                ("↑", Trend.SINGLE_UP), ("↓↓", Trend.DOUBLE_DOWN),
                                ("Flat", Trend.FLAT), ("unexpected", Trend.NONE), (999, Trend.NONE)]:
            self.assertIs(Trend.from_dexcom(value), expected)

    def test_invalid_readings_rejected(self):
        for value in (float("nan"), float("inf"), -1):
            with self.assertRaises(ValueError):
                GlucoseReading(value, self.now, Trend.FLAT)
        with self.assertRaises(ValueError):
            GlucoseReading(6, self.now.replace(tzinfo=None), Trend.FLAT)
