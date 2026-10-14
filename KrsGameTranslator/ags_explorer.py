#!/usr/bin/env python3
"""
AGS Explorer - Adventure Game Studio oyun arxivlərini (exe / .ags / .vox) açır,
tree-də göstərir, önizləmə, çıxarma, əvəzləmə, .tra redaktəsi və yenidən yığma.

Quraşdırma:  pip install PyQt6
İşlətmə:     python ags_explorer.py [oyun.exe]

DİQQƏT: CLIB parseri yaddaşdakı format biliyinə əsaslanır və real fayllarla
test olunmayıb. Parse alınmasa xəta mesajında başlığın hex-i çıxır.
"""
import sys, os, struct, mmap

KEY_TEXT = b"My\x01\xde\x04Jibzle"
TAIL_SIGS = (b"CLIB\x01\x02\x03\x04SIGE", b"CLIB\x01\x02\x03\x04SIGN")
TAIL_SIG = TAIL_SIGS[0]
KNOWN_VERS = (10, 11, 15, 20, 21, 30)
HEAD_SIG = b"CLIB\x1a"
SALT = 9338638
TRA_KEY = b"Avis Durgan"
TRA_SIG = b"AGSTranslation\0"


# ------------------------------------------------------------------ helpers
class Rnd:
    def __init__(s, seed):
        s.v = seed & 0xFFFFFFFF

    def next(s):
        s.v = (s.v * 214013 + 2531011) & 0xFFFFFFFF
        return (s.v >> 16) & 0x7FFF


def dec_text(b):
    b = b.split(b"\0", 1)[0]
    return bytes((c - KEY_TEXT[i % 11]) & 0xFF for i, c in enumerate(b)).decode("latin-1")


def enc_text(s):
    return bytes((c + KEY_TEXT[i % 11]) & 0xFF for i, c in enumerate(s.encode("latin-1")))


def i32(v):
    return struct.pack("<I", v & 0xFFFFFFFF)


class R:
    def __init__(s, d, p):
        s.d, s.p = d, p

    def raw(s, n):
        b = s.d[s.p:s.p + n]
        if len(b) < n:
            raise ValueError("EOF")
        s.p += n
        return b

    def u8(s):
        return s.raw(1)[0]

    def i32(s):
        return struct.unpack("<i", s.raw(4))[0]

    def i64(s):
        return struct.unpack("<q", s.raw(8))[0]

    def cstr(s):
        out = bytearray()
        while True:
            c = s.u8()
            if c == 0:
                return out.decode("latin-1")
            out.append(c)
            if len(out) > 1000:
                raise ValueError("long string")


def chk(c):
    if not c:
        raise ValueError("bad value")


# ------------------------------------------------------------------ CLIB parse
V30_LAYOUTS = [
    (("uid", "u8"), ("off", "i64"), ("len", "i64")),
    (("off", "i64"), ("len", "i64"), ("uid", "u8")),
    (("uid", "u8"), ("off", "i32"), ("len", "i32")),
    (("off", "i32"), ("len", "i32"), ("uid", "u8")),
    (("off", "i64"), ("len", "i64")),
    (("off", "i32"), ("len", "i32")),
]


def attempts(ver):
    old = [dict(kind="old", ver=ver, name_len=n) for n in ((100, 25) if ver >= 11 else (25, 100))]
    enc = [dict(kind="enc", ver=ver, mode=m, layout=l, libenc=le)
           for le in (False, True) for l in ("inter", "arrays") for m in ("sub", "none")]
    v30 = [dict(kind="v30", ver=ver, lead=ld, lay=i)
           for ld in (6, 5, 1, 0, 2, 3, 4) for i in range(len(V30_LAYOUTS))]
    if ver <= 15:
        return old
    if ver in (20, 21):
        return enc + old
    return v30


