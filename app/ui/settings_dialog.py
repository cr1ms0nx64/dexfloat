from __future__ import annotations

from app.ui.strings import TEXT

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QLabel, QLineEdit, QVBoxLayout,
)

from app.services.polling import Credentials
from app.settings import SettingsStore
from app.ui.strings import ERROR_MESSAGES


class SettingsDialog(QDialog):
    def __init__(self, settings, service, parent=None):
        super().__init__(parent)
        self._settings, self._service = settings, service
        self._pending: SettingsStore | None = None
        self._token: int | None = None
        self._close_on_success = False
        self._disposed = False
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(TEXT["settings_title"])
        self.setModal(True)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        self._form = QFormLayout()
        layout.addLayout(self._form)
        self._username = QLineEdit(settings.username)
        self._password = QLineEdit(settings.password)
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._region = QComboBox()
        for text, region in [(TEXT["region_us"], "us"), (TEXT["region_ous"], "ous"), (TEXT["region_jp"], "jp")]:
            self._region.addItem(text, region)
        self._region.setCurrentIndex(self._region.findData(settings.region))
        self._form.addRow(TEXT["username"], self._username)
        self._form.addRow(TEXT["password"], self._password)
        self._form.addRow(TEXT["region"], self._region)
        self._urgent_low = self._spin(TEXT["urgent_low"], settings.urgent_low_threshold, 1, 30, 1)
        self._low = self._spin(TEXT["low"], settings.low_threshold, 1, 30, 1)
        self._high = self._spin(TEXT["high"], settings.high_threshold, 1, 30, 1)
        self._idle_timeout = self._spin(TEXT["idle_timeout"], settings.idle_timeout_seconds, 2, 60, 0)
        self._idle_opacity = self._spin(TEXT["idle_opacity"], settings.idle_opacity_percent, 5, 80, 0)
        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply |
                                         QDialogButtonBox.StandardButton.Cancel |
                                         QDialogButtonBox.StandardButton.Ok)
        self._button(QDialogButtonBox.StandardButton.Apply).setText(TEXT["apply"])
        self._button(QDialogButtonBox.StandardButton.Cancel).setText(TEXT["cancel"])
        self._button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        self._buttons.accepted.connect(self._accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        service.validation_finished.connect(self._validated)
        self.finished.connect(self._dispose)

    def _button(self, role):
        button = self._buttons.button(role)
        assert button is not None
        return button

    def _spin(self, label, value, minimum, maximum, decimals):
        field = QDoubleSpinBox()
        field.setRange(minimum, maximum)
        field.setDecimals(decimals)
        field.setSingleStep(0.1 if decimals else 1)
        field.setValue(value)
        self._form.addRow(label, field)
        return field

    def _accept(self):
        self._close_on_success = True
        self._apply()

    def _set_loading(self, loading):
        for role in (QDialogButtonBox.StandardButton.Apply, QDialogButtonBox.StandardButton.Ok):
            self._button(role).setEnabled(not loading)
        for index in range(self._form.count()):
            item = self._form.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget:
                widget.setEnabled(not loading)

    def _apply(self):
        if self._pending is not None:
            return
        if not 1 <= self._urgent_low.value() <= self._low.value() < self._high.value():
            self._status.setText(TEXT["threshold_error"])
            self._close_on_success = False
            return
        if not self._username.text().strip() or not self._password.text():
            self._status.setText(TEXT["credentials_missing"])
            self._close_on_success = False
            return
        candidate = deepcopy(self._settings)
        candidate.username, candidate.password = self._username.text().strip(), self._password.text()
        candidate.region = self._region.currentData()
        candidate.region_ous = candidate.region == "ous"
        candidate.low_threshold, candidate.high_threshold = self._low.value(), self._high.value()
        candidate.urgent_low_threshold = self._urgent_low.value()
        candidate.idle_timeout_seconds = int(self._idle_timeout.value())
        candidate.idle_opacity_percent = int(self._idle_opacity.value())
        self._pending = candidate
        self._set_loading(True)
        self._status.setText(TEXT["validating"])
        self._token = self._service.validate(Credentials(candidate.username, candidate.password, candidate.region))

    def _validated(self, token, client, error):
        if token != self._token or self._disposed or self._pending is None:
            return
        candidate, self._pending = self._pending, None
        self._set_loading(False)
        if error is not None:
            self._status.setText(ERROR_MESSAGES[error])
            self._close_on_success = False
            return
        try:
            candidate.save()
        except OSError:
            self._status.setText(TEXT["save_error"])
            self._close_on_success = False
            return
        self._settings.__dict__.update(candidate.__dict__)
        self._service.adopt(Credentials(candidate.username, candidate.password, candidate.region), client)
        self._status.setText(TEXT["saved"])
        if self._close_on_success:
            self.accept()
        self._close_on_success = False

    def _dispose(self, *_):
        self._disposed = True
        self._pending = None
        self._service.validation_finished.disconnect(self._validated)
