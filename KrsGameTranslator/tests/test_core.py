"""Headless tests (no GUI, no game files needed). Run: python tests/test_core.py"""
import os
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from gtt import (Project, ERR, check_entry, encode_file, decode_display,  # noqa: E402
                  _encrypt, _decrypt)

SAMPLE = os.path.join(ROOT, "examples", "Sample.tra")


def make_script(strings, refs):
    """Minimal compiled script: code[2*i+1] holds the offset of string refs[i] (FIXUP_STRING)."""
    pool = b"".join(s + b"\0" for s in strings)
    offs, o = [], 0
    for s in strings:
        offs.append(o); o += len(s) + 1
    code = []
    for r in refs:
        code += [6, offs[r], 0]
    fix = [3 * i + 1 for i in range(len(refs))]
    tail = struct.pack("<i", 0) + struct.pack("<i", 0) + struct.pack("<i", 0) + struct.pack("<I", 0xBEEFCAFE)
    return (b"SCOM" + struct.pack("<iiii", 90, 0, len(code), len(pool)) + struct.pack("<%di" % len(code), *code) + pool +
            struct.pack("<i", len(fix)) + bytes([3] * len(fix)) + struct.pack("<%di" % len(fix), *fix) + tail)


def test_text_tra(app):
    p = Project(app)
    _o, errs = p.open_files([SAMPLE]); assert not errs, errs
    assert len(p.rows) == 4
    assert p.docs[0].build_bytes(p.settings) == open(SAMPLE, "rb").read()
    uids = [e.uid for e in p.rows]
    p.copy_text(uids[:3])
    p.apply_plan(p.plan_paste("Salam\nNecəsən?\nSağ ol", [uids[0]], uids))
    assert p.rows[0].tr == "Salam" and p.rows[0].tr_prefix == "&1 "
    p.rows[3].src, p.rows[3].tr, p.rows[3].touched = "Open %s now", "Aç", True
    assert any(s == ERR for s, _c, _m in check_entry(p.rows[3], p.settings))
    out = p.export_all(os.path.join(app, "out"))[0][1]
    assert open(out, "rb").read().decode("utf-8").split("\r\n")[:2] == ["&1 Hello there!", "&1 Salam"]
    try:
        p.export_all(os.path.dirname(SAMPLE)); raise AssertionError
    except ValueError:
        pass
    assert p.undo() is not None and os.path.isdir(p.backup_now())
    assert decode_display("w￤re") == "wäre" and encode_file("ä", "ffxx") == "￤"


def test_dta(app):
    scr = make_script([b"cName_AnyClick", b"&1 Hello there!", b"&2 Second line, longer text.", b"Walk to"], [1, 2, 3, 1])
    path = os.path.join(app, "game.dta")
    blob = b"Adventure Creator Game File v25" + b"\x00" * 20 + scr + b"AFTER" * 7
    open(path, "wb").write(blob)
    p = Project(app); p.open_files([path]); d = p.docs[0]
    assert len(d.scripts) == 1 and d.build_bytes(p.settings) == blob
    texts = [e.src for e in p.rows]
    assert "Hello there!" in texts and "cName_AnyClick" not in texts
    e = [x for x in p.rows if x.src == "Hello there!"][0]
    e.tr, e.touched = "Salam, bu daha uzun mətndir", True
    out = p.export_all(os.path.join(app, "out"))[0][1]
    new = open(out, "rb").read()
    assert new.endswith(b"AFTER" * 7) and "Salam, bu daha uzun mətndir".encode() in new
    q = Project(tempfile.mkdtemp()); q.open_files([out])
    assert [x.src for x in q.rows] == ["Salam, bu daha uzun mətndir", "Second line, longer text.", "Walk to"]


def test_binary_tra(app):
    def enc(t): return _encrypt(t.encode("cp1252") + b"\0")
    pairs = [("&1 Hello", "&1 Hallo"), ("Walk to", "Gehe zu")]
    raws = [enc(x) for pr in pairs for x in pr]
    body = b"".join(struct.pack("<i", len(r)) + r for r in raws)
    hdr = struct.pack("<I", 0x1234) + struct.pack("<i", 4) + _encrypt(b"Gam\0")
    data = (b"AGSTranslation\0" + struct.pack("<ii", 2, len(hdr)) + hdr + struct.pack("<ii", 1, len(body)) + body +
            struct.pack("<i", 3) + b"\x00\x00\x00\x00")
    assert _decrypt(raws[0]) == b"&1 Hello\0"
    path = os.path.join(app, "German.tra"); open(path, "wb").write(data)
    p = Project(app); p.open_files([path])
    assert len(p.rows) == 2 and p.docs[0].build_bytes(p.settings) == data
    p.rows[1].tr, p.rows[1].touched = "Getə zu", True
    out = p.export_all(os.path.join(app, "out"))[0][1]
    q = Project(tempfile.mkdtemp()); q.open_files([out])
    assert q.rows[1].tr == "Getə zu" and q.rows[0].tr == "Hallo" and q.rows[0].tr_prefix == "&1 "