def parse_variant(d, pos, v):
    r = R(d, pos + 6)
    k = v["kind"]
    if k == "v30":
        r.raw(v["lead"])
        mfc = r.i32(); chk(1 <= mfc <= 500)
        libnames = [r.cstr() for _ in range(mfc)]
        n = r.i32(); chk(0 < n < 500000)
        lay = V30_LAYOUTS[v["lay"]]
        assets = []
        for _ in range(n):
            nm = r.cstr(); f = {"uid": 0, "off": 0, "len": 0}
            for fld, t in lay:
                f[fld] = r.u8() if t == "u8" else (r.i64() if t == "i64" else r.i32())
            assets.append([nm, f["uid"], f["off"], f["len"]])
        return libnames, assets, r.p
    v["pm"] = r.u8(); r.u8()
    mfc = r.i32(); chk(1 <= mfc <= 500)
    if k == "old":
        libnames = [r.raw(20).split(b"\0")[0].decode("latin-1") for _ in range(mfc)]
        n = r.i32(); chk(0 < n < 500000)
        names = [dec_text(r.raw(v["name_len"])) for _ in range(n)]
        offs = [r.i32() for _ in range(n)]
        lens = [r.i32() for _ in range(n)]
        uids = [r.u8() for _ in range(n)]
        return libnames, [list(x) for x in zip(names, uids, offs, lens)], r.p
    rnd = Rnd(v["pm"] + SALT)
    sub = v["mode"] == "sub"

    def gi():
        x = r.i32()
        return x - rnd.next() if sub else x

    def gb():
        x = r.u8()
        return (x - rnd.next()) & 0xFF if sub else x

    def gs():
        out = bytearray()
        while True:
            c = (r.u8() - rnd.next()) & 0xFF
            if c == 0:
                return out.decode("latin-1")
            out.append(c)
            if len(out) > 1000:
                raise ValueError("long")
    if v["libenc"]:
        libnames = [gs() for _ in range(mfc)]
    else:
        libnames = [r.raw(20).split(b"\0")[0].decode("latin-1") for _ in range(mfc)]
    n = gi(); chk(0 < n < 500000)
    if v["layout"] == "inter":
        assets = []
        for _ in range(n):
            nm = gs(); off = gi(); ln = gi(); uid = gb()
            assets.append([nm, uid, off, ln])
    else:
        names = [gs() for _ in range(n)]
        offs = [gi() for _ in range(n)]
        lens = [gi() for _ in range(n)]
        uids = [gb() for _ in range(n)]
        assets = [list(x) for x in zip(names, uids, offs, lens)]
    return libnames, assets, r.p


def valid(assets, libnames, size):
    for nm, uid, off, ln in assets:
        if not nm or any(32 > ord(c) or ord(c) == 127 for c in nm):
            return False
        if off < 0 or ln < 0 or off > 1 << 42 or uid >= len(libnames):
            return False
        if uid == 0 and off + ln > size:
            return False
    return True


