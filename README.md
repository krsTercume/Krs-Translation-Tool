# Krs Translation Editor

A fan-made, dependency-free desktop tool (Python + Tkinter) for translating game text in bulk. Not affiliated with any game developer or engine.
It opens three kinds of files:
- plain-text `.tra` (alternating *source line / translation line*),
- **compiled binary `.tra`** (`AGSTranslation` header, encrypted pairs),
- compiled game data **`.dta`** (e.g. `game28.dta`): the dialogue / text strings inside the compiled scripts are
  replaced and every code reference is relocated, so translations may have a different length.
Bulk workflow with smart copy/paste; Source and Translation columns can both be edited.

> A tool for fan-made translations. Not affiliated with any game developer or publisher.
> Do not commit or redistribute game text; `.tra` files are git-ignored (only `examples/Sample.tra`, invented, is included).

## Features
- Reads/writes the plain-text `.tra`: untouched lines are written **byte-for-byte**, CRLF/BOM kept.
- Voice prefixes such as `&3001 ` are kept apart from the text, so a translator never sees or breaks them.
- `%s`-style placeholders, `<..>` / `@..@` tokens and `[` line breaks are checked by **Validate**.
- Smart bulk workflow: *Select next N + copy* -> paste into any translator -> copy result -> *Paste*
  (line-count mismatch warning, optional numbered mode, undo restores a whole paste).
- Rubber-band mouse selection, filters (not done / voiced / problems), multiple files, autosave, backup, themes.
- Optional *char replace on export* (e.g. `ə>ä ı>i`) for characters your game font cannot draw.
- Handles the quirk where some characters are stored as `U+FFxx` (shown as normal letters).
- Never modifies the original: backup on open, export only to a *different* folder.

## Install & run
Python 3.8+ with Tkinter. Windows: double-click `run.bat`; Linux/macOS: `./run.sh`. No `pip install`.

## Workflow
1. **Open .tra**.
2. Set *Select N*, press **Select next N + copy**, translate the copied English text elsewhere.
3. Copy the result, press **Paste (Ctrl+V)**. Ctrl+Z undoes a whole paste.
4. **Validate**, then **Export** to a different folder and copy the file into the game.
Lines count as *done* once you paste/edit them (or mark them with *Mark done*).

## Notes
- The engine matches entries by the **source** text. Editing the Source column is possible, but the
  game will then no longer match that entry (Validate warns).
- Whether letters like `ə`, `ğ`, `ş` appear in game depends on the game's font.
- Test one edited line in the game first (especially `ä ö ü` with the *Latin-1 chars* option).

## Structure
```
src/main.py            entry point (language choice on first launch)
src/gtt/               core package, no GUI: model, project, validation, i18n
src/gtt/formats/       one module per format (.tra, .dta/.crm, binary .tra, Ren'Py)
src/gtt/gui/           Tkinter window and Settings dialog
src/gtt/locales/       interface translations (az.json; add <code>.json to add a language)
tests/                 headless tests + GUI smoke test (mocked Tk)
examples/              invented sample
```
Run tests: `python tests/test_core.py` and `python tests/gui_smoke.py`

Interface language (Azərbaycan / English) is asked on first launch and can be changed in Settings.

## License
MIT

## .dta notes
- Only string literals inside the compiled scripts are edited; everything else is copied unchanged. The file is parsed,
  rebuilt and re-read before it is written (every string reference is checked). It is tested byte-exact on a real game file
  (no changes -> identical output), but the engine itself was not run here: **test in the game and keep a backup**.
- Choose the *Text encoding*: `utf-8` for characters like ə (needs an engine/font that supports it) or `cp1252`
  (use *Char replace*, e.g. `ə>ä`).


## Ren'Py translation files (.rpy)

Open the files from a game's `game/tl/<language>/` folder (for example `tl/english/script.rpy`).
The tool shows the existing text (usually English), you translate it, and **Export** writes the same files
with `translate <your language> ...` (set the name in "Ren'Py language", default `azerbaijani`).
Put the exported files into a NEW folder `game/tl/<your language>/`; the original files stay untouched.

- Keep `[variables]`, `{tags}` and `%s`-style placeholders; a `"` inside a text must be written `\"`.
- Validate warns about lost placeholders and unescaped quotes.
- Whether a letter such as the Azerbaijani schwa is shown depends on the game's font.

## Selecting, clearing and settings

- **Delete** (or the **Clear (Del)** button) empties the translation of every selected line; **Ctrl+Z** undoes it.
  For `.dta`, `.crm` and Ren'Py files an empty translation keeps the original text in the exported file.
- **Right-click** a selection for: Clear translation, Revert to original, Copy source -> translation, Mark done / not done, Copy, Paste.
- **Settings...** collects every option in one dialog: typing shortcuts, source editing, numbered copy, output encoding,
  character replacement and the Ren'Py language name.