def main():
    for t in (test_text_tra, test_dta, test_binary_tra):
        t(tempfile.mkdtemp())
    print("ALL OK")


def test_renpy():
    import gtt as core, tempfile, os
    src = ('# TODO: Translation updated at 2021-08-30 23:57\r\n\r\n# game/script.rpy:153\r\ntranslate english start_20465d4d:\r\n\r\n'
           '    # n "Rus metni"\r\n    n "I walk to my room, [name]."\r\n\r\n'
           'translate english strings:\r\n    # game/script.rpy:15\r\n    old "Rus"\r\n    new "Totally not cool."\r\n')
    d = tempfile.mkdtemp(); p = os.path.join(d, "script.rpy"); open(p, "w", encoding="utf-8", newline="").write(src)
    doc = core.make_doc(p); S = core.Settings()
    assert type(doc).__name__ == "RenpyDoc" and len(doc.entries) == 2
    assert doc.build_bytes(S).decode().replace("translate azerbaijani ", "translate english ") == src
    doc.entries[0].tr = "Otağıma gedirəm, [name]."; doc.entries[1].tr = "Heç də yaxşı deyil."
    b = doc.build_bytes(S); doc.verify(b, S)
    assert "translate azerbaijani start_20465d4d:" in b.decode() and 'n "Otağıma gedirəm, [name]."' in b.decode()
    assert not core.check_entry(doc.entries[0], S)
    doc.entries[0].tr = 'bad "q"'
    assert any(x[1] == "QUOTE" for x in core.check_entry(doc.entries[0], S))
    print("renpy ok")


def test_bulk_clear():
    import gtt as core, tempfile, os
    src = ('translate english a_1:\r\n\r\n    # n "Rus"\r\n    n "One."\r\n\r\n'
           'translate english a_2:\r\n\r\n    # n "Rus2"\r\n    n "Two."\r\n')
    d = tempfile.mkdtemp(); p = os.path.join(d, "s.rpy"); open(p, "w", encoding="utf-8", newline="").write(src)
    pr = core.Project(tempfile.mkdtemp()); pr.open_files([p]); rows = pr.rows
    pr.apply_batch([(rows[0].uid, "Bir."), (rows[1].uid, "Iki.")])
    assert pr.clear_text([rows[0].uid]) == 1 and rows[0].tr == "" and not rows[0].touched
    out = tempfile.mkdtemp(); pr.export_all(out)
    t = open(os.path.join(out, "s.rpy"), encoding="utf-8", newline="").read()
    assert 'n "One."' in t and 'n "Iki."' in t          # cleared line keeps the original text
    pr.undo(); assert rows[0].tr == "Bir."
    assert pr.copy_source([rows[0].uid]) and rows[0].tr == "One."
    print("bulk clear ok")


def test_i18n():
    """Every _("...") key in the package has an Azerbaijani entry with the same {placeholders}."""
    import ast, glob, json, re
    from gtt import i18n
    pkg = os.path.join(ROOT, "src", "gtt")
    table = json.load(open(os.path.join(pkg, "locales", "az.json"), encoding="utf-8"))
    keys = set()
    for f in glob.glob(os.path.join(pkg, "**", "*.py"), recursive=True):
        for n in ast.walk(ast.parse(open(f, encoding="utf-8").read())):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_" and n.args and isinstance(n.args[0], ast.Constant):
                keys.add(n.args[0].value)
    missing = [k for k in keys if k not in table]
    assert not missing, missing
    for k, v in table.items():
        assert set(re.findall(r"\{(\w+)\}", k)) == set(re.findall(r"\{(\w+)\}", v)), k
    i18n.set_language("az"); assert i18n._("Save") == "Yadda saxla"
    i18n.set_language("en"); assert i18n._("Save") == "Save"
    assert i18n._("Unknown {x}", x=1) == "Unknown 1"
    print("i18n ok")


if __name__ == "__main__":
    main()
    test_renpy()
    test_bulk_clear()
    test_i18n()
