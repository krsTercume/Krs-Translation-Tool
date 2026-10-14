"""Entry checks (placeholders, voice prefix, encoding...)."""
import hashlib, json, os, re, shutil, struct, time
from collections import Counter
import re
from collections import Counter
from .common import *  # noqa
from .i18n import _
from .formats.renpy import RENPY_TOKEN_RE  # noqa

def check_entry(e, settings):
    out = []
    if not e.tr.strip():
        keep = getattr(e.doc, "empty_keeps_original", False)
        return [(WARN, "EMPTY", _("Empty translation (the original text is kept)") if keep
                 else _("Empty translation (the game will show the source text)"))]
    if e.prefix and e.tr_prefix != e.prefix:
        out.append((WARN, "VOICE", _("Voice prefix differs: source '{a}', translation '{b}'", a=e.prefix.strip(), b=e.tr_prefix.strip() or _("none"))))
    ren = getattr(e.doc, "renpy", False)
    if ren:
        if re.search(r'(?<!\\)"', e.tr) or re.search(r'(?<!\\)(\\\\)*\\$', e.tr):
            out.append((ERR, "QUOTE", _('Unescaped " or trailing backslash - write \\" for a quote')))
    rx = RENPY_TOKEN_RE if ren else TOKEN_RE
    a, b = Counter(rx.findall(e.src)), Counter(rx.findall(e.tr))
    if a != b:
        lost, added = list((a - b).elements()), list((b - a).elements())
        out.append((ERR, "TOKEN", _("Placeholder mismatch") + (_("; lost: {x}", x=lost) if lost else "") + (_("; added: {x}", x=added) if added else "")))
    if not ren and e.src.count("[") != e.tr.count("["):
        out.append((WARN, "BREAKS", _("Line-break '[' count differs ({a} vs {b})", a=e.src.count("["), b=e.tr.count("["))))
    if len(e.tr) > max(60, len(e.src) * 2):
        out.append((WARN, "LONG", _("Translation is much longer ({a} vs {b} chars)", a=len(e.tr), b=len(e.src))))
    if getattr(settings, "out_encoding", "utf-8") == "cp1252":
        try:
            apply_charmap(e.tr, parse_charmap(settings.charmap)).encode("cp1252")
        except UnicodeEncodeError as ex:
            out.append((ERR, "ENC", _("Character not available in cp1252: {c} (use 'Char replace' or UTF-8)", c=repr(ex.object[ex.start:ex.end]))))
    if e.src != e.orig_src:
        out.append((WARN, "SRC", _("Source text was edited - the game will no longer match this entry")))
    return out


def has_error(issues):
    return any(s == ERR for s, _c, _m in issues)


