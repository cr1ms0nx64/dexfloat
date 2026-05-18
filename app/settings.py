from __future__ import annotations

import base64
import configparser
import hashlib
import platform
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.config import APPDATA_DIR, DEFAULT_HIGH, DEFAULT_LOW, SETTINGS_PATH


def _fernet() -> Fernet:
    seed = platform.node().encode("utf-8", errors="ignore") or b"dextop"
    digest = hashlib.sha256(seed + b":dextop").digest()
    return Fernet(base64.urlsafe_b64encode(digest))


@dataclass
class SettingsStore:
    username: str = ""
    password: str = ""
    region_ous: bool = True
    low_threshold: float = DEFAULT_LOW
    high_threshold: float = DEFAULT_HIGH
    idle_timeout_seconds: int = 5
    idle_opacity_percent: int = 25
    x: int | None = None
    y: int | None = None

    def __post_init__(self) -> None:
        APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        self._config = configparser.ConfigParser()
        self._config.read(SETTINGS_PATH, encoding="utf-8")
        self.load()

    def has_credentials(self) -> bool:
        return bool(self.username and self.password)

    def load(self) -> None:
        credentials = self._config["credentials"] if self._config.has_section("credentials") else {}
        settings = self._config["settings"] if self._config.has_section("settings") else {}
        position = self._config["position"] if self._config.has_section("position") else {}

        self.username = credentials.get("username", "")
        self.password = self._decrypt(credentials.get("password", ""))
        self.region_ous = settings.get("region", "ous") == "ous"
        self.low_threshold = float(settings.get("low_threshold", DEFAULT_LOW))
        self.high_threshold = float(settings.get("high_threshold", DEFAULT_HIGH))
        self.idle_timeout_seconds = int(settings.get("idle_timeout_seconds", 5))
        self.idle_opacity_percent = int(settings.get("idle_opacity_percent", 25))
        self.x = int(position["x"]) if position.get("x", "").strip() else None
        self.y = int(position["y"]) if position.get("y", "").strip() else None

    def save(self) -> None:
        self._config["credentials"] = {
            "username": self.username,
            "password": self._encrypt(self.password),
        }
        self._config["settings"] = {
            "region": "ous" if self.region_ous else "us",
            "low_threshold": str(self.low_threshold),
            "high_threshold": str(self.high_threshold),
            "idle_timeout_seconds": str(self.idle_timeout_seconds),
            "idle_opacity_percent": str(self.idle_opacity_percent),
        }
        self._config["position"] = {
            "x": "" if self.x is None else str(self.x),
            "y": "" if self.y is None else str(self.y),
        }
        with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
            self._config.write(handle)

    def save_position(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self.save()

    def _encrypt(self, value: str) -> str:
        return _fernet().encrypt(value.encode("utf-8")).decode("ascii") if value else ""

    def _decrypt(self, value: str) -> str:
        if not value:
            return ""
        try:
            return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError):
            return ""


class SettingsDialog(QDialog):
    def __init__(self, settings: SettingsStore, service, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._service = service
        self._last_error = ""
        self.setWindowTitle("Dextop Settings")
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._username = QLineEdit(settings.username)
        self._password = QLineEdit(settings.password)
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._region = QCheckBox("Outside US / Europe")
        self._region.setChecked(settings.region_ous)
        self._low = QDoubleSpinBox()
        self._low.setRange(1.0, 30.0)
        self._low.setDecimals(1)
        self._low.setSingleStep(0.1)
        self._low.setValue(settings.low_threshold)
        self._high = QDoubleSpinBox()
        self._high.setRange(1.0, 30.0)
        self._high.setDecimals(1)
        self._high.setSingleStep(0.1)
        self._high.setValue(settings.high_threshold)
        self._idle_timeout = QDoubleSpinBox()
        self._idle_timeout.setRange(2, 60)
        self._idle_timeout.setDecimals(0)
        self._idle_timeout.setSingleStep(1)
        self._idle_timeout.setValue(settings.idle_timeout_seconds)
        self._idle_opacity = QDoubleSpinBox()
        self._idle_opacity.setRange(5, 80)
        self._idle_opacity.setDecimals(0)
        self._idle_opacity.setSingleStep(5)
        self._idle_opacity.setValue(settings.idle_opacity_percent)

        form.addRow("Dexcom username", self._username)
        form.addRow("Password", self._password)
        form.addRow("Region", self._region)
        form.addRow("Low threshold", self._low)
        form.addRow("High threshold", self._high)
        form.addRow("Idle timeout (seconds)", self._idle_timeout)
        form.addRow("Idle opacity (%)", self._idle_opacity)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, alignment=Qt.AlignmentFlag.AlignRight)
        service.error_changed.connect(self._capture_error)

    def _accept(self) -> None:
        if self._apply():
            self.accept()

    def _apply(self) -> bool:
        if self._low.value() >= self._high.value():
            QMessageBox.warning(self, "Invalid thresholds", "Low threshold must be below high threshold.")
            return False
        if not self._username.text().strip() or not self._password.text():
            QMessageBox.warning(self, "Missing credentials", "Please enter your Dexcom username and password.")
            return False
        self._settings.username = self._username.text().strip()
        self._settings.password = self._password.text()
        self._settings.region_ous = self._region.isChecked()
        self._settings.low_threshold = self._low.value()
        self._settings.high_threshold = self._high.value()
        self._settings.idle_timeout_seconds = int(self._idle_timeout.value())
        self._settings.idle_opacity_percent = int(self._idle_opacity.value())
        self._last_error = ""
        if not self._service.reinitialize():
            QMessageBox.warning(
                self,
                "Dexcom login failed",
                self._last_error or "Dexcom rejected these credentials. Please check username, password and region.",
            )
            return False
        self._settings.save()
        self._service.refresh_now()
        return True

    def _capture_error(self, message: str) -> None:
        self._last_error = message
