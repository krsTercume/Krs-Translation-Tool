"""Krs Translation Editor - entry point."""
import os
import sys
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gtt import i18n  # noqa: E402

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root: backups/, projects/, config.json


def choose_language():
    """First launch: ask once (Azərbaycan / English). Returns the code, or None if the window was closed."""
    root = tk.Tk()
    root.title("Krs Translation Editor")
    root.resizable(False, False)
    res = {"code": None}
    f = ttk.Frame(root, padding=20); f.pack()
    ttk.Label(f, text="Choose your language / Dilinizi seçin", font=("Segoe UI", 11, "bold")).pack(pady=(0, 12))
    for code, name in i18n.LANGUAGES.items():
        ttk.Button(f, text=name, width=24, command=lambda c=code: (res.update(code=c), root.destroy())).pack(pady=3)
    ttk.Label(f, text="(Settings → Interface)", foreground="#777").pack(pady=(10, 0))
    root.eval("tk::PlaceWindow . center")
    root.mainloop()
    return res["code"]


def main():
    cfg = i18n.load_config(APP)
    code = cfg.get("language")
    if code not in i18n.LANGUAGES:
        code = choose_language()
        if code is None:
            return
        cfg["language"] = code
        i18n.save_config(APP, cfg)
    i18n.set_language(code)
    from gtt.gui.app import App
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
