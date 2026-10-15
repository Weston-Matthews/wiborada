# Wiborada

Personal library manager with shelves, tags, digital ebooks, ISBN lookup, and AI recommendations.

## Features

See [FEATURES.md](FEATURES.md) for the complete inventory of preserved functionality.

## Fresh install (venv)

```bash
python -m venv .venv
source .venv/bin/activate          # or .venv\Scripts\activate on Windows
pip install -r requirements.txt    # installs optional deps + pytest
# or for minimal: just make sure Tkinter is available, then:
python main.py
```

Core features need only the standard library + Tkinter (usually bundled with Python).  
On some Linux distros install the Tkinter system package first (e.g. `sudo apt install python3-tk`).

Optional packages (also listed in `requirements.txt`):

- `anthropic` — AI recommendations
- `Pillow` — cover image support
- `pytest` — running the test suite

API key can be set in the app Settings or via the `ANTHROPIC_API_KEY` environment variable.

## Structure (refactored)

- `main.py` — thin entry point
- `src/wiborada/app.py` — main `LibraryApp` window
- `src/wiborada/database.py` — SQLite layer
- `src/wiborada/themes.py` — color palettes and theme switching
- `src/wiborada/utils.py` — file and path helpers
- `src/wiborada/api/isbn.py` — Open Library ISBN and cover helpers
- `src/wiborada/ui/widgets.py` — reusable widgets (BookCard, VirtualBookList, etc.)
- `src/wiborada/ui/dialogs.py` — all dialog windows

## Tests

```bash
python -m pytest tests/ -v
```

## Notes

- Database lives at `~/.personal_library.db`.
- This refactor preserves every feature listed in FEATURES.md.
- The previous monolithic `library_manager.py` and incomplete modular files have been replaced by this structure.
