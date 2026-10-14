"""Shared constants and text helpers (no GUI)."""
import hashlib, json, os, re, shutil, struct, time
from collections import Counter
import re


PREFIX_RE = re.compile(r"^(&\d+ )")
TOKEN_RE = re.compile(r"%[A-Za-z0-9]|@[A-Z]+@|<[^<>]+>|\{[^{}]*\}")
EOL_RE = re.compile(r"\r\n|\n")
NUM_PREFIX_RE = re.compile(r"^\s*(\d{1,6})\s*[.)\]:\-]\s?(.*)$")
AZ_MARK = set("əƏğĞıİşŞ")

ERR, WARN = "ERROR", "WARNING"


# ---------------------------------------------------------------- encoding helpers

def decode_display(s):
    """U+FF80..U+FFFF -> chr(0x80..0xFF) so text is readable."""
    return "".join(chr(ord(c) - 0xFF00) if 0xFF80 <= ord(c) <= 0xFFFF else c for c in s)


def encode_file(s, style):
    """style 'unicode': keep as typed; 'ffxx': chars 0x80..0xFF -> U+FFxx (matches original German)."""
    if style == "ffxx":
        return "".join(chr(0xFF00 + ord(c)) if 0x80 <= ord(c) <= 0xFF else c for c in s)
    return s


def split_prefix(s):
    m = PREFIX_RE.match(s)
    return (m.group(1), s[m.end():]) if m else ("", s)


def apply_charmap(s, charmap):
    for a, b in charmap.items():
        s = s.replace(a, b)
    return s


def parse_charmap(text):
    """'ə>ä Ə>Ä ğ>g' -> {'ə': 'ä', ...}"""
    out = {}
    for tok in re.split(r"[\s,;]+", text.strip()):
        if ">" in tok:
            a, b = tok.split(">", 1)
            if a:
                out[a] = b
    return out


# ---------------------------------------------------------------- settings

