# Dune Market roadmap

Update this file when something gets done or the plan changes. History and reasons are in `project-log.md`.

## Done

- Researched price sources: no official Exchange API, dune.exchange covers few Worlds and has no public API.
- Design and implementation plan (`docs/superpowers/specs/`, `docs/superpowers/plans/`).
- Prototype code (tasks 1-8 of the plan, plus later fixes): OCR screen parsers for the Sell tab, Buy tab and inventory tooltips, statistics, local SQLite store, scanner with misread guard, hover popup overlay. 152 automated tests on the owner's screenshots.
- Real-game use: scan, hover popup (styled, about 0.3 s), in-game scan notices, grades from tooltips, pixel-based Exchange detection (almost no CPU when idle).
- Item search window (hotkey, default Ctrl+Shift+F, configurable): live results with grade, average, cheapest and age.
- Self-updating program: GitHub releases are built by Actions on a version tag; running copies download, verify and install updates at the next start (tested end to end). Public repo https://github.com/P4ssu/dune-market.
- Local-first sync with a shared Supabase table and a PyInstaller package for friends (129 MB zip).
- Release 1.2.0 published on GitHub and verified; Supabase `releases` row points 1.1.0 copies to the 1.2.0 installer zip (212 tests pass).

## In progress

- Friends reinstall once with the 1.2.0 zip (1.1.0 copies see an in-game notice); tell pre-1.1.0 users on Discord.
- Owner: decide about Funcom's rules (nothing in the code touches the game process; permission is not officially confirmed).

## Planned

- Drop history tab (compare backpack contents between scans).
- Per-grade Sell prices for rows other than the selected one.
- Support for a monitor other than the main one.
- Optional Windows code signing.
