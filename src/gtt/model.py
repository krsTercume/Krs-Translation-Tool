"""Settings and Entry: the data every format reads into."""
import hashlib, json, os, re, shutil, struct, time
from collections import Counter
from .common import *  # noqa

class Settings:
    def __init__(self):
        self.numbered = False       # numbered copy ("1. text")
        self.chunk = 100            # "select next N"
        self.allow_src_edit = False
        self.latin_style = "unicode"   # or 'ffxx'
        self.charmap = ""           # e.g. "ə>ä Ə>Ä ı>i İ>I ğ>g Ğ>G ş>s Ş>S"
        self.out_encoding = "utf-8"  # text for .dta / compiled .tra: "utf-8" or "cp1252"
        self.renpy_lang = "azerbaijani"  # Ren'Py: language name written after "translate"
        self.type_w = True          # typing w / W inserts the schwa letters

    def to_dict(self):
        return dict(self.__dict__)

    def load(self, d):
        for k, v in (d or {}).items():
            if k in self.__dict__:
                setattr(self, k, v)


# ---------------------------------------------------------------- entry / document

class Entry:
    __slots__ = ("uid", "doc", "idx", "prefix", "src", "tr", "tr_prefix", "touched",
                 "raw_src", "raw_tr", "orig_src", "orig_tr", "orig_tr_prefix", "orig_touched",
                 "issues", "meta")

    @property
    def number(self):
        return self.idx + 1

    @property
    def changed(self):
        # formats where an empty translation means "keep the original text" (.dta, .crm, Ren'Py)
        if getattr(self.doc, "empty_keeps_original", False) and not self.tr.strip():
            return self.src != self.orig_src
        return (self.src != self.orig_src or self.tr != self.orig_tr
                or self.tr_prefix != self.orig_tr_prefix)



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


def _make_entry(doc, idx, src_text, tr_text, meta, touched=False):
    e = Entry()
    e.doc, e.idx, e.meta = doc, idx, meta
    e.raw_src = e.raw_tr = None
    e.prefix, e.src = split_prefix(src_text)
    e.tr_prefix, e.tr = split_prefix(tr_text)
    e.orig_src, e.orig_tr, e.orig_tr_prefix = e.src, e.tr, e.tr_prefix
    e.touched = e.orig_touched = touched
    e.issues = []
    return e


