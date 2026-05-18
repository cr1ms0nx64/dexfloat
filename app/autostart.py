from __future__ import annotations

import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only feature.
    winreg = None


RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "CrimsonGlucoseOverlay"


def current_launch_command() -> str:
    """Return the command Windows should execute on user login."""
    if getattr(sys, "frozen", False):
        return _quote(Path(sys.executable))

    script_path = Path(__file__).resolve().parents[1] / "Dextop.py"
    launcher = Path(sys.executable)
    pythonw = launcher.with_name("pythonw.exe")
    if pythonw.exists():
        launcher = pythonw
    return f"{_quote(launcher)} {_quote(script_path)}"


def is_autostart_enabled() -> bool:
    if winreg is None:
        return False

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
    except FileNotFoundError:
        return False
    except OSError:
        return False

    return bool(str(value).strip())


def set_autostart_enabled(enabled: bool) -> None:
    if winreg is None:
        raise RuntimeError("Autostart wird nur unter Windows unterstuetzt.")

    if enabled:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, current_launch_command())
        return

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_VALUE_NAME)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _quote(path: Path) -> str:
    text = str(path)
    escaped = text.replace('"', r"\"")
    return f'"{escaped}"'
