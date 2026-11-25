from __future__ import annotations

import configparser
import math
import os
import platform as platform  # Compatibility: rename tests patch the shared platform module.
import tempfile
from dataclasses import dataclass

from app.config import APPDATA_DIR, DEFAULT_HIGH, DEFAULT_LOW, LEGACY_SETTINGS_PATH, SETTINGS_PATH
from app.services.credentials import _fernet as _fernet, decrypt_password, encrypt_password


def _number(values, key, default, convert=float, minimum=None, maximum=None):
    try:
        value = convert(values.get(key, default))
        if not math.isfinite(value):
            return default
        if minimum is not None and value < minimum:
            return default
        if maximum is not None and value > maximum:
            return default
        return value
    except (TypeError, ValueError, OverflowError):
        return default


@dataclass
class SettingsStore:
    username: str = ""
    password: str = ""
    region_ous: bool = True
    region: str = "ous"
    low_threshold: float = DEFAULT_LOW
    high_threshold: float = DEFAULT_HIGH
    urgent_low_threshold: float = 3.1
    idle_timeout_seconds: int = 5
    idle_opacity_percent: int = 25
    x: int | None = None
    y: int | None = None

    def __post_init__(self) -> None:
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        self._config = configparser.ConfigParser(interpolation=None)
        source = SETTINGS_PATH if SETTINGS_PATH.exists() else LEGACY_SETTINGS_PATH
        try:
            self._config.read(source, encoding="utf-8-sig")
        except (configparser.Error, OSError, UnicodeError):
            self._config = configparser.ConfigParser(interpolation=None)
        self.load()

    def has_credentials(self) -> bool:
        return bool(self.username and self.password)

    def load(self) -> None:
        credentials = self._config["credentials"] if self._config.has_section("credentials") else {}
        settings = self._config["settings"] if self._config.has_section("settings") else {}
        position = self._config["position"] if self._config.has_section("position") else {}
        self.username = credentials.get("username", "")
        self.password = self._decrypt(credentials.get("password", ""))
        self.region = settings.get("region", "ous")
        if self.region not in {"us", "ous", "jp"}:
            self.region = "ous"
        self.region_ous = self.region == "ous"
        self.low_threshold = _number(settings, "low_threshold", DEFAULT_LOW, minimum=1, maximum=30)
        self.high_threshold = _number(settings, "high_threshold", DEFAULT_HIGH, minimum=1, maximum=30)
        if self.low_threshold >= self.high_threshold:
            self.low_threshold, self.high_threshold = DEFAULT_LOW, DEFAULT_HIGH
        self.urgent_low_threshold = _number(settings, "urgent_low_threshold", 3.1, minimum=1, maximum=self.low_threshold)
        if self.urgent_low_threshold > self.low_threshold:
            self.urgent_low_threshold = min(3.1, self.low_threshold)
        self.idle_timeout_seconds = _number(settings, "idle_timeout_seconds", 5, int, 2, 60)
        self.idle_opacity_percent = _number(settings, "idle_opacity_percent", 25, int, 5, 80)
        self.x = _number(position, "x", None, int)
        self.y = _number(position, "y", None, int)

    def save(self) -> None:
        password, password_format = encrypt_password(self.password)
        config = configparser.ConfigParser(interpolation=None)
        config["credentials"] = {"username": self.username, "password": password,
                                 "password_format": password_format}
        config["settings"] = {
            "region": self.region,
            "low_threshold": str(self.low_threshold),
            "high_threshold": str(self.high_threshold),
            "urgent_low_threshold": str(self.urgent_low_threshold),
            "idle_timeout_seconds": str(self.idle_timeout_seconds),
            "idle_opacity_percent": str(self.idle_opacity_percent),
        }
        config["position"] = {"x": "" if self.x is None else str(self.x),
                              "y": "" if self.y is None else str(self.y)}
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=APPDATA_DIR,
                                             delete=False, suffix=".tmp") as handle:
                temporary = handle.name
                config.write(handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, SETTINGS_PATH)
            self._config = config
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def save_position(self, x: int, y: int) -> None:
        self.x, self.y = x, y
        self.save()

    def _encrypt(self, value: str) -> str:
        return encrypt_password(value)[0]

    def _decrypt(self, value: str) -> str:
        kind = self._config.get("credentials", "password_format", fallback="fernet")
        return decrypt_password(value, kind)


def __getattr__(name):
    # Keep old imports working without loading Qt when only settings are needed.
    if name == "SettingsDialog":
        from app.ui.settings_dialog import SettingsDialog
        return SettingsDialog
    raise AttributeError(name)
