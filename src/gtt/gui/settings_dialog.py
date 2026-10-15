"""Settings window."""
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from ..i18n import _, LANGUAGES, current, load_config, save_config


class SettingsDialog(tk.Toplevel):
    """All options in one place. OK applies them; Cancel discards."""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title(_("Settings"))
        self.transient(app.root)
        self.resizable(False, False)
        self.configure(bg=app.T["bg"])
        s = app.p.settings
        self.v_src = tk.BooleanVar(value=app.v_src.get())
        self.v_num = tk.BooleanVar(value=app.v_num.get())
        self.v_style = tk.StringVar(value=app.v_style.get())
        self.v_enc = tk.StringVar(value=app.v_enc.get())
        self.v_map = tk.StringVar(value=app.v_map.get())
        self.v_lang = tk.StringVar(value=app.v_lang.get())

        self.v_ui = tk.StringVar(value=LANGUAGES[current()])
        body = ttk.Frame(self, padding=10); body.pack(fill="both", expand=True)

        g = ttk.LabelFrame(body, text=_("Interface"), padding=8); g.pack(fill="x", pady=(0, 8))
        r0 = ttk.Frame(g); r0.pack(fill="x", pady=2)
        ttk.Label(r0, text=_("Interface language (restart to apply):"), width=36).pack(side="left")
        ttk.Combobox(r0, textvariable=self.v_ui, width=14, state="readonly", values=list(LANGUAGES.values())).pack(side="left")

        g = ttk.LabelFrame(body, text=_("Editing"), padding=8); g.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(g, text=_("Allow editing the Source text (the game then no longer matches that entry)"),
                        variable=self.v_src).pack(anchor="w")
        ttk.Checkbutton(g, text=_("Numbered copy (\"1. text\") when copying lines"), variable=self.v_num).pack(anchor="w")

        g = ttk.LabelFrame(body, text=_("Output (.tra / .dta / .crm)"), padding=8); g.pack(fill="x", pady=(0, 8))
        r1 = ttk.Frame(g); r1.pack(fill="x", pady=2)
        ttk.Label(r1, text=_("Latin-1 letters (\u00e4 \u00f6 \u00fc \u00df \u00e9) in text .tra:"), width=36).pack(side="left")
        ttk.Combobox(r1, textvariable=self.v_style, width=10, state="readonly", values=["unicode", "ffxx"]).pack(side="left")
        r2 = ttk.Frame(g); r2.pack(fill="x", pady=2)
        ttk.Label(r2, text=_("Text encoding (.dta, .crm, binary .tra):"), width=36).pack(side="left")
        ttk.Combobox(r2, textvariable=self.v_enc, width=10, state="readonly", values=["utf-8", "cp1252"]).pack(side="left")
        r3 = ttk.Frame(g); r3.pack(fill="x", pady=2)
        ttk.Label(r3, text=_("Char replace on export (e.g. \u0259>\u00e4 \u0131>i):"), width=36).pack(side="left")
        ttk.Entry(r3, textvariable=self.v_map, width=30).pack(side="left")

        g = ttk.LabelFrame(body, text="Ren'Py (.rpy)", padding=8); g.pack(fill="x", pady=(0, 8))
        r4 = ttk.Frame(g); r4.pack(fill="x", pady=2)
        ttk.Label(r4, text=_("Language name written after \"translate\":"), width=36).pack(side="left")
        ttk.Entry(r4, textvariable=self.v_lang, width=16).pack(side="left")

        bt = ttk.Frame(body); bt.pack(fill="x")
        ttk.Button(bt, text=_("Reset to defaults"), command=self.reset).pack(side="left")
        ttk.Button(bt, text=_("Cancel"), command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bt, text=_("OK"), command=self.ok).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.ok())
        self.update_idletasks()
        x = app.root.winfo_rootx() + (app.root.winfo_width() - self.winfo_width()) // 2
        y = app.root.winfo_rooty() + 80
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.grab_set()
        self.focus_set()

    def reset(self):
        self.v_src.set(False); self.v_num.set(False)
        self.v_style.set("unicode"); self.v_enc.set("utf-8"); self.v_map.set(""); self.v_lang.set("azerbaijani")

    def ok(self):
        a = self.app
        a.v_src.set(self.v_src.get()); a.v_num.set(self.v_num.get())
        a.v_style.set(self.v_style.get()); a.v_enc.set(self.v_enc.get())
        a.v_map.set(self.v_map.get()); a.v_lang.set(self.v_lang.get())
        a.apply_settings()
        code = next((k for k, v in LANGUAGES.items() if v == self.v_ui.get()), current())
        if code != current():
            cfg = load_config(a.app_dir); cfg["language"] = code; save_config(a.app_dir, cfg)
            messagebox.showinfo(_("Settings"), _("The language will change after you restart the program."), parent=self)
        a.info.config(text=_("Settings saved."))
        self.destroy()
