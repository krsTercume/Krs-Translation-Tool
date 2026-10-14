"""Ren'Py translation .rpy."""
import hashlib, json, os, re, shutil, struct, time
from collections import Counter
import re
from ..common import *  # noqa
from ..model import *  # noqa
from ..model import _bytes_to_text, _text_to_bytes, _make_entry  # noqa

RENPY_HEAD_RE = re.compile(r"^translate (\w+) (\w+):\s*$")
RENPY_LINE_RE = re.compile(r'^(\s*(?:[A-Za-z_]\w*\s*)?)"((?:[^"\\]|\\.)*)"(.*)$')
RENPY_NEW_RE = re.compile(r'^(\s*new\s+)"((?:[^"\\]|\\.)*)"(.*)$')
RENPY_TOKEN_RE = re.compile(r"\{[^{}]*\}|\[[^\[\]]*\]|%\([^)]*\)\w|%[sd]")


def _renpy_scan(lines):
    """-> list of (line_index, pre, text, post) for every translatable line of a Ren'Py translation file."""
    out, n, i = [], len(lines), 0
    while i < n:
        m = RENPY_HEAD_RE.match(lines[i])
        if not m:
            i += 1
            continue
        strings = m.group(2) == "strings"
        j = i + 1
        while j < n and not (lines[j].startswith("translate ") or lines[j].startswith("# game/")):
            s = lines[j]
            if strings:
                mm = RENPY_NEW_RE.match(s)
                if mm:
                    out.append((j, mm.group(1), mm.group(2), mm.group(3)))
            elif s.strip() and not s.lstrip().startswith("#"):
                mm = RENPY_LINE_RE.match(s)
                if mm:
                    out.append((j, mm.group(1), mm.group(2), mm.group(3)))
                break               # only the first statement of a block is the dialogue line
            j += 1
        i = j
    return out


class RenpyDoc:
    """Ren'Py translation file (game/tl/<language>/*.rpy): translate the English text, write a new language."""

    renpy = True
    empty_keeps_original = True

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        with open(path, "rb") as f:
            data = f.read()
        self.bom = data.startswith(b"\xef\xbb\xbf")
        if self.bom:
            data = data[3:]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"{self.name}: not UTF-8 ({e})")
        self.eol = "\r\n" if text.count("\r\n") >= text.count("\n") - text.count("\r\n") else "\n"
        self.lines = EOL_RE.split(text)
        if self.eol.join(self.lines) != text:
            raise ValueError(f"{self.name}: mixed line endings; refusing to edit")
        heads = [RENPY_HEAD_RE.match(l) for l in self.lines]
        langs = {m.group(1) for m in heads if m}
        if not langs:
            raise ValueError(f"{self.name}: no 'translate <language> ...' blocks (not a Ren'Py translation file)")
        self.langs = langs
        self.entries, self.tail = [], []
        for k, (li, pre, txt, post) in enumerate(_renpy_scan(self.lines)):
            self.entries.append(_make_entry(self, k, txt, txt, (li, pre, post),
                                            touched=any(ch in AZ_MARK for ch in txt)))

    def build_bytes(self, settings):
        lines = list(self.lines)
        lang = settings.renpy_lang.strip() or "azerbaijani"
        for i, l in enumerate(lines):
            if RENPY_HEAD_RE.match(l):
                lines[i] = "translate " + lang + l[l.index(" ", 10):]
        for e in self.entries:
            if e.changed and e.tr != e.orig_tr:
                li, pre, post = e.meta
                lines[li] = f'{pre}"{e.tr}"{post}'
        data = self.eol.join(lines).encode("utf-8")
        return (b"\xef\xbb\xbf" if self.bom else b"") + data

    def verify(self, newdata, settings):
        raw = newdata[3:] if newdata.startswith(b"\xef\xbb\xbf") else newdata
        lines = EOL_RE.split(raw.decode("utf-8"))
        if len(lines) != len(self.lines):
            raise RuntimeError("Export error: line count changed. Nothing was written.")
        lang = settings.renpy_lang.strip() or "azerbaijani"
        for l in lines:
            m = RENPY_HEAD_RE.match(l)
            if m and m.group(1) != lang:
                raise RuntimeError("Export error: language name not replaced. Nothing was written.")
        scan = _renpy_scan(lines)
        if len(scan) != len(self.entries):
            raise RuntimeError("Export error: number of text lines changed. Nothing was written.")
        for e, (li, pre, txt, post) in zip(self.entries, scan):
            want = e.tr if (e.changed and e.tr != e.orig_tr) else e.orig_tr
            if li != e.meta[0] or txt != want:
                raise RuntimeError(f"Export error: entry {e.number} does not match. Nothing was written.")


