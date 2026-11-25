"""Alias preserves existing imports and registry test patch points."""
import sys
from app.platform import autostart

sys.modules[__name__] = autostart
