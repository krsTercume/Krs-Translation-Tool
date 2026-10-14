"""AGS compiled script (SCOM) + obfuscation helpers."""
import struct as _struct
import hashlib, json, os, re, shutil, struct, time
from collections import Counter
import re
from ..common import *  # noqa
from ..model import *  # noqa
from ..model import _bytes_to_text, _text_to_bytes, _make_entry  # noqa

_KEY = b"Avis Durgan"
_NEWSCRIPT = b"__NEWSCRIPTSTART_"


def _decrypt(b):
    out, a = bytearray(), 0
    for c in b:
        out.append((c - _KEY[a]) & 255)
        a = (a + 1) % 11
    return bytes(out)


def _encrypt(b):
    out, a = bytearray(), 0
    for c in b:
        out.append((c + _KEY[a]) & 255)
        a = (a + 1) % 11
    return bytes(out)


def _bytes_to_text(b):
    """UTF-8 if valid and non-ASCII, else cp1252, else latin-1 (display only)."""
    try:
        return b.decode("ascii")
    except UnicodeDecodeError:
        pass
    for enc in ("utf-8", "cp1252"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1")


def _text_to_bytes(t, settings):
    t = apply_charmap(t, parse_charmap(settings.charmap))
    enc = getattr(settings, "out_encoding", "utf-8")
    return t.encode(enc, errors="replace")



class CCScript:
    """One compiled AGS script (SCOM). Only the string pool is edited; the rest is kept raw."""

    def __init__(self, data, p):
        self.start = p
        if data[p:p + 4] != b"SCOM":
            raise ValueError("no SCOM")
        p += 4
        self.ver, gd, cs, ss = _struct.unpack_from("<iiii", data, p)
        if not (80 <= self.ver <= 120) or min(gd, cs, ss) < 0 or cs > 5_000_000 or ss > 50_000_000:
            raise ValueError("implausible header")
        p += 16
        self.gdata = data[p:p + gd]; p += gd
        self.code = list(_struct.unpack_from("<%di" % cs, data, p)); p += cs * 4
        self.strings = data[p:p + ss]; p += ss
        if len(self.strings) != ss or (ss and not self.strings.endswith(b"\0")):
            raise ValueError("bad string pool")
        nf, = _struct.unpack_from("<i", data, p); p += 4
        if nf < 0 or nf > cs:
            raise ValueError("bad fixups")
        self.ftypes = data[p:p + nf]; p += nf
        self.fixups = list(_struct.unpack_from("<%di" % nf, data, p)); p += nf * 4
        tail_start = p
        ni, = _struct.unpack_from("<i", data, p); p += 4
        for _ in range(ni):
            p = data.index(b"\0", p) + 1
        nx, = _struct.unpack_from("<i", data, p); p += 4
        for _ in range(nx):
            p = data.index(b"\0", p) + 1 + 4
        if self.ver >= 83:
            nsec, = _struct.unpack_from("<i", data, p); p += 4
            for _ in range(nsec):
                p = data.index(b"\0", p) + 1 + 4
        if _struct.unpack_from("<I", data, p)[0] != 0xBEEFCAFE:
            raise ValueError("no end marker")
        p += 4
        self.tail = data[tail_start:p]
        self.end = p
        for k, t in enumerate(self.ftypes):
            if t == 3 and not (0 <= self.code[self.fixups[k]] < max(ss, 1)):
                raise ValueError("string fixup out of range")

    def pool(self):
        return self.strings.split(b"\0")[:-1]

    def to_bytes(self, strings=None, code=None):
        strings = self.strings if strings is None else strings
        code = self.code if code is None else code
        head = b"SCOM" + _struct.pack("<iiii", self.ver, len(self.gdata), len(code), len(strings))
        return (head + self.gdata + _struct.pack("<%di" % len(code), *code) + strings +
                _struct.pack("<i", len(self.ftypes)) + self.ftypes +
                _struct.pack("<%di" % len(self.fixups), *self.fixups) + self.tail)

    def rebuild(self, repl):
        """repl: {pool_index: new bytes}. Returns new serialized script with all string refs relocated."""
        old = self.pool()
        new_pool, starts_old, starts_new, a, b = [], [], [], 0, 0
        for i, s in enumerate(old):
            n = repl.get(i, s)
            starts_old.append(a); starts_new.append(b)
            new_pool.append(n)
            a += len(s) + 1; b += len(n) + 1
        import bisect
        code = list(self.code)
        for k, t in enumerate(self.ftypes):
            if t == 3:
                pos = self.fixups[k]
                off = code[pos]
                i = bisect.bisect_right(starts_old, off) - 1
                code[pos] = starts_new[i] + (off - starts_old[i])
        strings = b"".join(x + b"\0" for x in new_pool)
        return self.to_bytes(strings, code)

    def string_refs(self):
        """[(pool_index_or_offset...)]: resolved strings referenced from code, by code position"""
        return [(self.fixups[k], self.code[self.fixups[k]]) for k, t in enumerate(self.ftypes) if t == 3]


def _looks_text(b):
    if b.startswith(_NEWSCRIPT) or not any(65 <= c <= 90 or 97 <= c <= 122 or c > 127 for c in b):
        return False
    if PREFIX_RE.match(b.decode("latin-1")) or b" " in b:
        return True
    t = b.decode("latin-1")
    return t[:1].isupper() and "_" not in t and not any(c.isupper() for c in t[1:]) and len(t) > 3


