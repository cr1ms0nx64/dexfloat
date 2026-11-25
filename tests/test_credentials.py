from __future__ import annotations

import base64
import unittest
from unittest.mock import patch

from app.services import credentials


class DPAPITests(unittest.TestCase):
    def test_new_password_is_user_dpapi_and_round_trips(self):
        def crypt(value, *, protect):
            return b"protected:" + value if protect else value.removeprefix(b"protected:")
        with patch.object(credentials, "is_windows", return_value=True), patch.object(credentials, "_dpapi", side_effect=crypt):
            token, kind = credentials.encrypt_password("secret")
            self.assertEqual(kind, "dpapi")
            self.assertNotIn("secret", token)
            self.assertEqual(credentials.decrypt_password(token, kind), "secret")

    def test_invalid_dpapi_requests_fresh_credentials(self):
        with patch.object(credentials, "is_windows", return_value=True), patch.object(credentials, "_dpapi", side_effect=OSError):
            self.assertEqual(credentials.decrypt_password("!invalid!", "dpapi"), "")
            self.assertEqual(credentials.decrypt_password(base64.b64encode(b"bad").decode(), "dpapi"), "")
        with patch.object(credentials, "is_windows", return_value=False):
            self.assertEqual(credentials.decrypt_password("token", "dpapi"), "")

    def test_legacy_migrates_to_dpapi_on_save(self):
        for context in (b"dextop", b"dexfloat"):
            old = credentials._fernet(context).encrypt(b"secret").decode()
            self.assertEqual(credentials.decrypt_password(old), "secret")
            with patch.object(credentials, "is_windows", return_value=True), patch.object(credentials, "_dpapi", return_value=b"new"):
                _, kind = credentials.encrypt_password(credentials.decrypt_password(old))
                self.assertEqual(kind, "dpapi")
