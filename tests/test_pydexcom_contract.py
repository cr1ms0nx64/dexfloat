from __future__ import annotations

import inspect
import unittest
from datetime import datetime
from importlib.metadata import version
from unittest.mock import patch

from pydexcom import Dexcom
from pydexcom.const import DEXCOM_TREND_DIRECTIONS, Region
from pydexcom.glucose_reading import GlucoseReading

from app.services.polling import Credentials, create_client


class PydexcomContractTests(unittest.TestCase):
    def test_pinned_constructor_signature_and_regions(self):
        self.assertEqual(version("pydexcom"), "0.5.1")
        parameters = inspect.signature(Dexcom).parameters
        self.assertEqual(parameters["username"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertIn("region", parameters)
        self.assertNotIn("ous", parameters)
        self.assertEqual({region.value for region in Region}, {"us", "ous", "jp"})
        self.assertEqual(list(DEXCOM_TREND_DIRECTIONS.values()), list(range(10)))

    def test_real_reading_has_sensor_datetime_and_mmol_attribute(self):
        raw = GlucoseReading({"Value": 100, "Trend": "SingleUp", "DT": "Date(1700000000000+0000)"})
        self.assertIsInstance(raw.datetime, datetime)
        self.assertIsNotNone(raw.datetime.utcoffset())
        self.assertEqual(raw.mmol_l, round(100 * 0.0555, 1))
        self.assertEqual((raw.trend, raw.trend_arrow, raw.trend_direction), (2, "↑", "SingleUp"))

    def test_timeout_adapter_is_installed_before_first_login(self):
        def fake_login(client):
            adapter = client._session.get_adapter("https://example.invalid")
            self.assertEqual(adapter.max_retries.total, 0)
            with patch("requests.adapters.HTTPAdapter.send", return_value=object()) as send:
                adapter.send(object(), timeout=None)
                self.assertEqual(send.call_args.kwargs["timeout"], (5, 15))
        with patch.object(Dexcom, "_get_session", fake_login):
            client = create_client(Credentials("user", "secret", "ous"))
            self.assertEqual(client.username, "user")
