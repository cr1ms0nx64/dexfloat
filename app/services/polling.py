"""Polling policy, independent of Qt for deterministic tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable

from app.domain.reading import GlucoseReading, Trend


class ErrorKind(Enum):
    AUTH = auto()
    NETWORK = auto()
    SESSION = auto()
    NO_DATA = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str = field(repr=False)
    region: str = "ous"


@dataclass(frozen=True)
class PollResult:
    reading: GlucoseReading | None = None
    error: ErrorKind | None = None
    retry_seconds: int = 60


def classify_error(exc: Exception) -> ErrorKind:
    from pydexcom import errors
    from requests.exceptions import RequestException  # type: ignore[import-untyped]

    if isinstance(exc, errors.AccountError):
        return ErrorKind.AUTH
    if isinstance(exc, errors.SessionError):
        return ErrorKind.SESSION
    if isinstance(exc, (RequestException, OSError, TimeoutError, errors.ServerError)):
        return ErrorKind.NETWORK
    return ErrorKind.UNKNOWN


def create_client(credentials: Credentials) -> Any:
    from pydexcom import Dexcom
    from pydexcom.const import Region
    from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]

    class TimeoutAdapter(HTTPAdapter):
        def send(self, request, **kwargs):
            if kwargs.get("timeout") is None:
                kwargs["timeout"] = (5, 15)
            return super().send(request, **kwargs)

    class BoundedDexcom(Dexcom):
        def _get_session(self):
            # Installed before the constructor's first network request.
            self._session.mount("https://", TimeoutAdapter(max_retries=0))
            return super()._get_session()

    return BoundedDexcom(username=credentials.username, password=credentials.password,
                         region=Region(credentials.region))


def _mmol(raw: Any) -> float:
    value = getattr(raw, "mmol_l", None)
    return float(value) if value is not None else float(raw.value) / 18.0182


def sensor_reading(values: list[Any]) -> GlucoseReading | None:
    if not values:
        return None
    for raw in values:
        if not isinstance(raw.datetime, datetime) or raw.datetime.utcoffset() is None:
            raise ValueError("Missing timezone-aware sensor timestamp")
    ordered = sorted(values, key=lambda raw: raw.datetime, reverse=True)
    newest = ordered[0]
    previous = next((raw for raw in ordered[1:] if raw.datetime < newest.datetime), None)
    delta = _mmol(newest) - _mmol(previous) if previous is not None else None
    trend = getattr(newest, "trend", None)
    if trend is None:
        trend = getattr(newest, "trend_direction", None)
    if trend is None:
        trend = getattr(newest, "trend_arrow", None)
    return GlucoseReading(_mmol(newest), newest.datetime.astimezone(timezone.utc),
                          Trend.from_dexcom(trend), delta)


class Poller:
    def __init__(self, credentials: Credentials, *, client: Any = None,
                 factory: Callable = create_client, error_classifier: Callable = classify_error):
        self.credentials = credentials
        self.client = client
        self.factory = factory
        self.error_classifier = error_classifier
        self.auth_blocked = False
        self.failures = 0

    def poll(self) -> PollResult:
        if self.auth_blocked:
            return PollResult(error=ErrorKind.AUTH, retry_seconds=0)
        try:
            if self.client is None:
                self.client = self.factory(self.credentials)
            reading = sensor_reading(self.client.get_glucose_readings(minutes=15, max_count=2))
            self.failures = 0
            return PollResult(reading, None if reading else ErrorKind.NO_DATA)
        except Exception as exc:
            kind = self.error_classifier(exc)
            if kind is ErrorKind.AUTH:
                self.auth_blocked = True
                return PollResult(error=kind, retry_seconds=0)
            if kind is ErrorKind.SESSION:
                self.client = None
            wait = min(15 * 2 ** min(self.failures, 5), 300)
            self.failures += 1
            return PollResult(error=kind, retry_seconds=wait)
