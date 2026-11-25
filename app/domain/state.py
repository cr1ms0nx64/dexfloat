from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum, auto

from app.domain.reading import GlucoseReading, Trend


class DisplayState(Enum):
    NO_DATA = auto()
    STALE = auto()
    URGENT_LOW = auto()
    LOW = auto()
    HIGH = auto()
    RISING_FAST = auto()
    FALLING_FAST = auto()
    RISING = auto()
    FALLING = auto()
    IN_RANGE = auto()
    TREND_UNKNOWN = auto()


def classify(
    reading: GlucoseReading | None, low: float, high: float, now: datetime, *,
    stale_after: timedelta = timedelta(minutes=10), urgent_low: float = 3.1,
) -> DisplayState:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if reading is None:
        return DisplayState.NO_DATA
    age = now - reading.timestamp
    # Future timestamps cannot establish freshness either.
    if age < timedelta(0) or age >= stale_after:
        return DisplayState.STALE
    if reading.value_mmol < urgent_low:
        return DisplayState.URGENT_LOW
    if reading.value_mmol < low:
        return DisplayState.LOW
    if reading.trend is Trend.DOUBLE_DOWN:
        return DisplayState.FALLING_FAST
    if reading.value_mmol > high:
        return DisplayState.HIGH
    if reading.trend is Trend.DOUBLE_UP:
        return DisplayState.RISING_FAST
    if reading.trend in {Trend.NONE, Trend.NOT_COMPUTABLE, Trend.RATE_OUT_OF_RANGE}:
        return DisplayState.TREND_UNKNOWN
    if reading.trend in {Trend.SINGLE_DOWN, Trend.FORTY_FIVE_DOWN}:
        return DisplayState.FALLING
    if reading.trend in {Trend.SINGLE_UP, Trend.FORTY_FIVE_UP}:
        return DisplayState.RISING
    return DisplayState.IN_RANGE
