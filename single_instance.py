"""Single-instance guard via a named Windows mutex.

Two copies running at once (e.g. the installed exe plus a `python tray.py`
dev copy) would each install a global keyboard hook, so every hotkey press
would start two recordings and paste twice.
"""

import ctypes

MUTEX_NAME = "Local\\SwarLekh-single-instance"
_ERROR_ALREADY_EXISTS = 183

_handle = None  # kept alive for the life of the process; Windows frees it on exit


def acquire(name: str = MUTEX_NAME) -> bool:
    """True if this is the only running instance; False if another one holds
    the mutex. Fails open (True) if the Win32 call itself is unavailable."""
    global _handle
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            return True
        if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
            return False
        _handle = handle
        return True
    except Exception:
        return True
