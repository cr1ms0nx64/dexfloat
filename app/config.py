from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "dexfloat"
APPDATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / APP_NAME
SETTINGS_PATH = APPDATA_DIR / "settings.ini"
LEGACY_SETTINGS_PATH = APPDATA_DIR.parent / "dextop" / "settings.ini"
FONTS_DIR = APPDATA_DIR / "fonts"

APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
ASSETS_DIR = APP_ROOT / "assets"
TRAY_ICON_PATH = ASSETS_DIR / "dexfloat_icon.png"

WINDOW_WIDTH = 400
WINDOW_HEIGHT = 120
CARD_WIDTH = 360
CARD_HEIGHT = 80
CARD_X = 20
CARD_Y = 20
CARD_RADIUS = 16

MMOL_FACTOR = 18.0
DEFAULT_LOW = 4.5
DEFAULT_HIGH = 10.0
DEFAULT_POLL_SECONDS = 60

SURFACE = "#13161d"
BORDER_ALPHA = 18
STATUS_ALPHA = 77
UNIT_ALPHA = 71
GREEN = "#22d37a"
YELLOW = "#f5c842"
RED = "#f2504b"
FAILED_ACCENT = "#444444"


@dataclass(frozen=True)
class FontSpec:
    family: str
    fallback: str
    file_name: str
    url: str


FONTS = {
    "display": FontSpec(
        family="Syne",
        fallback="Arial Black",
        file_name="Syne[wght].ttf",
        url="https://github.com/google/fonts/raw/main/ofl/syne/Syne%5Bwght%5D.ttf",
    ),
    "mono_regular": FontSpec(
        family="DM Mono",
        fallback="Courier New",
        file_name="DMMono-Regular.ttf",
        url="https://github.com/google/fonts/raw/main/ofl/dmmono/DMMono-Regular.ttf",
    ),
    "mono_light": FontSpec(
        family="DM Mono",
        fallback="Courier New",
        file_name="DMMono-Light.ttf",
        url="https://github.com/google/fonts/raw/main/ofl/dmmono/DMMono-Light.ttf",
    ),
}
