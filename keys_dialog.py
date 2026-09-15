"""tkinter dialog for entering/editing API keys — used for first-run setup
and the tray "Edit API Keys..." menu item. No console dependency, since the
packaged .exe runs windowed with no console attached at all.

Runs as a Toplevel of the app's single shared gui_root (see gui_root.py) so
it behaves as a normal modal dialog instead of an independent, separately-
interpreted top-level window.
"""

import tkinter as tk
from tkinter import messagebox

import gui_root


def prompt_for_keys(initial: dict | None = None) -> dict | None:
    """Show a modal dialog with masked Groq/Mistral key fields. Returns the
    entered {"GROQ_API_KEY", "MISTRAL_API_KEY"} dict on Save, or None if the
    user cancelled or closed the window. Blocks the calling thread; safe to
    call from any thread (marshalled onto the GUI thread internally)."""
    return gui_root.run_on_gui_thread(lambda: _show(initial or {}))


def _show(initial: dict) -> dict | None:
    result: dict | None = None
    root = gui_root.get_root()

    top = tk.Toplevel(root)
    top.title("SwarLekh - API Keys")
    top.attributes("-topmost", True)
    top.resizable(False, False)

    tk.Label(top, text="Groq API key:").grid(row=0, column=0, sticky="w", padx=10, pady=(14, 4))
    groq_var = tk.StringVar(value=initial.get("GROQ_API_KEY", ""))
    groq_entry = tk.Entry(top, textvariable=groq_var, show="*", width=42)
    groq_entry.grid(row=0, column=1, padx=10, pady=(14, 4))

    tk.Label(top, text="Mistral API key:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
    mistral_var = tk.StringVar(value=initial.get("MISTRAL_API_KEY", ""))
    mistral_entry = tk.Entry(top, textvariable=mistral_var, show="*", width=42)
    mistral_entry.grid(row=1, column=1, padx=10, pady=4)

    def on_save() -> None:
        nonlocal result
        groq = groq_var.get().strip()
        mistral = mistral_var.get().strip()
        if not groq or not mistral:
            messagebox.showerror("SwarLekh", "Both keys are required.", parent=top)
            return
        result = {"GROQ_API_KEY": groq, "MISTRAL_API_KEY": mistral}
        top.destroy()

    def on_cancel() -> None:
        top.destroy()

    button_frame = tk.Frame(top)
    button_frame.grid(row=2, column=0, columnspan=2, pady=14)
    tk.Button(button_frame, text="Save", command=on_save, width=10).pack(side="left", padx=4)
    tk.Button(button_frame, text="Cancel", command=on_cancel, width=10).pack(side="left", padx=4)

    top.protocol("WM_DELETE_WINDOW", on_cancel)
    top.lift()
    top.focus_force()
    top.grab_set()
    groq_entry.focus_set()
    top.wait_window(top)
    return result
