import configparser
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from app import autostart, settings
from app.services import credentials


class SettingsRenameTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(credentials, "is_windows", return_value=False))
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.current = root / "dexfloat" / "settings.ini"
        self.legacy = root / "dextop" / "settings.ini"
        for key, value in {
            "APPDATA_DIR": self.current.parent,
            "SETTINGS_PATH": self.current,
            "LEGACY_SETTINGS_PATH": self.legacy,
        }.items():
            self.stack.enter_context(patch.object(settings, key, value))
        self.stack.enter_context(patch.object(settings.platform, "node", return_value="test-device"))

    def write_settings(self, path, context, username="example-user"):
        path.parent.mkdir(parents=True, exist_ok=True)
        token = settings._fernet(context).encrypt(b"example-password").decode("ascii")
        path.write_text(
            f"[credentials]\nusername={username}\npassword={token}\n"
            "[settings]\nlow_threshold=4.8\nregion=us\n"
            "[position]\nx=120\ny=250\n", encoding="utf-8"
        )

    def test_legacy_read_and_new_save_preserve_access_and_position(self):
        self.write_settings(self.legacy, b"dextop")
        original = self.legacy.read_bytes()
        store = settings.SettingsStore()
        self.assertEqual((store.username, store.password), ("example-user", "example-password"))
        self.assertEqual((store.x, store.y, store.low_threshold, store.region_ous), (120, 250, 4.8, False))
        self.assertFalse(self.current.exists())
        store.save()
        config = configparser.ConfigParser()
        config.read(self.current, encoding="utf-8")
        plaintext = settings._fernet().decrypt(config["credentials"]["password"].encode("ascii"))
        self.assertEqual(plaintext, b"example-password")
        self.assertEqual(self.legacy.read_bytes(), original)
        self.assertEqual(settings.SettingsStore().password, store.password)

    def test_current_settings_take_priority_over_legacy(self):
        self.write_settings(self.legacy, b"dextop", "legacy-user")
        self.write_settings(self.current, b"dexfloat", "current-user")
        self.assertEqual(settings.SettingsStore().username, "current-user")

    def test_legacy_key_with_empty_hostname_still_decrypts(self):
        with patch.object(settings.platform, "node", return_value=""):
            self.write_settings(self.legacy, b"dextop")
            self.assertEqual(settings.SettingsStore().password, "example-password")

    def test_invalid_ciphertext_requests_fresh_credentials(self):
        store = settings.SettingsStore()
        self.assertEqual(store._decrypt("invalid-token"), "")
        self.assertEqual(store._decrypt(""), "")


class FakeRegistry:
    HKEY_CURRENT_USER = KEY_READ = KEY_SET_VALUE = REG_SZ = 1

    def __init__(self, values):
        self.values = dict(values)

    def OpenKey(self, *args):
        return self

    CreateKeyEx = OpenKey

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


class AutostartRenameTests(unittest.TestCase):
    def test_enabled_legacy_entry_is_retargeted_and_migration_is_idempotent(self):
        registry = FakeRegistry({autostart.LEGACY_RUN_VALUE_NAME: '"old/Dextop.exe"', "OtherApp": "keep"})
        with patch.object(autostart, "winreg", registry), patch.object(autostart, "current_launch_command", return_value='"new/Dexfloat.exe"'):
            autostart.migrate_legacy_autostart()
            self.assertTrue(autostart.is_autostart_enabled())
            self.assertEqual(registry.values, {"Dexfloat": '"new/Dexfloat.exe"', "OtherApp": "keep"})
            autostart.migrate_legacy_autostart()
            self.assertEqual(len(registry.values), 2)
            autostart.set_autostart_enabled(False)
            self.assertEqual(registry.values, {"OtherApp": "keep"})

    def test_disabled_autostart_stays_disabled(self):
        registry = FakeRegistry({"OtherApp": "keep"})
        with patch.object(autostart, "winreg", registry):
            autostart.migrate_legacy_autostart()
            self.assertFalse(autostart.is_autostart_enabled())
            self.assertEqual(registry.values, {"OtherApp": "keep"})

    def test_launch_command_uses_renamed_source_and_frozen_executable(self):
        with patch.object(autostart.sys, "frozen", False, create=True):
            command = autostart.current_launch_command()
            self.assertIn("Dexfloat.py", command)
            self.assertNotIn("Dextop.py", command)
        with patch.object(autostart.sys, "frozen", True, create=True), patch.object(autostart.sys, "executable", "C:/Apps/Dexfloat.exe"):
            self.assertEqual(autostart.current_launch_command(), '"C:/Apps/Dexfloat.exe"')


if __name__ == "__main__":
    unittest.main()

