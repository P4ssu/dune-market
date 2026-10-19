# Dune Market roadmap

Update this file when something gets done or the plan changes. History and reasons are in `project-log.md`.

## Done

- Researched price sources: no official Exchange API, dune.exchange covers few Worlds and has no public API.
- Design and implementation plan (`docs/superpowers/specs/`, `docs/superpowers/plans/`).
- Prototype code (tasks 1-8 of the plan, plus later fixes): OCR screen parsers for the Sell tab, Buy tab and inventory tooltips, statistics, local SQLite store, scanner with misread guard, hover popup overlay. 152 automated tests on the owner's screenshots.
- Real-game use: scan, hover popup (styled, about 0.3 s), in-game scan notices, grades from tooltips, pixel-based Exchange detection (almost no CPU when idle).
- Local-first sync with a shared Supabase table and a PyInstaller package for friends (129 MB zip).

## In progress

- Owner: create the Supabase project (`docs/supabase-setup.md`), then build the friends' zip with `packaging/make-friend-zip.ps1`.
- Owner: decide about Funcom's rules (nothing in the code touches the game process; permission is not officially confirmed).

## Planned

- Real test of sharing with one friend (two computers).
- Drop history tab (compare backpack contents between scans).
- Per-grade price on the Sell tab for rows other than the selected one.
- Auto-update or a version check for the friends' package.
