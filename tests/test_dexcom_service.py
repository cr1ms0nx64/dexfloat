from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from app.domain.reading import Trend
from app.services.polling import Credentials, ErrorKind, Poller, sensor_reading


class PollingTests(unittest.TestCase):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def raw(self, value, age=0):
        return SimpleNamespace(value=value * 18.0182, mmol_l=value,
                               datetime=self.now - timedelta(minutes=age), trend=4)

    def poller(self, client=None, **kwargs):
        return Poller(Credentials("user", "secret"), client=client, **kwargs)

    def test_sensor_delta_timestamp_and_repeated_poll(self):
        client = Mock()
        client.get_glucose_readings.return_value = [self.raw(6.3), self.raw(6.0, 5)]
        poller = self.poller(client)
        for _ in range(2):
            result = poller.poll()
            self.assertAlmostEqual(result.reading.delta_mmol, 0.3)
            self.assertEqual(result.reading.timestamp, self.now)
        client.get_glucose_readings.assert_called_with(minutes=15, max_count=2)

    def test_one_duplicate_and_no_value(self):
        self.assertIsNone(sensor_reading([self.raw(6)]).delta_mmol)
        self.assertIsNone(sensor_reading([self.raw(6), self.raw(6)]).delta_mmol)
        client = Mock()
        client.get_glucose_readings.return_value = []
        self.assertIs(self.poller(client).poll().error, ErrorKind.NO_DATA)

    def test_fallback_and_unknown(self):
        raw = SimpleNamespace(value=180.182, datetime=self.now, trend=8, trend_arrow="→")
        reading = sensor_reading([raw])
        self.assertAlmostEqual(reading.value_mmol, 10)
        self.assertIs(reading.trend, Trend.NOT_COMPUTABLE)

    def test_auth_error_blocks_all_further_logins(self):
        factory = Mock(side_effect=RuntimeError("account"))
        poller = self.poller(factory=factory, error_classifier=lambda exc: ErrorKind.AUTH)
        for _ in range(5):
            self.assertIs(poller.poll().error, ErrorKind.AUTH)
        factory.assert_called_once()

    def test_network_backoff_reset(self):
        client = Mock()
        client.get_glucose_readings.side_effect = OSError("offline")
        poller = self.poller(client, error_classifier=lambda exc: ErrorKind.NETWORK)
        self.assertEqual([poller.poll().retry_seconds for _ in range(7)],
                         [15, 30, 60, 120, 240, 300, 300])
        client.get_glucose_readings.side_effect = None
        client.get_glucose_readings.return_value = [self.raw(6)]
        self.assertIsNone(poller.poll().error)
        client.get_glucose_readings.side_effect = OSError("offline")
        self.assertEqual(poller.poll().retry_seconds, 15)

    def test_session_recreates_client_after_backoff(self):
        client = Mock()
        client.get_glucose_readings.side_effect = RuntimeError("session")
        factory = Mock(return_value=Mock(get_glucose_readings=Mock(return_value=[])))
        poller = self.poller(client, factory=factory, error_classifier=lambda exc: ErrorKind.SESSION)
        self.assertEqual(poller.poll().retry_seconds, 15)
        self.assertIs(poller.poll().error, ErrorKind.NO_DATA)
        factory.assert_called_once()
