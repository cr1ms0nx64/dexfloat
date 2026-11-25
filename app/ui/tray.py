from app.ui.strings import TEXT

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from app.config import TRAY_ICON_PATH
from app.platform.autostart import is_autostart_enabled, set_autostart_enabled
from app.services.polling import ErrorKind


class TrayController:
    def __init__(self, widget, service):
        self.widget, self.service = widget, service
        self.icon = QSystemTrayIcon(widget)
        if TRAY_ICON_PATH.exists():
            self.icon.setIcon(QIcon(str(TRAY_ICON_PATH)))
        self.icon.setToolTip(TEXT["tray_title"])
        self.menu = QMenu(widget)
        self.icon.setContextMenu(self.menu)
        self.drag = QAction(TEXT["drag"], widget)
        self.drag.setCheckable(True)
        self.drag.toggled.connect(widget.set_drag_enabled)
        self.autostart = QAction(TEXT["autostart"], widget)
        self.autostart.setCheckable(True)
        self.autostart.setChecked(is_autostart_enabled())
        self.autostart.toggled.connect(self._set_autostart)
        self.menu.addAction(self.drag)
        self.menu.addAction(self.autostart)
        self.menu.addSeparator()
        for label, callback in [(TEXT["refresh"], service.refresh_now),
                                (TEXT["settings"], widget._open_settings),
                                (TEXT["quit"], QApplication.quit)]:
            action = QAction(label, widget)
            action.triggered.connect(callback)
            self.menu.addAction(action)
        self.icon.activated.connect(self._activated)
        service.error_changed.connect(self._error)
        self.icon.show()

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.widget._open_settings()

    def _set_autostart(self, enabled):
        try:
            set_autostart_enabled(enabled)
        except (OSError, RuntimeError) as exc:
            self.autostart.blockSignals(True)
            self.autostart.setChecked(is_autostart_enabled())
            self.autostart.blockSignals(False)
            self.icon.showMessage(TEXT["autostart_error"], str(exc),
                                  QSystemTrayIcon.MessageIcon.Warning, 5000)

    def _error(self, kind, message):
        self.icon.setToolTip(TEXT["app_title"] + " · " + message if message else TEXT["tray_title"])
        if kind is ErrorKind.AUTH:
            self.icon.showMessage(TEXT["login_required"], message,
                                  QSystemTrayIcon.MessageIcon.Warning, 10000)
