from __future__ import annotations

import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from pydexcom.errors import AccountError

from app.services.dexcom import DexcomService
from app.services.polling import Credentials, ErrorKind, classify_error


class WorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def settings(self):
        return SimpleNamespace(username="user", password="secret", region="ous")

    def process_until(self, condition, timeout=2):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.001)
        self.assertTrue(condition())

    def test_slow_network_does_not_block_qt_or_overlap_polls(self):
        entered, release = threading.Event(), threading.Event()
        worker_threads = []

        def slow_read(**kwargs):
            worker_threads.append(threading.get_ident())
            entered.set()
            release.wait(2)
            return []

        client = Mock(get_glucose_readings=Mock(side_effect=slow_read))
        with patch("app.services.dexcom.create_client", return_value=client) as factory:
            service = DexcomService(self.settings())
            try:
                service.start()
                self.process_until(entered.is_set)
                for _ in range(10):
                    service.refresh_now()
                tick = []
                QTimer.singleShot(0, lambda: tick.append(True))
                self.process_until(lambda: bool(tick))
                self.assertEqual(factory.call_count, 1)
                self.assertNotEqual(worker_threads[0], threading.get_ident())
                self.assertEqual(client.get_glucose_readings.call_count, 1)
            finally:
                release.set()
                service.wait_stopped()

    def test_account_error_does_not_retry_on_refresh_or_same_validation(self):
        with patch("app.services.dexcom.create_client", side_effect=AccountError()) as factory:
            service = DexcomService(self.settings())
            try:
                service.start()
                self.process_until(lambda: service._auth_blocked)
                service.refresh_now()
                service.reinitialize()
                completed = []
                service.validation_finished.connect(lambda *args: completed.append(args))
                service.validate(Credentials("user", "secret", "ous"))
                self.process_until(lambda: bool(completed))
                self.assertEqual(factory.call_count, 1)
                self.assertIs(completed[0][2], ErrorKind.AUTH)
            finally:
                service.wait_stopped()

    def test_real_account_error_type_is_classified_as_auth(self):
        self.assertIs(classify_error(AccountError()), ErrorKind.AUTH)