def build_header(v, libnames, assets):
    """assets: list of (name, uid, off, len)"""
    b = bytearray(HEAD_SIG + bytes([v["ver"]]))
    k = v["kind"]
    ln0 = libnames[0] if libnames else ""
    n = len(assets)
    if k == "v30":
        b += b"\0" * v["lead"]
        b += i32(len(libnames))
        for x in libnames:
            b += x.encode("latin-1") + b"\0"
        b += i32(n)
        for nm, uid, off, ln in assets:
            b += nm.encode("latin-1") + b"\0"
            f = {"uid": uid, "off": off, "len": ln}
            for fld, t in V30_LAYOUTS[v["lay"]]:
                b += bytes([f[fld]]) if t == "u8" else (struct.pack("<q", f[fld]) if t == "i64" else i32(f[fld]))
        return bytes(b)
    b += bytes([v["pm"], 0]) + i32(len(libnames))
    if k == "old":
        for x in libnames:
            b += x.encode("latin-1")[:19].ljust(20, b"\0")
        b += i32(n)
        for nm, *_ in assets:
            b += enc_text(nm)[:v["name_len"] - 1].ljust(v["name_len"], b"\0")
        for a in assets: b += i32(a[2])
        for a in assets: b += i32(a[3])
        for a in assets: b += bytes([a[1]])
        return bytes(b)
    rnd = Rnd(v["pm"] + SALT)
    sub = v["mode"] == "sub"

    def pi(x):
        return i32(x + rnd.next()) if sub else i32(x)

    def pb(x):
        return bytes([(x + rnd.next()) & 0xFF]) if sub else bytes([x])

    def ps(s):
        return bytes((c + rnd.next()) & 0xFF for c in s.encode("latin-1") + b"\0")
    if v["libenc"]:
        for x in libnames:
            b += ps(x)
    else:
        for x in libnames:
            b += x.encode("latin-1")[:19].ljust(20, b"\0")
    b += pi(n)
    if v["layout"] == "inter":
        for nm, uid, off, ln in assets:
            b += ps(nm) + pi(off) + pi(ln) + pb(uid)
    else:
        for a in assets: b += ps(a[0])
        for a in assets: b += pi(a[2])
        for a in assets: b += pi(a[3])
        for a in assets: b += pb(a[1])
    return bytes(b)


class Asset:
    def __init__(s, name, uid, off, ln):
        s.name, s.uid, s.off, s.len, s.data = name, uid, off, ln, None

    @property
    def size(s):
        return len(s.data) if s.data is not None else s.len


class Lib:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        self.d = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        self._locate()

    def _locate(self):
        d, size = self.d, len(self.d)
        cands = []
        tail = d[max(0, size - 64):]
        self.tail_sig = TAIL_SIGS[0]
        for sg in TAIL_SIGS:
            i = tail.rfind(sg)
            if i < 4:
                continue
            offs = [struct.unpack_from("<i", tail, i - 4)[0]]
            if i >= 8:
                offs.append(struct.unpack_from("<q", tail, i - 8)[0])
            for off in offs:
                if 0 <= off < size and d[off:off + 5] == HEAD_SIG:
                    cands.append((off, True)); self.tail_sig = sg
                    break
            if cands:
                break
        if not cands and d[:5] == HEAD_SIG:
            cands.append((0, False))
        if not cands:
            p = 0
            while len(cands) < 50:
                p = d.find(HEAD_SIG, p)
                if p < 0:
                    break
                if d[p + 5] in KNOWN_VERS:
                    cands.append((p, False))
                p += 1
        errs = []
        for hp, ht in cands:
            ver = d[hp + 5]
            for v in attempts(ver):
                try:
                    libnames, assets, hend = parse_variant(d, hp, dict(v))
                    vv = dict(v)
                    libnames, assets, hend = parse_variant(d, hp, vv)
                except Exception as e:
                    errs.append(f"v{ver} {v['kind']}: {e}"); continue
                if valid(assets, libnames, size):
                    self._setup(vv, libnames, assets, hp, hend, ht)
                    return
                errs.append(f"v{ver} {v['kind']}: yoxlama alınmadı")
        hx = ""
        if cands:
            hx = f"(offset {cands[0][0]}) " + d[cands[0][0]:cands[0][0] + 48].hex(" ")
        raise ValueError("CLIB oxunmadı.\n" + ("Başlıq: " + hx + "\n" if hx else "CLIB imzası tapılmadı.\n")
                         + "\n".join(errs[:8]))

    def _setup(self, v, libnames, assets, hp, hend, ht):
        self.variant, self.libnames = v, libnames
        self.assets = [Asset(*a) for a in assets]
        self.hdr_pos, self.hdr_end, self.has_tail = hp, hend, ht
        z = [a for a in self.assets if a.uid == 0]
        mo = min((a.off for a in z), default=0)
        me = max((a.off + a.len for a in z), default=0)
        size = len(self.d)
        tail_start = size - 16 if ht else size
        self.hdr_first = not (hend >= tail_start - 4 and hp > 0 and hp - me >= 0)
        if self.hdr_first:
            self.base = hend - mo
            self.prefix_end = hp
        else:
            self.base = hp - me
            self.prefix_end = self.base + mo
        self.single = all(a.uid == 0 for a in self.assets)

    def get(self, a):
        if a.data is not None:
            return a.data
        if a.uid == 0:
            s = self.base + a.off
            return self.d[s:s + a.len]
        p = os.path.join(os.path.dirname(self.path), self.libnames[a.uid])
        if not os.path.exists(p):
            return b""
        with open(p, "rb") as f:
            f.seek(a.off)
            return f.read(a.len)

    def build(self):
        datas = [self.get(a) for a in self.assets]
        names = [(a.name, a.uid) for a in self.assets]

        def hdr(offs):
            return build_header(self.variant, self.libnames,
                                [(n, u, o, len(x)) for (n, u), o, x in zip(names, offs, datas)])
        prefix = self.d[:self.prefix_end]
        start = self.prefix_end + (len(hdr([0] * len(datas))) if self.hdr_first else 0)
        offs, cur = [], start
        for x in datas:
            offs.append(cur - self.base); cur += len(x)
        h = hdr(offs)
        out = bytearray(prefix)
        if self.hdr_first:
            out += h + b"".join(datas)
            hp = self.prefix_end
        else:
            out += b"".join(datas); hp = len(out); out += h
        if self.has_tail:
            out += i32(hp) + self.tail_sig
        return bytes(out)


