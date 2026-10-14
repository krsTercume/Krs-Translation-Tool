"""GUI smoke test with a mocked tkinter (so it runs without a display). Run: python tests/gui_smoke.py
It only proves the code paths run without exceptions; it does NOT check how the window looks."""
import os, sys, types, tempfile
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


class Dummy(MagicMock):
    pass


class Toplevel:
    def __init__(self, *a, **k): self.__dict__["_m"] = MagicMock()
    def __getattr__(self, n): return getattr(self.__dict__["_m"], n)


tk = types.ModuleType("tkinter"); ttk = MagicMock(); mb = MagicMock(); fd = MagicMock()
for n in ("Tk", "Frame", "Text", "Listbox", "Menu", "Button", "StringVar", "IntVar", "BooleanVar", "Entry"):
    setattr(tk, n, MagicMock())
tk.Toplevel = Toplevel; tk.TclError = type("TclError", (Exception,), {})
tk.ttk, tk.messagebox, tk.filedialog = ttk, mb, fd
sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.messagebox": mb, "tkinter.filedialog": fd})
mb.askyesno.return_value = True; mb.askyesnocancel.return_value = True

from gtt import i18n  # noqa: E402
for lang in ("en", "az"):
    i18n.set_language(lang)
    from gtt.gui.app import App
    from gtt.gui.settings_dialog import SettingsDialog
    root = MagicMock()
    for m in ("winfo_rootx", "winfo_rooty", "winfo_width"): getattr(root, m).return_value = 100
    app = App(root)
    app.app_dir = tempfile.mkdtemp()
    app.tv.get_children.return_value = ()
    app.v_doc.get.return_value = i18n._("(all)")
    app.open_files([os.path.join(ROOT, "examples", "Sample.tra")])
    app.validate(quiet=True); app._stats(); app.mark(True); app.on_sel()
    app.root.winfo_rootx.return_value = 100
    Toplevel.winfo_width = Toplevel.winfo_rootx = Toplevel.winfo_rooty = lambda self: 50
    SettingsDialog(app)
    print("gui smoke ok:", lang)

import main  # noqa: E402,F401
print("main imports ok")
