import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QMessageBox

from app.config import TRAY_ICON_PATH
from app.autostart import migrate_legacy_autostart
from app.data import DexcomService
from app.settings import SettingsDialog, SettingsStore
from app.widget import GlucoseWidget


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Dexfloat")
    app.setQuitOnLastWindowClosed(False)
    migrate_legacy_autostart()
    if TRAY_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(TRAY_ICON_PATH)))

    settings = SettingsStore()
    service = DexcomService(settings)
    widget = GlucoseWidget(settings, service)

    if not settings.has_credentials():
        dialog = SettingsDialog(settings, service, widget)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return 0

    widget.show()
    if not service.start():
        QMessageBox.warning(
            widget,
            "Dexcom login failed",
            "Dexcom rejected the saved credentials. Please update username, password or region.",
        )
        dialog = SettingsDialog(settings, service, widget)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return 0
        service.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
