"""Check which Azerbaijani letters a .ttf font really contains (reads the font's character table; no Qt fallback).
Usage: python font_check.py agsfnt7.ttf [more.ttf ...]"""
import struct
import sys

LETTERS = "əƏıİğĞşŞçÇöÖüÜ"


def cmap_chars(data):
    n = struct.unpack(">H", data[4:6])[0]
    off = next((struct.unpack(">I", data[12 + 16 * i + 8:12 + 16 * i + 12])[0]
                for i in range(n) if data[12 + 16 * i:16 + 16 * i] == b"cmap"), None)
    if off is None:
        return set()
    chars = set()
    for i in range(struct.unpack(">H", data[off + 2:off + 4])[0]):
        pid, eid, so = struct.unpack(">HHI", data[off + 4 + 8 * i:off + 12 + 8 * i])
        t = off + so
        fmt = struct.unpack(">H", data[t:t + 2])[0]
        if fmt == 4:
            sc = struct.unpack(">H", data[t + 6:t + 8])[0] // 2
            ends = struct.unpack(">%dH" % sc, data[t + 14:t + 14 + 2 * sc])
            starts = struct.unpack(">%dH" % sc, data[t + 16 + 2 * sc:t + 16 + 4 * sc])
            for s, e in zip(starts, ends):
                chars.update(range(s, e + 1))
        elif fmt == 12:
            ng = struct.unpack(">I", data[t + 12:t + 16])[0]
            for g in range(ng):
                s, e, _ = struct.unpack(">III", data[t + 16 + 12 * g:t + 28 + 12 * g])
                chars.update(range(s, e + 1))
    return chars


for p in sys.argv[1:]:
    ch = cmap_chars(open(p, "rb").read())
    miss = [c for c in LETTERS if ord(c) not in ch]
    print("%s: %s" % (p, "all 14 letters present" if not miss else "MISSING " + " ".join(miss)))