# ------------------------------------------------------------------ TRA
def tra_dec(b):
    s = bytes((c - TRA_KEY[i % 11]) & 0xFF for i, c in enumerate(b))
    if s.endswith(b"\0"):
        s = s[:-1]
    try:
        return s.decode("utf-8")
    except UnicodeDecodeError:
        return s.decode("cp1252", "replace")


def tra_enc(s):
    b = s.encode("utf-8") + b"\0"
    return bytes((c + TRA_KEY[i % 11]) & 0xFF for i, c in enumerate(b))


def tra_pairs(blk, sk):
    p, strs = sk, []
    while p < len(blk):
        if p + 4 > len(blk):
            return None
        n = struct.unpack_from("<i", blk, p)[0]; p += 4
        if n < 0 or p + n > len(blk):
            return None
        strs.append(tra_dec(blk[p:p + n])); p += n
    if len(strs) % 2:
        return None
    return list(zip(strs[::2], strs[1::2]))


def tra_load(b):
    if not b.startswith(TRA_SIG):
        return None
    for hl in (15, 19):
        p, blocks = hl, []
        try:
            while p < len(b):
                t, l = struct.unpack_from("<ii", b, p); p += 8
                if l < 0 or p + l > len(b):
                    raise ValueError
                blocks.append((t, b[p:p + l])); p += l
        except Exception:
            continue
        if p == len(b) and blocks and all(0 < t < 20 for t, _ in blocks):
            for bi, (t, blk) in enumerate(blocks):
                if t == 1:
                    for sk in (0, 4, 8):
                        pr = tra_pairs(blk, sk)
                        if pr:
                            return dict(head=b[:hl], blocks=blocks, bi=bi, skip=blk[:sk], pairs=pr)
    return None


def tra_build(st, pairs):
    blk = bytearray(st["skip"])
    for a, t in pairs:
        for s in (a, t):
            e = tra_enc(s)
            blk += i32(len(e)) + e
    out = bytearray(st["head"])
    for i, (t, data) in enumerate(st["blocks"]):
        data = bytes(blk) if i == st["bi"] else data
        out += struct.pack("<ii", t, len(data)) + data
    return bytes(out)


