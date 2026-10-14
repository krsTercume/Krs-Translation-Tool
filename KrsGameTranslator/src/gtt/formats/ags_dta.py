"""game28.dta and room .crm (compiled scripts)."""
import struct as _struct
import hashlib, json, os, re, shutil, struct, time
from collections import Counter
import re
from ..common import *  # noqa
from ..model import *  # noqa
from ..model import _bytes_to_text, _text_to_bytes, _make_entry  # noqa
from .ags_script import *  # noqa
from .ags_script import _KEY, _NEWSCRIPT, _decrypt, _encrypt, _looks_text  # noqa

class DtaDoc:
    """AGS compiled game data (e.g. game28.dta): edits dialogue/text strings inside the scripts."""

    empty_keeps_original = True

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        with open(path, "rb") as f:
            self.data = f.read()
        if not self.data.startswith(b"Adventure Creator Game File"):
            raise ValueError(f"{self.name}: not an AGS game data file")
        self.scripts, self.entries = [], []
        p = 0
        while True:
            p = self.data.find(b"SCOM", p)
            if p < 0:
                break
            try:
                sc = CCScript(self.data, p)
            except Exception:
                p += 4
                continue
            self.scripts.append(sc)
            p = sc.end
        if not self.scripts:
            raise ValueError(f"{self.name}: no compiled scripts found")
        idx = 0
        for si, sc in enumerate(self.scripts):
            if sc.to_bytes() != self.data[sc.start:sc.end]:
                raise ValueError(f"{self.name}: script #{si} does not round-trip; refusing to edit")
            for pi, raw in enumerate(sc.pool()):
                if _looks_text(raw):
                    t = _bytes_to_text(raw)
                    e = _make_entry(self, idx, t, t, (si, pi, raw))
                    self.entries.append(e); idx += 1
        self.tail = []

    def build_bytes(self, settings):
        per = {}
        for e in self.entries:
            if e.changed:
                si, pi, _raw = e.meta
                per.setdefault(si, {})[pi] = _text_to_bytes(e.tr_prefix + e.tr, settings)
        out, pos = [], 0
        for si, sc in enumerate(self.scripts):
            out.append(self.data[pos:sc.start])
            out.append(sc.rebuild(per[si]) if si in per else self.data[sc.start:sc.end])
            pos = sc.end
        out.append(self.data[pos:])
        return b"".join(out)

    def verify(self, newdata, settings):
        """Re-parse the new file: every code string reference must still point at the right text."""
        sc2, p = [], 0
        while True:
            p = newdata.find(b"SCOM", p)
            if p < 0:
                break
            try:
                s = CCScript(newdata, p)
            except Exception:
                p += 4
                continue
            sc2.append(s); p = s.end
        if len(sc2) != len(self.scripts):
            raise RuntimeError("Export error: script count changed. Nothing was written.")
        repl = {}
        for e in self.entries:
            if e.changed:
                si, pi, _r = e.meta
                repl.setdefault(si, {})[pi] = _text_to_bytes(e.tr_prefix + e.tr, settings)
        for si, (a, b) in enumerate(zip(self.scripts, sc2)):
            oldp = a.pool(); r = repl.get(si, {})
            starts, o = [], 0
            for s in oldp:
                starts.append(o); o += len(s) + 1
            import bisect
            for (pos_a, off_a), (pos_b, off_b) in zip(a.string_refs(), b.string_refs()):
                i = bisect.bisect_right(starts, off_a) - 1
                want = r.get(i, oldp[i])[off_a - starts[i]:] if off_a != starts[i] else r.get(i, oldp[i])
                got = b.strings[off_b:b.strings.index(b"\0", off_b)]
                if pos_a != pos_b or (off_a == starts[i] and got != want):
                    raise RuntimeError(f"Export error: string reference mismatch in script {si}. Nothing was written.")
            if a.code != b.code and not r:
                raise RuntimeError(f"Export error: script {si} changed unexpectedly. Nothing was written.")


class CrmDoc(DtaDoc):
    """AGS room file (roomN.crm): edits dialogue strings in the room's compiled script."""

    def __init__(self, path):
        with open(path, "rb") as f:
            head = f.read(4)
        if len(head) < 4 or _struct.unpack_from("<h", head, 0)[0] < 20 or head[2] != 1:
            raise ValueError(f"{os.path.basename(path)}: not an AGS room file")
        # DtaDoc.__init__ checks the dta magic, so load the same way here
        self.path = path
        self.name = os.path.basename(path)
        with open(path, "rb") as f:
            self.data = f.read()
        self.scripts, self.entries = [], []
        p = 0
        while True:
            p = self.data.find(b"SCOM", p)
            if p < 0:
                break
            try:
                sc = CCScript(self.data, p)
            except Exception:
                p += 4
                continue
            self.scripts.append(sc)
            p = sc.end
        if not self.scripts:
            raise ValueError(f"{self.name}: no compiled script found in room file")
        idx = 0
        for si, sc in enumerate(self.scripts):
            if sc.to_bytes() != self.data[sc.start:sc.end]:
                raise ValueError(f"{self.name}: script #{si} does not round-trip; refusing to edit")
            if sc.start < 9 or self.data[sc.start - 9] != 7 or \
                    _struct.unpack_from("<Q", self.data, sc.start - 8)[0] != sc.end - sc.start:
                raise ValueError(f"{self.name}: script block header not recognised; refusing to edit")
            for pi, raw in enumerate(sc.pool()):
                if _looks_text(raw):
                    t = _bytes_to_text(raw)
                    e = _make_entry(self, idx, t, t, (si, pi, raw))
                    self.entries.append(e); idx += 1
        self.tail = []

    def build_bytes(self, settings):
        per = {}
        for e in self.entries:
            if e.changed:
                si, pi, _raw = e.meta
                per.setdefault(si, {})[pi] = _text_to_bytes(e.tr_prefix + e.tr, settings)
        out, pos = [], 0
        for si, sc in enumerate(self.scripts):
            out.append(self.data[pos:sc.start - 8])
            new = sc.rebuild(per[si]) if si in per else self.data[sc.start:sc.end]
            out.append(_struct.pack("<Q", len(new)))   # block length (8 bytes) before the script
            out.append(new)
            pos = sc.end
        out.append(self.data[pos:])
        return b"".join(out)

    def verify(self, newdata, settings):
        # block header of every script must match its new length
        p, n = 0, 0
        while True:
            p = newdata.find(b"SCOM", p)
            if p < 0:
                break
            try:
                s = CCScript(newdata, p)
            except Exception:
                p += 4
                continue
            if newdata[p - 9] != 7 or _struct.unpack_from("<Q", newdata, p - 8)[0] != s.end - p:
                raise RuntimeError("Export error: room block length wrong. Nothing was written.")
            n += 1; p = s.end
        if n != len(self.scripts):
            raise RuntimeError("Export error: script count changed. Nothing was written.")
        DtaDoc.verify(self, newdata, settings)


