from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydexcom import Dexcom
from pydexcom import errors as dexcom_errors
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.config import DEFAULT_POLL_SECONDS, MMOL_FACTOR


@dataclass(frozen=True)
class GlucoseReading:
    value_mmol: float
    delta_mmol: float
    trend_arrow: str
    failed: bool = False


class DexcomService(QObject):
    reading_changed = pyqtSignal(object)
    error_changed = pyqtSignal(str)

    def __init__(self, settings) -> None:
        super().__init__()
        self._settings = settings
        self._dexcom: Optional[Dexcom] = None
        self._last_reading: Optional[GlucoseReading] = None
        self._last_raw_value: Optional[int] = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_now)

    @property
    def last_reading(self) -> Optional[GlucoseReading]:
        return self._last_reading

    def start(self) -> bool:
        if not self.reinitialize():
            return False
        self._timer.start(DEFAULT_POLL_SECONDS * 1000)
        self.refresh_now()
        return True

    def stop(self) -> None:
        self._timer.stop()

    def reinitialize(self) -> bool:
        self._dexcom = None
        if not self._settings.has_credentials():
            self.error_changed.emit("Dexcom username and password are required.")
            return False
        try:
            self._dexcom = Dexcom(
                self._settings.username,
                self._settings.password,
                ous=self._settings.region_ous,
            )
            return True
        except dexcom_errors.AccountError as exc:
            self.error_changed.emit(f"Dexcom login failed: {exc}")
        except dexcom_errors.SessionError as exc:
            self.error_changed.emit(f"Dexcom session failed: {exc}")
        except dexcom_errors.ArgumentError as exc:
            self.error_changed.emit(f"Dexcom settings failed: {exc}")
        except Exception as exc:
            self.error_changed.emit(f"Dexcom connection failed: {exc}")
        self._dexcom = None
        return False

    def refresh_now(self) -> None:
        if self._dexcom is None:
            if self._settings.has_credentials():
                if not self.reinitialize():
                    return
            else:
                return

        try:
            reading = self._dexcom.get_current_glucose_reading()
            raw_value = int(reading.value)
            value_mmol = raw_value / MMOL_FACTOR
            delta_mmol = 0.0 if self._last_raw_value is None else (raw_value - self._last_raw_value) / MMOL_FACTOR
            self._last_raw_value = raw_value
            trend_arrow = getattr(reading, "trend_arrow", "") or self._arrow_from_trend(getattr(reading, "trend", 0))
            self._last_reading = GlucoseReading(value_mmol=value_mmol, delta_mmol=delta_mmol, trend_arrow=trend_arrow)
            self.reading_changed.emit(self._last_reading)
        except Exception as exc:
            self.error_changed.emit(str(exc))
            if self._last_reading is not None:
                failed = GlucoseReading(
                    value_mmol=self._last_reading.value_mmol,
                    delta_mmol=self._last_reading.delta_mmol,
                    trend_arrow=self._last_reading.trend_arrow,
                    failed=True,
                )
                self.reading_changed.emit(failed)

    def _arrow_from_trend(self, trend: int) -> str:
        return {
            1: "↑",
            2: "↑",
            3: "↗",
            4: "→",
            5: "↘",
            6: "↓",
            7: "↓",
        }.get(int(trend or 0), "→")