# ------------------------------------------------------------------ GUI
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QSplitter,
                             QStackedWidget, QPlainTextEdit, QLabel, QScrollArea, QTableWidget,
                             QTableWidgetItem, QFileDialog, QMessageBox, QWidget, QVBoxLayout,
                             QPushButton, QMenu, QHeaderView, QLineEdit)
from PyQt6.QtGui import QPixmap, QFont, QFontDatabase, QAction, QKeySequence
from PyQt6.QtCore import Qt, QByteArray

IMG = {"png", "jpg", "jpeg", "bmp", "gif", "webp"}
TXT = {"txt", "ini", "cfg", "json", "xml", "csv", "log", "md", "asc", "inf", "lua", "sh", "bat"}
SAMPLE = "ƏəĞğİıÖöÜüŞşÇç\nABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz 0123456789"


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def hexdump(b, limit=65536):
    out = []
    for i in range(0, min(len(b), limit), 16):
        c = b[i:i + 16]
        out.append(f"{i:08x}  {c.hex(' '):<47}  {''.join(chr(x) if 32 <= x < 127 else '.' for x in c)}")
    if len(b) > limit:
        out.append(f"... ({len(b) - limit} bayt daha)")
    return "\n".join(out)


def looks_text(b):
    if not b or b"\0" in b[:2048]:
        return False
    try:
        b[:4096].decode("utf-8"); return True
    except UnicodeDecodeError:
        return False


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AGS Explorer")
        self.resize(1150, 720)
        self.lib = None
        self.cur = None
        self.fontid = -1
        self.dirty = False
        self.tra = None
        self.textenc = "utf-8"

        left = QWidget(); lv = QVBoxLayout(left)
        self.search = QLineEdit(); self.search.setPlaceholderText("Axtar...")
        self.search.textChanged.connect(self.filter)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Ad", "Ölçü"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.ctx)
        self.tree.currentItemChanged.connect(lambda it, _: self.select(it))
        lv.addWidget(self.search); lv.addWidget(self.tree)

        self.stack = QStackedWidget()
        self.p_info = QLabel("Fayl aç (Ctrl+O)"); self.p_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # text
        tw = QWidget(); tl = QVBoxLayout(tw)
        self.text = QPlainTextEdit(); self.text.setFont(QFont("Consolas", 10))
        b = QPushButton("Dəyişikliyi tətbiq et"); b.clicked.connect(self.apply_text)
        tl.addWidget(self.text); tl.addWidget(b)
        # image
        self.img = QLabel(); self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.p_img = QScrollArea(); self.p_img.setWidget(self.img); self.p_img.setWidgetResizable(True)
        # hex
        self.hex = QPlainTextEdit(); self.hex.setReadOnly(True); self.hex.setFont(QFont("Consolas", 9))
        # font
        self.fontlbl = QLabel(); self.fontlbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # tra
        trw = QWidget(); trl = QVBoxLayout(trw)
        self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(["Orijinal", "Tərcümə"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(True)
        b2 = QPushButton("Tərcüməni tətbiq et"); b2.clicked.connect(self.apply_tra)
        trl.addWidget(self.table); trl.addWidget(b2)
        for w in (self.p_info, tw, self.p_img, self.hex, self.fontlbl, trw):
            self.stack.addWidget(w)

        sp = QSplitter(); sp.addWidget(left); sp.addWidget(self.stack)
        sp.setStretchFactor(1, 3); sp.setSizes([380, 770])
        self.setCentralWidget(sp)

        m = self.menuBar().addMenu("Fayl")
        for t, f, k in (("Aç...", self.open_dlg, QKeySequence.StandardKey.Open),
                        ("Yadda saxla (yeni fayl)...", self.save, QKeySequence.StandardKey.Save),
                        ("Seçilənləri çıxar...", self.extract, None),
                        ("Hamısını çıxar...", self.extract_all, None),
                        ("Seçiləni əvəz et...", self.replace, None)):
            a = QAction(t, self); a.triggered.connect(f)
            if k: a.setShortcut(k)
            m.addAction(a)

    # ---- loading
    def open_dlg(self):
        p, _ = QFileDialog.getOpenFileName(self, "AGS oyunu", "", "AGS (*.exe *.ags *.vox *.ac2 *.dat);;Hamısı (*)")
        if p:
            self.load(p)

    def load(self, path):
        try:
            self.lib = Lib(path)
        except Exception as e:
            QMessageBox.critical(self, "Xəta", str(e)); return
        self.dirty = False
        self.setWindowTitle(f"AGS Explorer - {os.path.basename(path)}")
        self.fill()
        v = self.lib.variant
        self.statusBar().showMessage(
            f"{len(self.lib.assets)} fayl | CLIB v{v['ver']} ({v['kind']}) | hissələr: {', '.join(self.lib.libnames)}"
            + ("" if self.lib.single else " | çox hissəli: yadda saxlama söndürülüb"))

    def fill(self):
        self.tree.clear(); dirs = {}
        for i, a in enumerate(self.lib.assets):
            parts = a.name.replace("\\", "/").split("/")
            parent = self.tree.invisibleRootItem(); path = ""
            for p in parts[:-1]:
                path += "/" + p
                if path not in dirs:
                    it = QTreeWidgetItem(parent, [p, ""]); dirs[path] = it
                parent = dirs[path]
            it = QTreeWidgetItem(parent, [parts[-1], human(a.size)])
            it.setData(0, Qt.ItemDataRole.UserRole, i)
        self.tree.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.tree.expandToDepth(0)

    def item_asset(self, it):
        i = it.data(0, Qt.ItemDataRole.UserRole) if it else None
        return self.lib.assets[i] if i is not None else None

    def filter(self, t):
        t = t.lower()

        def rec(it):
            vis = t in it.text(0).lower()
            for k in range(it.childCount()):
                vis = rec(it.child(k)) or vis
            it.setHidden(not vis and bool(t))
            return vis or not t
        root = self.tree.invisibleRootItem()
        for k in range(root.childCount()):
            rec(root.child(k))

    # ---- preview
    def select(self, it):
        a = self.item_asset(it) if self.lib else None
        if not a:
            return
        self.cur = a
        data = self.lib.get(a)
        ext = a.name.lower().rsplit(".", 1)[-1] if "." in a.name else ""
        self.statusBar().showMessage(f"{a.name} | {human(len(data))} | hissə {a.uid}")
        if ext in IMG:
            pm = QPixmap()
            if pm.loadFromData(bytes(data)):
                self.img.setPixmap(pm); self.stack.setCurrentWidget(self.p_img); return
        if ext in ("ttf", "otf"):
            if self.fontid >= 0:
                QFontDatabase.removeApplicationFont(self.fontid)
            self.fontid = QFontDatabase.addApplicationFontFromData(QByteArray(bytes(data)))
            fam = QFontDatabase.applicationFontFamilies(self.fontid)
            if fam:
                self.fontlbl.setFont(QFont(fam[0], 26)); self.fontlbl.setText(fam[0] + "\n\n" + SAMPLE)
                self.stack.setCurrentWidget(self.fontlbl); return
        if ext == "tra":
            st = tra_load(bytes(data))
            if st:
                self.tra = st; self.table.setRowCount(len(st["pairs"]))
                for r, (o, t) in enumerate(st["pairs"]):
                    io = QTableWidgetItem(o); io.setFlags(io.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(r, 0, io); self.table.setItem(r, 1, QTableWidgetItem(t))
                self.table.resizeRowsToContents()
                self.stack.setCurrentIndex(5); return
        if ext in TXT or looks_text(bytes(data[:4096])):
            try:
                self.text.setPlainText(bytes(data).decode("utf-8")); self.textenc = "utf-8"
            except UnicodeDecodeError:
                self.text.setPlainText(bytes(data).decode("cp1252", "replace")); self.textenc = "cp1252"
            self.stack.setCurrentIndex(1); return
        self.hex.setPlainText(hexdump(bytes(data))); self.stack.setCurrentWidget(self.hex)

    def touch(self, a, data):
        a.data = data; self.dirty = True
        for it in self.tree.findItems("*", Qt.MatchFlag.MatchWildcard | Qt.MatchFlag.MatchRecursive):
            if it.data(0, Qt.ItemDataRole.UserRole) is not None and self.lib.assets[it.data(0, Qt.ItemDataRole.UserRole)] is a:
                it.setText(1, human(len(data)) + " *")

    def apply_text(self):
        if self.cur:
            self.touch(self.cur, self.text.toPlainText().encode(self.textenc, "replace"))

    def apply_tra(self):
        if not (self.cur and self.tra):
            return
        pairs = [(self.table.item(r, 0).text(), self.table.item(r, 1).text()) for r in range(self.table.rowCount())]
        self.touch(self.cur, tra_build(self.tra, pairs))

    # ---- actions
    def ctx(self, pos):
        m = QMenu()
        m.addAction("Çıxar...", self.extract); m.addAction("Əvəz et...", self.replace)
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def collect(self, it, prefix=""):
        a = self.item_asset(it)
        if a:
            return [(prefix + it.text(0), a)]
        out = []
        for k in range(it.childCount()):
            out += self.collect(it.child(k), prefix + it.text(0) + "/")
        return out

    def extract(self):
        it = self.tree.currentItem()
        if not (self.lib and it):
            return
        a = self.item_asset(it)
        if a:
            p, _ = QFileDialog.getSaveFileName(self, "Çıxar", os.path.basename(a.name.replace("\\", "/")))
            if p:
                open(p, "wb").write(self.lib.get(a))
            return
        d = QFileDialog.getExistingDirectory(self, "Qovluq seç")
        if d:
            self.write_all(self.collect(it), d, strip=it.text(0) + "/")

    def extract_all(self):
        if not self.lib:
            return
        d = QFileDialog.getExistingDirectory(self, "Qovluq seç")
        if d:
            root = self.tree.invisibleRootItem(); items = []
            for k in range(root.childCount()):
                items += self.collect(root.child(k))
            self.write_all(items, d)

    def write_all(self, items, d, strip=""):
        for rel, a in items:
            if strip and rel.startswith(strip):
                rel = rel[len(strip):]
            p = os.path.join(d, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(self.lib.get(a))
        QMessageBox.information(self, "Hazır", f"{len(items)} fayl çıxarıldı.")

    def replace(self):
        a = self.cur
        if not a:
            return
        p, _ = QFileDialog.getOpenFileName(self, f"{a.name} əvəzinə")
        if p:
            self.touch(a, open(p, "rb").read()); self.select(self.tree.currentItem())

    def save(self):
        if not self.lib:
            return
        if not self.lib.single:
            QMessageBox.warning(self, "Saxlanmır", "Çox hissəli arxivlər (ayrıca .ags/.vox) hələ dəstəklənmir."); return
        p, _ = QFileDialog.getSaveFileName(self, "Yeni fayl kimi saxla", self.lib.path + ".new")
        if not p or os.path.abspath(p) == os.path.abspath(self.lib.path):
            if p:
                QMessageBox.warning(self, "Xəta", "Orijinalın üzərinə yazmaq olmaz. Başqa ad seç.")
            return
        try:
            open(p, "wb").write(self.lib.build())
            QMessageBox.information(self, "Hazır", "Saxlanıldı. Orijinalı yedəkdə saxla və yeni faylı oyunla yoxla.")
        except Exception as e:
            QMessageBox.critical(self, "Xəta", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Main(); w.show()
    if len(sys.argv) > 1:
        w.load(sys.argv[1])
    sys.exit(app.exec())
