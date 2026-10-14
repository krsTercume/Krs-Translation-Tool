
# Krs Game Translator

A free, open-source desktop tool for translating game localization files. It brings multiple file formats into one interface and provides a practical workflow for translating text with external translation tools.

The project focuses on safe file handling, bulk translation, text validation, and Azerbaijani language support.

> A tool for fan-made translations. Not affiliated with any game developer or publisher.

## Supported Formats

### Adventure Game Studio (AGS)

- **Plain-text `.tra`** — Reads and writes alternating source and translation lines while preserving untouched lines, line endings, and byte-order marks where supported.
- **Compiled binary `.tra`** — Supports AGS translation files using the `AGSTranslation` format.
- **Compiled game data `.dta`** — Designed to edit translatable string literals in compiled AGS game data while preserving other data and updating string references where necessary.
- **`.crm`** — Support for compatible AGS game data files.

### Ren'Py

- **`.rpy`** — Works with Ren'Py script and translation files, allowing source text to be translated and exported into a separate language directory.
- Preserves translation structure, variables, tags, and supported placeholders.
- Supports configurable translation language names.

**Compatibility note:** Support can vary depending on the game, file version, encoding, and script structure. Test exported files with the target game before distributing a patch.

## Features

### Bulk Translation Workflow

- Select the next N entries and copy them in one operation.
- Paste translated text from an external translation tool.
- Warns when the number of translated lines does not match the selection.
- Optional numbered copy mode.
- Undo an entire paste operation with a single `Ctrl+Z`.
- Edit source and translation text directly.

### Text Validation

- Detects missing or modified placeholders.
- Checks supported voice prefixes and special text markers.
- Detects line-break inconsistencies.
- Warns about potentially unsafe quotes in Ren'Py text.
- Helps identify encoding and character compatibility problems.

### Safe File Handling

- Keeps the original files unchanged.
- Creates backups when opening files.
- Exports translated files to a separate output directory.
- Re-reads and validates generated output before writing it.
- Aborts export when validation detects critical inconsistencies.

### Azerbaijani Language Support

- Azerbaijani and English interface options.
- Additional character input buttons for letters such as `ə`, `ğ`, `ı`, `ö`, `ş`, `ü`, and `ç`.
- Character replacement options for games whose fonts do not support Azerbaijani characters.
- Configurable output encoding where supported.

### Additional Features

- Multiple-file workflow.
- Filters for untranslated entries, voiced entries, and potential problems.
- Autosave and backup options.
- Themes and configurable settings.
- Source editing and translation progress tracking.

## Installation

Requirements:

- Python 3.8 or newer, depending on the selected runtime and supported dependencies.
- Tkinter for the desktop interface.

On Windows, run:

```bat
run.bat
```

On Linux or macOS, run:

```bash
./run.sh
```

The project is designed to run without installing additional packages through `pip`, provided the required Python components are available.

## Basic Workflow

1. Open a supported translation or game data file.
2. Choose the number of entries to translate.
3. Select **Select next N + copy**.
4. Translate the copied text using your preferred external translation tool.
5. Copy the translated result and use **Paste** in the application.
6. Review the translated entries and run **Validate**.
7. Export to a different folder.
8. Test the exported files in the target game.

Use `Ctrl+Z` to undo supported editing operations. Always keep the original game files backed up.

## Important Notes

- Preserve placeholders, variables, voice prefixes, control tags, and special formatting.
- Editing source text can prevent the game from matching an entry to its original string.
- Azerbaijani characters may require a compatible game font and encoding.
- Some legacy game engines have restrictions on text length, encoding, or supported characters.
- Export validation cannot guarantee that every game will load the translated files correctly.

## Project Structure

```text
src/
  main.py
  gtt/
    formats/
    gui/
    locales/

tests/
examples/
README.md
LICENSE
```

The exact structure may vary between releases.

## Testing

Run the available tests with:

```bash
python tests/test_core.py
python tests/gui_smoke.py
```

Test coverage and results depend on the current version of the project.

## Interface Language

The interface supports Azerbaijani and English. The language can be selected on first launch and changed in Settings.

## License

This project is released under the MIT License.

## Disclaimer

Kurosawa Translator is an independent fan-localization utility. It does not include commercial game assets or game scripts. Users are responsible for ensuring that their use and distribution of translated files complies with applicable licenses and laws.
