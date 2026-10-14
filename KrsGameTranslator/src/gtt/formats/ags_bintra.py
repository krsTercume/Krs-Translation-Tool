"""Compiled binary AGS .tra."""
import struct as _struct
import hashlib, json, os, re, shutil, struct, time
from collections import Counter
import re
from ..common import *  # noqa
from ..model import *  # noqa
from ..model import _bytes_to_text, _text_to_bytes, _make_entry  # noqa
from .ags_script import *  # noqa
from .ags_script import _KEY, _NEWSCRIPT, _decrypt, _encrypt, _looks_text  # noqa

class BinTraDoc:
    """Compiled AGS translation (.tra, binary): encrypted source/translation pairs."""

    @staticmethod
    def _parse(d, name="file"):
        if not d.startswith(b"AGSTranslation\0"):
            raise ValueError(f"{name}: not a compiled .tra")
        p = 15
        _ver, hl = _struct.unpack_from("<ii", d, p)
        head = d[15:p + 8 + hl]; p += 8 + hl
        btype, blen = _struct.unpack_from("<ii", d, p); p += 8
        if btype != 1:
            raise ValueError(f"{name}: unexpected block type {btype}")
        end, raws = p + blen, []
        while p < end:
            n, = _struct.unpack_from("<i", d, p); p += 4
            raws.append(d[p:p + n]); p += n
        if p != end or len(raws) % 2:
            raise ValueError(f"{name}: malformed translation block")
        return head, btype, raws, d[end:]

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        with open(path, "rb") as f:
            d = f.read()
        self.head, self.btype, self.raws, self.footer = self._parse(d, self.name)
        self.entries, self.tail = [], []
        for i in range(0, len(self.raws), 2):
            s, t = (_bytes_to_text(_decrypt(r).rstrip(b"\0")) for r in self.raws[i:i + 2])
            self.entries.append(_make_entry(self, i // 2, s, t, i))

    def _pack(self, raws):
        body = b"".join(_struct.pack("<i", len(r)) + r for r in raws)
        return b"AGSTranslation\0" + self.head + _struct.pack("<ii", self.btype, len(body)) + body + self.footer

    def _new_raws(self, settings):
        raws = list(self.raws)
        for e in self.entries:
            if e.changed:
                i = e.meta
                if e.src != e.orig_src:
                    raws[i] = _encrypt(_text_to_bytes(e.prefix + e.src, settings) + b"\0")
                raws[i + 1] = _encrypt(_text_to_bytes(e.tr_prefix + e.tr, settings) + b"\0")
        return raws

    def build_bytes(self, settings):
        return self._pack(self._new_raws(settings))

    def verify(self, newdata, settings):
        head, btype, raws, footer = self._parse(newdata, "export")
        want = self._new_raws(settings)
        if head != self.head or footer != self.footer or raws != want:
            raise RuntimeError("Export error: re-read file differs from what was intended. Nothing was written.")


