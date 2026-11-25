from dataclasses import dataclass

from app.config import GREEN, RED, YELLOW
from app.domain.reading import Trend
from app.domain.state import DisplayState as S


@dataclass(frozen=True)
class StateStyle:
    color: str
    marker: str = ""


STYLES = {
    S.NO_DATA: StateStyle("#9298a3", "?"),
    S.STALE: StateStyle("#9298a3", "⌛"),
    S.URGENT_LOW: StateStyle(RED, "!!"),
    S.LOW: StateStyle(RED, "!"),
    S.HIGH: StateStyle("#ffab54", "+"),
    S.FALLING_FAST: StateStyle(RED),
    S.RISING_FAST: StateStyle(RED),
    S.TREND_UNKNOWN: StateStyle("#9298a3", "?"),
    S.FALLING: StateStyle(YELLOW),
    S.RISING: StateStyle(YELLOW),
    S.IN_RANGE: StateStyle(GREEN),
}
NEUTRAL = "#9298a3"
CRITICAL = {S.URGENT_LOW, S.LOW, S.FALLING_FAST, S.STALE, S.NO_DATA}
ARROWS = {
    Trend.DOUBLE_UP: "double_up", Trend.SINGLE_UP: "up", Trend.FORTY_FIVE_UP: "diagonal_up",
    Trend.FLAT: "flat", Trend.FORTY_FIVE_DOWN: "diagonal_down", Trend.SINGLE_DOWN: "down",
    Trend.DOUBLE_DOWN: "double_down", Trend.NONE: "unknown", Trend.NOT_COMPUTABLE: "unknown",
    Trend.RATE_OUT_OF_RANGE: "unknown",
}
