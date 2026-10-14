"""Interface translations. English text is the key; locales/<code>.json maps it to another language.
A missing key falls back to the English text, so the UI never breaks. No GUI imports here."""
import json
import os

LOCALES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
LANGUAGES = {"az": "Azərbaycan", "en": "English"}
_table, _lang = {}, "en"


def set_language(code):
    global _table, _lang
    _lang = code if code in LANGUAGES else "en"
    _table = {}
    try:
        with open(os.path.join(LOCALES, _lang + ".json"), encoding="utf-8") as f:
            _table = json.load(f)
    except (OSError, ValueError):
        pass


def current():
    return _lang


def _(text, **kw):
    s = _table.get(text, text)
    if kw:
        try:
            return s.format(**kw)
        except (KeyError, IndexError, ValueError):
            return text.format(**kw)
    return s


def load_config(app_dir):
    try:
        with open(os.path.join(app_dir, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(app_dir, cfg):
    try:
        with open(os.path.join(app_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    except OSError:
        pass
