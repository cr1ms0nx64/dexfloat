from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from app import settings


class SettingsTests(unittest.TestCase):
    def test_corrupt_values_and_percent_username(self):
        with tempfile.TemporaryDirectory() as root, ExitStack() as stack:
            path = Path(root) / "settings.ini"
            for name, value in [("APPDATA_DIR", Path(root)), ("SETTINGS_PATH", path),
                                ("LEGACY_SETTINGS_PATH", Path(root) / "legacy.ini")]:
                stack.enter_context(patch.object(settings, name, value))
            path.write_text("[credentials]\nusername=100%user\n[settings]\nlow_threshold=abc\nhigh_threshold=nan\nurgent_low_threshold=inf\nidle_timeout_seconds=-1\nregion=invalid\n[position]\nx=oops\ny=\n")
            store = settings.SettingsStore()
            self.assertEqual(store.username, "100%user")
            self.assertEqual((store.low_threshold, store.high_threshold, store.urgent_low_threshold), (4.5, 10, 3.1))
            self.assertEqual((store.x, store.y, store.region, store.idle_timeout_seconds), (None, None, "ous", 5))

    def test_malformed_ini_does_not_crash(self):
        with tempfile.TemporaryDirectory() as root, patch.object(settings, "APPDATA_DIR", Path(root)), patch.object(settings, "SETTINGS_PATH", Path(root) / "settings.ini"):
            settings.SETTINGS_PATH.write_text("not an ini\n")
            self.assertFalse(settings.SettingsStore().has_credentials())
