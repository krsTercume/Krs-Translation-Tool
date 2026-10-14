"""Project: documents, undo/redo, paste planning, export."""
import hashlib, json, os, re, shutil, time
from collections import Counter
from .common import *  # noqa
from .i18n import _
from .model import *  # noqa
from .validation import check_entry, has_error  # noqa
from .formats import make_doc  # noqa
from .formats.text_tra import Doc  # noqa
from .formats.ags_dta import DtaDoc, CrmDoc  # noqa
from .formats.renpy import RenpyDoc, RENPY_TOKEN_RE  # noqa
from .formats.ags_bintra import BinTraDoc  # noqa

# ---------------------------------------------------------------- project / controller

class Project:

    def __init__(self, app_dir):
        self.app_dir = app_dir
        self.settings = Settings()
        self.docs, self.rows, self.by_uid = [], [], {}
        self._uid = 0
        self.undo_stack, self.redo_stack = [], []
        self.last_copy = None
        self.dirty = False

    # ---- open / backup / project file
    def backup_dir(self):
        d = os.path.join(self.app_dir, "backups")
        os.makedirs(d, exist_ok=True)
        return d

    def open_files(self, paths):
        opened, errors = [], []
        for p in paths:
            p = os.path.abspath(p)
            if any(d.path == p for d in self.docs):
                continue
            try:
                doc = make_doc(p)
            except Exception as ex:
                errors.append(f"{os.path.basename(p)}: {ex}")
                continue
            self._make_backup(p)
            self.docs.append(doc)
            for e in doc.entries:
                e.uid = self._uid
                self._uid += 1
                self.rows.append(e)
                self.by_uid[e.uid] = e
            self._load_saved(doc)
            opened.append(doc)
        return opened, errors

    def _make_backup(self, path):
        with open(path, "rb") as f:
            h = hashlib.sha1(f.read()).hexdigest()[:8]
        dst = os.path.join(self.backup_dir(), f"{os.path.basename(path)}.{h}.bak")
        if not os.path.exists(dst):
            shutil.copy2(path, dst)
        return dst

    def close_all(self):
        self.docs, self.rows, self.by_uid = [], [], {}
        self.undo_stack.clear(); self.redo_stack.clear()
        self.last_copy = None; self.dirty = False

    def backup_now(self):
        self.save_all()
        d = os.path.join(self.backup_dir(), time.strftime("manual_%Y%m%d_%H%M%S"))
        os.makedirs(d, exist_ok=True)
        for doc in self.docs:
            shutil.copy2(doc.path, os.path.join(d, doc.name))
            shutil.copy2(self._proj_path(doc), os.path.join(d, doc.name + ".project.json"))
        return d

    def _proj_path(self, doc):
        h = hashlib.sha1(doc.path.encode("utf-8")).hexdigest()[:8]
        d = os.path.join(self.app_dir, "projects")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"{doc.name}.{h}.json")

    def save_all(self):
        for doc in self.docs:
            items = []
            for e in doc.entries:
                if e.changed or e.touched != e.orig_touched:
                    items.append({"i": e.idx, "os": e.orig_src, "src": e.src, "tr": e.tr,
                                  "trp": e.tr_prefix, "t": e.touched})
            data = {"version": 1, "path": doc.path, "settings": self.settings.to_dict(), "items": items}
            tmp = self._proj_path(doc) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self._proj_path(doc))
        self.dirty = False

    def _load_saved(self, doc):
        p = self._proj_path(doc)
        if not os.path.isfile(p):
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        self.settings.load(data.get("settings"))
        by_i = {e.idx: e for e in doc.entries}
        by_src = {}
        for e in doc.entries:
            by_src.setdefault(e.orig_src, []).append(e)
        used = set()
        for it in data.get("items", []):
            e = by_i.get(it.get("i"))
            if e is None or e.orig_src != it.get("os"):
                c = [x for x in by_src.get(it.get("os"), []) if x.idx not in used]
                e = c[0] if c else None
            if e is None:
                continue
            used.add(e.idx)
            e.src, e.tr = it.get("src", e.src), it.get("tr", e.tr)
            e.tr_prefix, e.touched = it.get("trp", e.tr_prefix), bool(it.get("t", e.touched))

    # ---- filter
    def filter(self, query="", only_untranslated=False, only_voiced=False, only_issues=False, doc_name=None):
        toks = query.lower().split()
        out = []
        for e in self.rows:
            if doc_name and e.doc.name != doc_name:
                continue
            if only_untranslated and e.touched:
                continue
            if only_voiced and not e.prefix:
                continue
            if only_issues and not e.issues:
                continue
            if toks:
                hay = f"{e.prefix} {e.src} {e.tr}".lower()
                if not all(t in hay for t in toks):
                    continue
            out.append(e.uid)
        return out

    # ---- editing + undo (record = {uid: (src, tr, trp, touched)})
    @staticmethod
    def _snap(e):
        return (e.src, e.tr, e.tr_prefix, e.touched)

    @staticmethod
    def _restore(e, s):
        e.src, e.tr, e.tr_prefix, e.touched = s

    def _push(self, rec):
        if rec:
            self.undo_stack.append(rec)
            self.redo_stack.clear()
            if len(self.undo_stack) > 300:
                del self.undo_stack[0]
            self.dirty = True

    def set_translation(self, uid, text):
        return self.apply_batch([(uid, text)])

    def set_source(self, uid, text):
        e = self.by_uid[uid]
        if e.src == text:
            return False
        self._push({uid: self._snap(e)})
        e.src = text
        return True

    def apply_batch(self, pairs):
        rec = {}
        for uid, text in pairs:
            e = self.by_uid[uid]
            pre, body = split_prefix(text) if PREFIX_RE.match(text) else (e.tr_prefix, text)
            if (e.tr, e.tr_prefix, e.touched) != (body, pre, True):
                rec.setdefault(uid, self._snap(e))
                e.tr, e.tr_prefix, e.touched = body, pre, True
        self._push(rec)
        return len(rec)

    def clear_text(self, uids):
        """Bulk delete: empty the translation text (a voice prefix such as '&3001 ' is kept)."""
        rec = {}
        for uid in uids:
            e = self.by_uid[uid]
            if e.tr != "" or e.touched:
                rec[uid] = self._snap(e)
                e.tr, e.touched = "", False
        self._push(rec)
        return len(rec)

    def copy_source(self, uids):
        """Bulk: translation := source text (prefix kept)."""
        return self.apply_batch([(u, self.by_uid[u].src) for u in uids])

    def clear_translations(self, uids):
        """Bulk delete: put the translation (and Source, if edited) back to the state it had when the file was opened."""
        rec = {}
        for uid in uids:
            e = self.by_uid[uid]
            old = (e.orig_src, e.orig_tr, e.orig_tr_prefix, e.orig_touched)
            if self._snap(e) != old:
                rec[uid] = self._snap(e)
                self._restore(e, old)
        self._push(rec)
        return len(rec)

    def mark(self, uids, done):
        rec = {}
        for uid in uids:
            e = self.by_uid[uid]
            if e.touched != done:
                rec[uid] = self._snap(e)
                e.touched = done
        self._push(rec)
        return len(rec)

    def _swap(self, src_stack, dst_stack):
        if not src_stack:
            return None
        rec = src_stack.pop()
        cur = {}
        for uid, s in rec.items():
            e = self.by_uid[uid]
            cur[uid] = self._snap(e)
            self._restore(e, s)
        dst_stack.append(cur)
        self.dirty = True
        return list(rec)

    def undo(self):
        return self._swap(self.undo_stack, self.redo_stack)

    def redo(self):
        return self._swap(self.redo_stack, self.undo_stack)

    # ---- smart select / copy / paste
    def next_untranslated(self, displayed, n, start_uid=None):
        start = displayed.index(start_uid) if start_uid in displayed else 0
        picked = []
        for uid in displayed[start:]:
            if not self.by_uid[uid].touched:
                picked.append(uid)
                if len(picked) >= n:
                    break
        return picked

    def copy_text(self, uids):
        lines = [self.by_uid[u].src for u in uids]
        if self.settings.numbered:
            lines = [f"{i}. {t}" for i, t in enumerate(lines, 1)]
        self.last_copy = {"uids": list(uids), "numbered": self.settings.numbered}
        return "\n".join(lines)

    def plan_paste(self, text, selected, displayed):
        raw = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        while raw and not raw[-1].strip():
            raw.pop()
        plan = {"pairs": [], "warnings": [], "overwrite": 0, "mode": "sequence", "count_mismatch": False}
        if not raw:
            plan["warnings"].append("The clipboard is empty.")
            return plan
        lc, first = self.last_copy, (selected[0] if selected else None)
        if lc and (first is None or first == lc["uids"][0]):
            targets = list(lc["uids"])
        elif first is not None and first in displayed:
            targets = displayed[displayed.index(first):]
        else:
            plan["warnings"].append("Select a row in the table first.")
            return plan
        numbered = sum(1 for l in raw if NUM_PREFIX_RE.match(l)) >= max(2, int(len(raw) * 0.8))
        if numbered:
            plan["mode"] = "numbered"
            items, order, cur = {}, [], None
            for l in raw:
                m = NUM_PREFIX_RE.match(l)
                if m:
                    cur = int(m.group(1)); items[cur] = m.group(2).strip(); order.append(cur)
                elif l.strip() and cur is not None:
                    items[cur] = (items[cur] + " " + l.strip()).strip()
            for n in order:
                if 1 <= n <= len(targets):
                    plan["pairs"].append((targets[n - 1], items[n]))
                else:
                    plan["warnings"].append(f"Number {n} is outside the target range, skipped.")
            if lc and lc["numbered"]:
                miss = [n for n in range(1, len(lc["uids"]) + 1) if n not in items]
                if miss:
                    plan["warnings"].append("Missing numbers: " + ", ".join(map(str, miss[:20])) + (" ..." if len(miss) > 20 else ""))
                    plan["count_mismatch"] = True
        else:
            if lc and lc["uids"] == targets[:len(lc["uids"])] and len(raw) != len(lc["uids"]):
                plan["count_mismatch"] = True
                plan["warnings"].append(f"Copied: {len(lc['uids'])} lines, pasted: {len(raw)} lines. "
                                        "The translator may have merged/split lines - lines may be shifted.")
            if len(raw) > len(targets):
                plan["warnings"].append(f"{len(raw) - len(targets)} extra lines run past the end of the table and will not be written.")
            for uid, line in zip(targets, raw):
                if line.strip():
                    plan["pairs"].append((uid, line.strip()))
        plan["overwrite"] = sum(1 for u, _t in plan["pairs"] if self.by_uid[u].touched)
        return plan

    def apply_plan(self, plan):
        return self.apply_batch(plan["pairs"])

    # ---- validate
    def validate(self):
        res, stats = [], Counter()
        for e in self.rows:
            e.issues = check_entry(e, self.settings) if e.touched else []
            if not e.touched:
                stats["UNTRANSLATED"] += 1
                continue
            for s, c, m in e.issues:
                res.append((e, s, c, m)); stats[c] += 1
        stats["TOTAL"] = len(self.rows)
        stats["DONE"] = sum(1 for e in self.rows if e.touched)
        return res, stats

    # ---- export
    def export_all(self, out_dir):
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        results = []
        for doc in self.docs:
            if os.path.abspath(os.path.dirname(doc.path)) == out_dir:
                raise ValueError(_("The output folder cannot be the original file's folder. Choose another folder."))
            data = doc.build_bytes(self.settings)
            if hasattr(doc, "verify"):
                doc.verify(data, self.settings)
            else:
                self._verify(doc, data)
            dst = os.path.join(out_dir, doc.name)
            with open(dst + ".tmp", "wb") as f:
                f.write(data)
            os.replace(dst + ".tmp", dst)
            results.append((doc, dst))
        return results

    @staticmethod
    def _verify(doc, data):
        raw = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
        lines = EOL_RE.split(raw.decode("utf-8"))
        want = len(doc.entries) * 2 + len(doc.tail)
        if len(lines) != want:
            raise RuntimeError(_("Export error: line count changed ({a} vs {b}). Nothing was written.", a=len(lines), b=want))
        for e in doc.entries:
            pre = split_prefix(decode_display(lines[e.idx * 2]))[0]
            if pre != e.prefix:
                raise RuntimeError(_("Export error: voice prefix of entry {n} changed. Nothing was written.", n=e.number))

