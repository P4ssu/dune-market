# Dune Market

Live Exchange prices inside **Dune: Awakening**, for a group of friends.

An unofficial, free Windows tool that reads the Exchange (market) screens and shows prices right in the game:

- **Hover an item** in your inventory: lowest price of the last scan, average price, trend and data age, per grade.
- **Tray icon** (bottom right of the taskbar): search, pause popups or scanning, open the log, quit.
- **Ctrl+Shift+F**: search any item by name and see its prices; `cobalt paste:5` shows grade 5 only. The search also shows when the cheapest listing expires.
- **Shared prices:** what one player scans in the Buy / Sell tabs is shared with the group through a small shared database.

> **Unofficial.** Not made or endorsed by Funcom, and Funcom has not confirmed that screen-reading tools are allowed.
> The program only looks at the screen while the game is the active window. It does not read the game's memory or files,
> does not touch its network traffic and does not send input to the game. Use it at your own risk.

## For players

Get the installer zip from the person who invited you (it contains the settings for the shared database).
Unzip it, run `Install.bat` and follow `README.txt`. New versions are downloaded and installed automatically
(published as GitHub releases; see `docs/releasing.md`).

## For developers

```
python -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]
.venv\Scripts\python -m pytest
.venv\Scripts\python -m dune_market run
```

Many tests use screenshots of the game that are not part of this repository (they contain player names), so they
skip themselves when the files are missing. Design notes are in `docs/superpowers/specs/`, the build and release
steps in `packaging/README.md` and `docs/releasing.md`.
