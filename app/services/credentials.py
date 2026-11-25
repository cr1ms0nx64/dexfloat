from __future__ import annotations

import base64
import ctypes
import hashlib
import platform
import sys
from ctypes import wintypes


def is_windows() -> bool:
    return sys.platform == "win32"


def _fernet(context: bytes = b"dexfloat"):
    from cryptography.fernet import Fernet
    seed = platform.node().encode("utf-8", errors="ignore") or context
    digest = hashlib.sha256(seed + b":" + context).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class _Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data: bytes, *, protect: bool) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = _Blob()
    operation = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    operation.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
    operation.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    # CRYPTPROTECT_UI_FORBIDDEN; no LOCAL_MACHINE flag: bound to this Windows user.
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel32.LocalFree(target.data)


def encrypt_password(value: str) -> tuple[str, str]:
    if is_windows():
        return (base64.b64encode(_dpapi(value.encode("utf-8"), protect=True)).decode("ascii")
                if value else "", "dpapi")
    return (_fernet().encrypt(value.encode("utf-8")).decode("ascii") if value else "", "fernet")


def decrypt_password(value: str, password_format: str = "fernet") -> str:
    if not value:
        return ""
    if password_format == "dpapi":
        try:
            if not is_windows():
                return ""
            return _dpapi(base64.b64decode(value, validate=True), protect=False).decode("utf-8")
        except (OSError, ValueError, UnicodeError):
            return ""
    if password_format not in ("", "fernet"):
        return ""
    from cryptography.fernet import InvalidToken
    for context in (b"dexfloat", b"dextop"):
        try:
            return _fernet(context).decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, UnicodeError):
            continue
    return ""
