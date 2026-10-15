"""Main window."""
import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ..project import Project
from ..validation import check_entry, has_error
from ..common import ERR
from ..i18n import _
from .themes import THEMES
from .settings_dialog import SettingsDialog

APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # repo root: backups/, projects/


class App:
    def __init__(self, root):
        self.root = root
        self.app_dir = APP
        root.title(_("Krs Translation Editor"))
        root.geometry("1280x740")
        self.p = Project(APP)
        self.shown = []
        self._rb = None
        self._build()
        self.apply_theme(self._load_theme())
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(60000, self._autosave)

    # ---------------------------------------------------------------- UI
    def _build(self):
        r = self.root
        top = ttk.Frame(r); top.pack(fill="x", padx=6, pady=4)
        B = lambda t, c: ttk.Button(top, text=t, command=c).pack(side="left", padx=2)
        B(_("Open .tra/.dta/.crm/.rpy"), self.open_files); B(_("Open folder (.crm/.rpy)"), self.open_folder); B(_("Save"), self.save); B(_("Backup"), self.backup)
        B(_("Undo (Ctrl+Z)"), self.undo); B(_("Redo (Ctrl+Y)"), self.redo)
        B(_("Validate"), self.validate); B(_("Export"), self.export); B(_("Settings..."), self.open_settings)
        ttk.Label(top, text=_("Search:")).pack(side="left", padx=(12, 2))
        self.q = tk.StringVar(); ttk.Entry(top, textvariable=self.q, width=16).pack(side="left")
        self.q.trace_add("write", lambda *a: self.refresh())
        ttk.Label(top, text=_("Theme:")).pack(side="left", padx=(8, 2))
        self.v_theme = tk.StringVar(value="Standard")
        cb = ttk.Combobox(top, textvariable=self.v_theme, width=9, state="readonly", values=list(THEMES))
        cb.pack(side="left"); cb.bind("<<ComboboxSelected>>", lambda e: self.apply_theme(self.v_theme.get()))
        ttk.Label(top, text=_("File:")).pack(side="left", padx=(8, 2))
        self.v_doc = tk.StringVar(value=_("(all)"))
        self.cb_doc = ttk.Combobox(top, textvariable=self.v_doc, width=14, state="readonly", values=[_("(all)")])
        self.cb_doc.pack(side="left"); self.cb_doc.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.f_un, self.f_vo, self.f_is = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        for t, v in ((_("Not done only"), self.f_un), (_("Voiced only"), self.f_vo), (_("With problems only"), self.f_is)):
            ttk.Checkbutton(top, text=t, variable=v, command=self.refresh).pack(side="left", padx=3)

        bar = ttk.Frame(r); bar.pack(fill="x", padx=6)
        s = self.p.settings
        self.v_n = tk.IntVar(value=s.chunk); self.v_num = tk.BooleanVar(value=s.numbered)
        self.v_src = tk.BooleanVar(value=s.allow_src_edit); self.v_style = tk.StringVar(value=s.latin_style)
        self.v_map = tk.StringVar(value=s.charmap); self.v_enc = tk.StringVar(value=s.out_encoding)
        ttk.Label(bar, text=_("Select N (or drag with mouse):")).pack(side="left")
        ttk.Spinbox(bar, from_=1, to=2000, width=5, textvariable=self.v_n).pack(side="left")
        ttk.Button(bar, text=_("Select next N + copy"), command=self.smart_copy).pack(side="left", padx=4)
        ttk.Button(bar, text=_("Copy selected"), command=self.copy_sel).pack(side="left", padx=2)
        ttk.Button(bar, text=_("Paste (Ctrl+V)"), command=self.paste).pack(side="left", padx=2)
        ttk.Button(bar, text=_("Mark done"), command=lambda: self.mark(True)).pack(side="left", padx=2)
        ttk.Button(bar, text=_("Mark not done"), command=lambda: self.mark(False)).pack(side="left", padx=2)
        ttk.Button(bar, text=_("Clear (Del)"), command=self.clear_text_sel).pack(side="left", padx=(12, 2))

        self.v_lang = tk.StringVar(value=s.renpy_lang)

        pan = ttk.PanedWindow(r, orient="vertical"); pan.pack(fill="both", expand=True, padx=6, pady=4)
        cols = ("n", "file", "voice", "orig", "tr", "len", "st")
        tf = ttk.Frame(pan)
        self.tv = ttk.Treeview(tf, columns=cols, show="headings", selectmode="extended", height=16)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.tv.pack(side="left", fill="both", expand=True)
        for c, t, w in (("n", "#", 55), ("file", _("File"), 80), ("voice", _("Voice"), 60),
                        ("orig", _("Source (select on the left)"), 480),
                        ("tr", _("Translation (paste here / double-click)"), 480), ("len", _("Length"), 70), ("st", "", 28)):
            self.tv.heading(c, text=t); self.tv.column(c, width=w, stretch=c in ("orig", "tr"))
        pan.add(tf, weight=3)
        self.tv.bind("<<TreeviewSelect>>", self.on_sel)
        self.tv.bind("<Double-1>", self.edit_cell)
        self._rb_frames = [tk.Frame(self.tv) for _i in range(4)]
        self.tv.bind("<ButtonPress-1>", self.rb_press)
        self.tv.bind("<B1-Motion>", self.rb_move)
        self.tv.bind("<ButtonRelease-1>", self.rb_release)

        pv = ttk.Frame(pan); pan.add(pv, weight=1)
        self.t_o = self._preview(pv, _("Source ('[' = new line)"))
        self.t_t = self._preview(pv, _("Translation"))
        self.info = ttk.Label(r, text=_("Open a .tra file."), anchor="w"); self.info.pack(fill="x", padx=6)
        self.lb = tk.Listbox(r, height=5); self.lb.pack(fill="x", padx=6, pady=(0, 6))
        self.lb.bind("<Double-1>", self.goto_issue); self._issue_uids = []

        self.tv.bind("<Delete>", lambda e: (self.clear_text_sel(), "break")[1])
        self.tv.bind("<Button-3>", self.context_menu)
        for seq in ("<Control-c>", "<Control-C>"): self.tv.bind(seq, lambda e: (self.copy_sel(), "break")[1])
        for seq in ("<Control-v>", "<Control-V>"): self.tv.bind(seq, lambda e: (self.paste(), "break")[1])
        r.bind("<Control-z>", lambda e: self.undo()); r.bind("<Control-y>", lambda e: self.redo())

    def _preview(self, parent, title):
        f = ttk.LabelFrame(parent, text=title); f.pack(side="left", fill="both", expand=True, padx=3)
        t = tk.Text(f, height=6, wrap="word", font=("Consolas", 11), state="disabled", relief="flat")
        t.pack(fill="both", expand=True); return t

    def _load_theme(self):
        try:
            t = open(os.path.join(APP, "theme.txt"), encoding="utf-8").read().strip()
            return t if t in THEMES else "Standard"
        except Exception:
            return "Standard"

    def apply_theme(self, name):
        T = self.T = THEMES.get(name, THEMES["Standard"]); self.v_theme.set(name)
        try: open(os.path.join(APP, "theme.txt"), "w", encoding="utf-8").write(name)
        except Exception: pass
        st = ttk.Style(); st.theme_use("clam")
        st.configure(".", background=T["bg"], foreground=T["fg"], fieldbackground=T["field"])
        st.configure("TButton", background=T["panel"], foreground=T["fg"], padding=4)
        st.map("TButton", background=[("active", T["acc"])], foreground=[("active", "#ffffff")])
        st.configure("TCheckbutton", background=T["bg"], foreground=T["fg"])
        st.configure("TLabelframe", background=T["bg"]); st.configure("TLabelframe.Label", background=T["bg"], foreground=T["acc"])
        st.configure("Treeview", background=T["panel"], fieldbackground=T["panel"], foreground=T["fg"], rowheight=20)
        st.map("Treeview", background=[("selected", T["acc"])], foreground=[("selected", "#ffffff")])
        st.configure("Treeview.Heading", background=T["field"], foreground=T["fg"])
        self.root.configure(bg=T["bg"])
        for k in ("err", "warn", "done"):
            self.tv.tag_configure(k, background=T[{"done": "ok"}.get(k, k)], foreground=T["fg"])
        self.lb.configure(bg=T["panel"], fg=T["fg"], selectbackground=T["acc"])
        for t in (self.t_o, self.t_t): t.configure(bg=T["pbg"], fg=T["pfg"])

    # ---------------------------------------------------------------- helpers
    def apply_settings(self):
        s = self.p.settings
        try: s.chunk = max(1, int(self.v_n.get()))
        except Exception: pass
        s.numbered, s.allow_src_edit = self.v_num.get(), self.v_src.get()
        s.latin_style, s.charmap = self.v_style.get(), self.v_map.get()
        s.out_encoding = self.v_enc.get()
        s.renpy_lang = self.v_lang.get().strip() or "azerbaijani"
        self.p.dirty = True

    def sel_uids(self):
        return [int(i) for i in self.tv.selection()]

    def sel_ordered(self):
        ss = set(self.sel_uids()); return [u for u in self.shown if u in ss]

    def refresh(self, keep=False):
        keep_sel = self.sel_uids() if keep else []
        dn = self.v_doc.get()
        self.shown = self.p.filter(self.q.get(), self.f_un.get(), self.f_vo.get(), self.f_is.get(),
                                   None if dn == _("(all)") else dn)
        self.tv.delete(*self.tv.get_children())
        for uid in self.shown:
            e = self.p.by_uid[uid]
            self.tv.insert("", "end", iid=str(uid), values=self._vals(e), tags=self._tag(e))
        ks = [str(u) for u in keep_sel if u in self.shown]
        if ks: self.tv.selection_set(ks)
        self._stats()

    def _vals(self, e):
        return (e.number, e.doc.name, e.prefix.strip(), e.src, e.tr,
                f"{len(e.src)}→{len(e.tr)}", "✓" if e.touched else "")

    def _tag(self, e):
        if not e.touched: return ()
        if has_error(e.issues): return ("err",)
        return ("warn",) if e.issues else ("done",)

    def _update_row(self, uid):
        if str(uid) in self.tv.get_children():
            e = self.p.by_uid[uid]
            self.tv.item(str(uid), values=self._vals(e), tags=self._tag(e))

    def _stats(self):
        n = len(self.p.rows); t = sum(1 for e in self.p.rows if e.touched)
        self.info.config(text=_("Total: {n}   Done: {t}   Remaining: {r}   Shown: {s}", n=n, t=t, r=n - t, s=len(self.shown)))

    # ---------------------------------------------------------------- actions
    def open_folder(self):
        import re
        d = filedialog.askdirectory(title=_("Folder with .crm or .rpy files"))
        if not d: return
        ps = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith((".crm", ".rpy"))]
        ps.sort(key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", os.path.basename(s).lower())])
        if not ps: return messagebox.showinfo(_("Open folder"), _("No .crm or .rpy files in that folder."))
        self.open_files(ps)

    def open_files(self, ps=None):
        if ps is None:
            ps = filedialog.askopenfilenames(title=_("Game files (.tra / .dta / .crm / .rpy)"), filetypes=[(_("Game files"), "*.tra *.dta *.crm *.rpy"), (_("All files"), "*.*")])
        if not ps: return
        names = "\n".join(os.path.basename(x) for x in ps[:15]) + (_("\n... and {n} more", n=len(ps) - 15) if len(ps) > 15 else "")
        if self.p.docs:
            a = messagebox.askyesnocancel(_("Add file"), _("Selected:\n{names}\n\nYes = close the current file(s) and open the new one (your progress is saved)\nNo = add next to the current file(s)\nCancel = do nothing", names=names))
            if a is None: return
            if a: self.p.save_all(); self.p.close_all()
        elif not messagebox.askyesno(_("Open"), _("Open these file(s)?\n{names}\n\n(The original is never changed; a backup is made.)", names=names)):
            return
        opened, errs = self.p.open_files(ps)
        if errs: messagebox.showerror(_("Could not open"), "\n".join(errs))
        self.cb_doc["values"] = [_("(all)")] + [d.name for d in self.p.docs]
        self.v_doc.set(opened[0].name if opened else _("(all)"))
        self.q.set(""); self.f_un.set(False); self.f_vo.set(False); self.f_is.set(False)
        self.v_num.set(self.p.settings.numbered); self.v_src.set(self.p.settings.allow_src_edit)
        self.v_style.set(self.p.settings.latin_style); self.v_map.set(self.p.settings.charmap); self.v_enc.set(self.p.settings.out_encoding); self.v_lang.set(self.p.settings.renpy_lang)
        self.refresh()
        kids = self.tv.get_children()
        if kids: self.tv.selection_set(kids[0]); self.tv.see(kids[0])
        self.info.config(text=_("Opened: {names}. A backup was saved to 'backups'.", names=", ".join(d.name for d in opened)))

    def backup(self):
        if not self.p.docs: return messagebox.showinfo(_("Backup"), _("Open a file first."))
        messagebox.showinfo(_("Backup"), _("Original file and project saved to:\n{path}", path=self.p.backup_now()))

    def save(self):
        self.apply_settings(); self.p.save_all(); self.info.config(text=_("Project saved (projects/)."))

    def _autosave(self):
        if self.p.dirty: self.p.save_all()
        self.root.after(60000, self._autosave)

    def on_close(self):
        if self.p.dirty: self.p.save_all()
        self.root.destroy()

    def smart_copy(self):
        self.apply_settings()
        sel = self.sel_uids()
        pick = self.p.next_untranslated(self.shown, self.p.settings.chunk, sel[0] if sel else None)
        if not pick: return messagebox.showinfo(_("Done"), _("No untranslated lines left."))
        self.tv.selection_set([str(u) for u in pick]); self.tv.see(str(pick[0]))
        self._to_clip(self.p.copy_text(pick))
        self.info.config(text=_("{n} lines selected and copied. Paste into your translator, copy the result, then press 'Paste'.", n=len(pick)))

    def copy_sel(self):
        self.apply_settings(); sel = self.sel_ordered()
        if sel:
            self._to_clip(self.p.copy_text(sel)); self.info.config(text=_("{n} lines copied.", n=len(sel)))

    def _to_clip(self, t):
        self.root.clipboard_clear(); self.root.clipboard_append(t); self.root.update()

    def paste(self):
        try: text = self.root.clipboard_get()
        except tk.TclError: return messagebox.showwarning(_("Clipboard"), _("The clipboard is empty."))
        plan = self.p.plan_paste(text, self.sel_ordered(), self.shown)
        if not plan["pairs"]:
            return messagebox.showwarning(_("Paste"), "\n".join(plan["warnings"]) or _("Nothing to write."))
        msg = _("{n} lines will be written ({mode}).", n=len(plan["pairs"]), mode=plan["mode"])
        if plan["overwrite"]: msg += _("\n{n} already-done translations will be overwritten.", n=plan["overwrite"])
        if plan["warnings"]: msg += "\n\n" + "\n".join(plan["warnings"])
        if (plan["count_mismatch"] or plan["overwrite"] or plan["warnings"]) and \
                not messagebox.askyesno(_("Confirm"), msg + "\n\n" + _("Continue?"), default="no"):
            return
        self.p.apply_plan(plan)
        for u, _t in plan["pairs"]: self._update_row(u)
        last = str(plan["pairs"][-1][0])
        if last in self.tv.get_children(): self.tv.see(last)
        self.validate(quiet=True)
        self.info.config(text=_("{n} lines pasted (Ctrl+Z to undo).", n=len(plan["pairs"])))

    def mark(self, done):
        sel = self.sel_ordered()
        n = self.p.mark(sel, done)
        for u in sel: self._update_row(u)
        self._stats(); self.info.config(text=(_("{n} lines marked done.", n=n) if done else _("{n} lines marked not done.", n=n)))

    # ---------------------------------------------------------------- bulk clear / context menu
    def clear_text_sel(self):
        """Delete key / 'Clear': empty the translation of every selected line (Ctrl+Z undoes it)."""
        if self.root.focus_get() is not self.tv and isinstance(self.root.focus_get(), (ttk.Entry, tk.Entry)):
            return          # Delete inside a cell editor / entry must edit text, not clear rows
        sel = self.sel_ordered()
        if not sel: return
        if len(sel) > 50 and not messagebox.askyesno(_("Clear"), _("Clear the translation of {n} lines? (Ctrl+Z undoes this.)", n=len(sel))):
            return
        n = self.p.clear_text(sel)
        self._after_bulk(sel, _("{n} line(s) cleared.", n=n))

    def copy_source_sel(self):
        sel = self.sel_ordered()
        n = self.p.copy_source(sel) if sel else 0
        self._after_bulk(sel, _("{n} line(s): source copied to translation.", n=n))

    def _after_bulk(self, sel, msg):
        for u in sel:
            e = self.p.by_uid[u]; e.issues = check_entry(e, self.p.settings) if e.touched else []
            self._update_row(u)
        self.on_sel(); self._stats(); self.info.config(text=msg)

    def context_menu(self, ev):
        iid = self.tv.identify_row(ev.y)
        if iid and iid not in self.tv.selection():
            self.tv.selection_set(iid)
        if not self.tv.selection(): return
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=_("Clear translation (Del)"), command=self.clear_text_sel)
        m.add_command(label=_("Revert to original"), command=self.clear_sel)
        m.add_command(label=_("Copy source \u2192 translation"), command=self.copy_source_sel)
        m.add_separator()
        m.add_command(label=_("Mark done"), command=lambda: self.mark(True))
        m.add_command(label=_("Mark not done"), command=lambda: self.mark(False))
        m.add_separator()
        m.add_command(label=_("Copy selected (Ctrl+C)"), command=self.copy_sel)
        m.add_command(label=_("Paste (Ctrl+V)"), command=self.paste)
        try: m.tk_popup(ev.x_root, ev.y_root)
        finally: m.grab_release()
        return "break"

    # ---------------------------------------------------------------- settings dialog
    def open_settings(self):
        SettingsDialog(self)

    def clear_sel(self):
        sel = self.sel_ordered()
        if not sel: return messagebox.showinfo(_("Clear"), _("Select some rows first."))
        if not messagebox.askyesno(_("Revert translations"), _("Revert {n} selected line(s)?\nThey go back to what they were when the file was opened. (Ctrl+Z undoes this.)", n=len(sel))):
            return
        n = self.p.clear_translations(sel)
        for u in sel:
            e = self.p.by_uid[u]; e.issues = check_entry(e, self.p.settings) if e.touched else []
            self._update_row(u)
        self.on_sel(); self._stats(); self.info.config(text=_("{n} line(s) cleared.", n=n))

    KEYSYM_CHARS = {"schwa": "\u0259", "SCHWA": "\u018f", "U0259": "\u0259", "U018F": "\u018f", "idotless": "\u0131",
                    "Iabovedot": "\u0130", "U0131": "\u0131", "U0130": "\u0130"}

    def _type_key(self, ent, ev):
        """Direct typing: the schwa key of an Azerbaijani keyboard layout."""
        if ev.state & 0x4 or ev.state & 0x20000:   # Ctrl / Alt: leave to normal shortcuts
            return None
        ch = self.KEYSYM_CHARS.get(ev.keysym)
        if ch is None and ev.keycode == 192 and ev.char == "?":
            # Windows delivers the Azerbaijani schwa key as a plain '?' (keycode 192); Shift or CapsLock -> capital
            ch = "\u018f" if (ev.state & 0x1) != (ev.state & 0x2) // 2 else "\u0259"
        if ch is None: return None
        try:
            if ent.selection_present(): ent.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        ent.insert("insert", ch)
        return "break"

    def edit_cell(self, ev):
        iid, col = self.tv.identify_row(ev.y), self.tv.identify_column(ev.x)
        if not iid or col not in ("#4", "#5"): return
        if col == "#4" and not self.p.settings.allow_src_edit:
            if not messagebox.askyesno(
                    _("Edit Source?"),
                    _("The game finds each entry by its Source (English) text.\nIf you change it, the game will no longer match that entry (it will show the original English).\n\nEnable Source editing?"), default="no"):
                return
            self.v_src.set(True); self.apply_settings()
        x, y, w, h = self.tv.bbox(iid, "orig" if col == "#4" else "tr"); uid = int(iid)
        e = self.p.by_uid[uid]
        ent = ttk.Entry(self.tv); ent.place(x=x, y=y, width=w, height=h)
        ent.insert(0, e.src if col == "#4" else e.tr); ent.focus()
        self._edit_entry = ent
        ent.bind("<KeyPress>", lambda ev, w=ent: self._type_key(w, ev))
        for k, ch in self.ALT_KEYS.items():
            ent.bind(f"<Alt-{k}>", lambda ev, c=ch: (ent.insert("insert", c), "break")[1])

        def done(_ev=None):
            val = ent.get()
            if col == "#4": self.p.set_source(uid, val)
            else: self.p.set_translation(uid, val)
            ent.destroy()
            e.issues = check_entry(e, self.p.settings) if e.touched else []
            self._update_row(uid); self.on_sel(); self._stats()
        ent.bind("<Return>", done); ent.bind("<FocusOut>", done); ent.bind("<Escape>", lambda ev2: ent.destroy())

    ALT_KEYS = {"e": "\u0259", "E": "\u018f", "i": "\u0131", "I": "\u0130", "g": "\u011f", "G": "\u011e",
                "s": "\u015f", "S": "\u015e", "c": "\u00e7", "C": "\u00c7", "o": "\u00f6", "O": "\u00d6",
                "u": "\u00fc", "U": "\u00dc"}

    def _hist(self, uids):
        for u in uids or []: self._update_row(u)
        self._stats()

    def undo(self): self._hist(self.p.undo())
    def redo(self): self._hist(self.p.redo())

    # ---------------------------------------------------------------- rubber-band selection
    def rb_press(self, ev):
        if ev.state & 0x0005: return None
        if self.tv.identify_region(ev.x, ev.y) not in ("cell", "tree", "nothing"): return None
        kids = self.tv.get_children()
        if not kids: return "break"
        row = self.tv.identify_row(ev.y) or (kids[-1] if ev.y > 0 else kids[0])
        self._rb = {"anchor": row, "x0": ev.x, "x": ev.x, "y": ev.y}
        self.tv.focus_set(); self.tv.selection_set(row); self.tv.focus(row)
        return "break"

    def rb_move(self, ev):
        if not self._rb: return
        self._rb.update(x=ev.x, y=ev.y); self._rb_update(); self._rb_scroll()

    def _rb_scroll(self):
        rb = self._rb
        if not rb: return
        h, y = self.tv.winfo_height(), rb["y"]
        if y < 22: self.tv.yview_scroll(-1, "units")
        elif y > h - 4: self.tv.yview_scroll(1, "units")
        else: return
        self._rb_update(); self.root.after(40, self._rb_scroll)

    def _rb_update(self):
        rb = self._rb
        if not rb: return
        kids = self.tv.get_children(); h = self.tv.winfo_height()
        cur = self.tv.identify_row(rb["y"]) or (kids[-1] if rb["y"] > 22 else kids[0])
        i, j = sorted((kids.index(rb["anchor"]), kids.index(cur)))
        self.tv.selection_set(kids[i:j + 1])
        bb = self.tv.bbox(rb["anchor"])
        ay = (bb[1] + bb[3] // 2) if bb else (-5 if kids.index(rb["anchor"]) < kids.index(cur) else h + 5)
        x1, x2 = sorted((rb["x0"], rb["x"])); y1, y2 = sorted((ay, rb["y"]))
        y1, y2 = max(y1, 0), min(y2, h - 1); w, hh = max(x2 - x1, 1), max(y2 - y1, 1)
        for f, (x, y, ww, hg) in zip(self._rb_frames, ((x1, y1, w, 2), (x1, y2, w, 2), (x1, y1, 2, hh), (x2, y1, 2, hh))):
            f.configure(bg=self.T["acc"]); f.place(x=x, y=y, width=ww, height=hg)

    def rb_release(self, ev):
        for f in self._rb_frames: f.place_forget()
        self._rb = None

    # ---------------------------------------------------------------- validate / preview / export
    def validate(self, quiet=False):
        self.apply_settings()
        res, st = self.p.validate()
        self.lb.delete(0, "end"); self._issue_uids = []
        for e, s, c, m in res:
            self.lb.insert("end", f"[{s}] #{e.number} {e.doc.name}: {m}"); self._issue_uids.append(e.uid)
        for uid in self.shown: self._update_row(uid)
        errs = sum(1 for r in res if r[1] == ERR)
        self.info.config(text=_("Validation: {e} errors, {w} warnings, {d} done of {t}.", e=errs, w=len(res) - errs, d=st["DONE"], t=st["TOTAL"]))
        if not quiet and not res: messagebox.showinfo(_("Validate"), _("No problems found."))

    def goto_issue(self, _ev=None):
        i = self.lb.curselection()
        if i:
            uid = self._issue_uids[i[0]]
            if str(uid) not in self.tv.get_children():
                self.f_un.set(False); self.f_vo.set(False); self.f_is.set(False); self.q.set(""); self.refresh()
            self.tv.selection_set(str(uid)); self.tv.see(str(uid))

    def _show(self, t, text):
        t.configure(state="normal"); t.delete("1.0", "end"); t.insert("1.0", text.replace("[", "\n")); t.configure(state="disabled")

    def on_sel(self, _ev=None):
        s = self.sel_uids()
        if not s: return
        e = self.p.by_uid[s[0]]
        self._show(self.t_o, e.src); self._show(self.t_t, e.tr if e.tr else _("(no translation)"))

    def export(self):
        self.apply_settings()
        res, st = self.p.validate()
        errs = [r for r in res if r[1] == ERR]
        if errs and not messagebox.askyesno(_("Errors found"), _("{n} lines have errors (e.g. lost placeholders). Export anyway?", n=len(errs)), default="no"):
            return
        d = filedialog.askdirectory(title=_("Export folder (must DIFFER from the original)"))
        if not d: return
        try: out = self.p.export_all(d)
        except Exception as ex: return messagebox.showerror(_("Export"), str(ex))
        self.save()
        tip = (_("\n\nRen'Py: put these files into  game/tl/{lang}/  (a NEW folder; the original files stay untouched).", lang=self.p.settings.renpy_lang)
               if any(getattr(doc, "renpy", False) for doc, _p in out)
               else _("\n\nTo test: back up the game's original file, then copy this file over it."))
        messagebox.showinfo(_("Export complete"), "\n".join(f"{doc.name} → {path}" for doc, path in out) + tip)

