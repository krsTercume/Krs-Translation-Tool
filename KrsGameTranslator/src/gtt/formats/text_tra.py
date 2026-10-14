"""Plain-text AGS .tra."""
import hashlib, json, os, re, shutil, struct, time
from collections import Counter
import re
from ..common import *  # noqa
from ..model import *  # noqa
from ..model import _bytes_to_text, _text_to_bytes, _make_entry  # noqa

class Doc:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.entries = []
        self.tail = []
        self.bom = False
        self.eol = "\r\n"
        self._load()

    def _load(self):
        with open(self.path, "rb") as f:
            data = f.read()
        self.bom = data.startswith(b"\xef\xbb\xbf")
        if self.bom:
            data = data[3:]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"{self.name}: not UTF-8 ({e}). This tool expects a UTF-8 text .tra file.")
        if "\x00" in text[:200]:
            raise ValueError(f"{self.name}: looks like a binary .tra, not the plain-text format.")
        self.eol = "\r\n" if text.count("\r\n") >= text.count("\n") - text.count("\r\n") else "\n"
        lines = EOL_RE.split(text)
        n = len(lines) // 2 * 2
        self.tail = lines[n:]
        for i in range(0, n, 2):
            e = Entry()
            e.doc, e.idx = self, i // 2
            e.raw_src, e.raw_tr = lines[i], lines[i + 1]
            e.prefix, e.src = split_prefix(decode_display(lines[i]))
            e.tr_prefix, e.tr = split_prefix(decode_display(lines[i + 1]))
            e.orig_src, e.orig_tr, e.orig_tr_prefix = e.src, e.tr, e.tr_prefix
            e.touched = e.orig_touched = any(c in AZ_MARK for c in e.tr)
            e.issues = []
            self.entries.append(e)

    def build_bytes(self, settings):
        cm = parse_charmap(settings.charmap)
        out = []
        for e in self.entries:
            rewrite = e.changed or (cm and any(c in e.tr for c in cm))
            if rewrite:
                src = encode_file(e.prefix + e.src, settings.latin_style)
                tr = encode_file(apply_charmap(e.tr_prefix + e.tr, cm), settings.latin_style)
                if not e.changed:       # only charmap touched translation: keep source raw
                    src = e.raw_src
                out += [src, tr]
            else:
                out += [e.raw_src, e.raw_tr]
        out += self.tail
        data = self.eol.join(out).encode("utf-8")
        return (b"\xef\xbb\xbf" if self.bom else b"") + data


