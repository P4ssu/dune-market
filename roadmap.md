# Dune Market roadmap

Update this file when something gets done or the plan changes. History and reasons are in `project-log.md`.

## Done

- Researched price sources: no official Exchange API, dune.exchange covers few Worlds and has no public API.
- Design and implementation plan (`docs/superpowers/specs/`, `docs/superpowers/plans/`).
- Prototype code (tasks 1-8 of the plan): OCR screen parsers for the Sell tab, Buy tab and inventory tooltips, statistics, local SQLite store, scanner with misread guard, hover popup overlay. 84 automated tests on the owner's screenshots.

## In progress

- Task 9: real-game check by the owner (run `scan`, then `overlay`, record findings in the spec).

## Planned

- Task 10 (gate): check Funcom's rules or ask Funcom whether a screen-reading overlay is allowed. Nothing is shared with friends before this.
- Task 11: shared remote price store (Supabase free tier) so friends pool prices in World Andromeda.
- Single `.exe` packaging for friends.
- Drop history tab (compare backpack contents between scans).
- Grades: find out how the Sell tab and tooltips expose an item's grade.
- Faster hover lookup (about 1.7 s warm now; three OCR passes).
