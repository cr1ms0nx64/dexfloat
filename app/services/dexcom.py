from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot

from app.domain.reading import GlucoseReading
from app.services.polling import Credentials, ErrorKind, Poller, create_client


class _Worker(QObject):
    completed = pyqtSignal(int, object)
    validated = pyqtSignal(int, object, object)

    def __init__(self):
        super().__init__()
        self._poller = None
        self._generation = -1

    @pyqtSlot(int, object, object)
    def poll(self, generation, credentials, client):
        if QThread.currentThread().isInterruptionRequested():
            return
        if generation != self._generation:
            self._poller = Poller(credentials, client=client)
            self._generation = generation
        self.completed.emit(generation, self._poller.poll())

    @pyqtSlot(int, object)
    def validate(self, token, credentials):
        if QThread.currentThread().isInterruptionRequested():
            return
        from app.services.polling import classify_error
        try:
            client = create_client(credentials)
        except Exception as exc:
            self.validated.emit(token, None, classify_error(exc))
        else:
            self.validated.emit(token, client, None)


class DexcomService(QObject):
    reading_changed = pyqtSignal(object)
    error_changed = pyqtSignal(object, str)
    validation_finished = pyqtSignal(int, object, object)
    stopped = pyqtSignal()
    _poll_requested = pyqtSignal(int, object, object)
    _validation_requested = pyqtSignal(int, object)

    def __init__(self, settings):
        super().__init__()
        self._settings = settings
        self._last_reading: GlucoseReading | None = None
        self._generation = 0
        self._token = 0
        self._busy = False
        self._running = False
        self._auth_blocked = False
        self._credentials = self.credentials_from_settings()
        self._adopted_client = None
        self._thread = QThread(self)
        self._worker = _Worker()
        self._worker.moveToThread(self._thread)
        self._poll_requested.connect(self._worker.poll)
        self._validation_requested.connect(self._worker.validate)
        self._worker.completed.connect(self._completed)
        self._worker.validated.connect(self._validated)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self.stopped)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh_now)
        self._thread.start()

    def credentials_from_settings(self):
        region = getattr(self._settings, "region", None)
        if region is None:
            region = "ous" if self._settings.region_ous else "us"
        return Credentials(self._settings.username, self._settings.password, region)

    @property
    def last_reading(self):
        return self._last_reading

    def start(self):
        self._running = True
        self.refresh_now()

    def stop(self):
        self._running = False
        self._timer.stop()
        self._thread.requestInterruption()
        self._thread.quit()

    def wait_stopped(self):
        self.stop()
        self._thread.wait()

    def reinitialize(self):
        self.adopt(self.credentials_from_settings(), None)

    def adopt(self, credentials, client):
        self._generation += 1
        self._credentials = credentials
        self._adopted_client = client
        self._auth_blocked = False
        self._last_reading = None
        self.reading_changed.emit(None)
        self._timer.stop()
        self._running = True
        if not self._busy:
            self.refresh_now()

    def refresh_now(self):
        if not self._running or self._busy or self._auth_blocked:
            return
        self._busy = True
        self._timer.stop()
        client, self._adopted_client = self._adopted_client, None
        self._poll_requested.emit(self._generation, self._credentials, client)

    @pyqtSlot(int, object)
    def _completed(self, generation, result):
        self._busy = False
        if not self._running:
            return
        if generation != self._generation:
            self.refresh_now()
            return
        self._last_reading = result.reading
        self.reading_changed.emit(result.reading)
        if result.error is not None:
            from app.ui.strings import ERROR_MESSAGES
            self.error_changed.emit(result.error, ERROR_MESSAGES[result.error])
        else:
            self.error_changed.emit(None, "")
        self._auth_blocked = result.error is ErrorKind.AUTH
        if not self._auth_blocked:
            self._timer.start(result.retry_seconds * 1000)

    def validate(self, credentials):
        self._token += 1
        self._validation_requested.emit(self._token, credentials)
        return self._token

    @pyqtSlot(int, object, object)
    def _validated(self, token, client, error):
        self.validation_finished.emit(token, client, error)
