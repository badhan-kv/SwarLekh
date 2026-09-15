"""Single persistent Tk interpreter for the whole app, created once on the
main thread at startup. Every dialog is a Toplevel of this one root, and any
call from a non-GUI thread (pystray's icon thread, pynput's listener thread)
must go through run_on_gui_thread().

Why this exists: creating a brand-new tkinter.Tk() (a fresh Tcl interpreter)
from inside pystray's Windows icon thread — itself a hand-rolled ctypes
GetMessage/DispatchMessage loop, not a standard framework loop — produced
dialogs that rendered once but never processed further input (no exceptions,
just permanently inert), and each got its own taskbar entry since it was a
fully independent top-level interpreter. A single Tcl interpreter, with its
mainloop() as the actual main thread's blocking call and pystray's icon
loop demoted to a background thread (the pattern pystray's own FAQ
recommends for non-macOS platforms), avoids both problems.
"""

import threading
import tkinter

_root: tkinter.Tk | None = None


def init_root() -> tkinter.Tk:
    global _root
    _root = tkinter.Tk()
    _root.withdraw()
    return _root


def get_root() -> tkinter.Tk:
    if _root is None:
        raise RuntimeError("gui_root.init_root() must be called before get_root()")
    return _root


def run_on_gui_thread(fn):
    """Run fn() on the Tk mainloop's thread and block the calling thread
    until it completes, returning its result (or re-raising its exception).
    Safe to call from any thread — tkinter's .after() is the documented
    thread-safe way to schedule work onto the interpreter's owning thread."""
    result: dict = {}
    done = threading.Event()

    def wrapper():
        try:
            result["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 — re-raised on the caller's thread below
            result["error"] = exc
        finally:
            done.set()

    get_root().after(0, wrapper)
    done.wait()
    if "error" in result:
        raise result["error"]
    return result.get("value")
