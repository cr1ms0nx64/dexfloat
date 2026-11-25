from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from app import settings
from app.services.polling import ErrorKind
from app.ui.settings_dialog import SettingsDialog


class FakeService(QObject):
    validation_finished = pyqtSignal(int, object, object)

    def __init__(self):
        super().__init__()
        self.validate = Mock(return_value=1)
        self.adopt = Mock()


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "settings.ini"
        for key, value in [("APPDATA_DIR", self.path.parent), ("SETTINGS_PATH", self.path),
                           ("LEGACY_SETTINGS_PATH", self.path.parent / "old.ini")]:
            patcher = patch.object(settings, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.store = settings.SettingsStore()
        self.store.username, self.store.password = "old", "old-password"
        self.service = FakeService()
        self.dialog = SettingsDialog(self.store, self.service)
        self.addCleanup(self.dialog.deleteLater)
        self.dialog._username.setText("new")
        self.dialog._password.setText("new-password")

    def test_failed_validation_leaves_memory_disk_and_connection_unchanged(self):
        self.dialog._apply()
        self.assertEqual(self.store.username, "old")
        self.assertFalse(self.path.exists())
        self.service.validation_finished.emit(1, None, ErrorKind.NETWORK)
        self.dialog.reject()
        self.assertEqual((self.store.username, self.store.password), ("old", "old-password"))
        self.service.adopt.assert_not_called()

    def test_cancel_discards_late_success(self):
        self.dialog._apply()
        self.dialog.reject()
        self.service.validation_finished.emit(1, object(), None)
        self.assertEqual(self.store.username, "old")
        self.assertFalse(self.path.exists())
        self.service.adopt.assert_not_called()

    def test_success_adopts_checked_client_without_second_login(self):
        self.dialog._apply()
        client = object()
        with patch.object(settings.SettingsStore, "save") as save:
            self.service.validation_finished.emit(1, client, None)
        save.assert_called_once()
        self.assertEqual(self.store.username, "new")
        self.assertIs(self.service.adopt.call_args.args[1], client)
        self.service.validate.assert_called_once()
