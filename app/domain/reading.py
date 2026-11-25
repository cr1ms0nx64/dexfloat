from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Trend(Enum):
    NONE = 0
    DOUBLE_UP = 1
    SINGLE_UP = 2
    FORTY_FIVE_UP = 3
    FLAT = 4
    FORTY_FIVE_DOWN = 5
    SINGLE_DOWN = 6
    DOUBLE_DOWN = 7
    NOT_COMPUTABLE = 8
    RATE_OUT_OF_RANGE = 9

    @classmethod
    def from_dexcom(cls, value: object) -> Trend:
        if isinstance(value, cls):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            try:
                return cls(value)
            except ValueError:
                return cls.NONE
        return _TREND_NAMES.get(str(value), cls.NONE)


_TREND_NAMES = dict(zip(
    ("None", "DoubleUp", "SingleUp", "FortyFiveUp", "Flat",
     "FortyFiveDown", "SingleDown", "DoubleDown", "NotComputable", "RateOutOfRange"),
    Trend,
))
_TREND_NAMES.update(dict(zip(("", "↑↑", "↑", "↗", "→", "↘", "↓", "↓↓", "?", "-"), Trend)))
_TREND_NAMES.update({"⇈": Trend.DOUBLE_UP, "⇊": Trend.DOUBLE_DOWN})


@dataclass(frozen=True)
class GlucoseReading:
    value_mmol: float
    timestamp: datetime
    trend: Trend
    delta_mmol: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.trend, Trend):
            raise ValueError("Invalid trend")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("Sensor timestamp must be timezone-aware")
        if not math.isfinite(self.value_mmol) or self.value_mmol <= 0:
            raise ValueError("Invalid glucose value")
        if self.delta_mmol is not None and not math.isfinite(self.delta_mmol):
            raise ValueError("Invalid delta")
