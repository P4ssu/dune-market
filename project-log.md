# Dune Market project log

Newer entries are at the top. Each entry: date, what was done, why. Add a new entry at the end of a session.

## 2026-10-19 (session 3)

- **Real-game fixes.** The first real run showed the scanner burning about 95% CPU (OCR thread oversubscription plus continuous OCR), which also made the hover popup arrive too late. Fixed with: OCR capped at 6 threads and a better detection setting, scanner and hover only active when the game window is in front, Exchange tab bar detected from pixels (no OCR), tooltip banner found by its gold border lines (hover about 0.3 s, near zero cost when no tooltip), header read cache, popup stays while the same tooltip is under the cursor, painted dark/gold popup, in-game scan notices, `run` command.
- **Grades and matching.** Grade read from the tooltip badge and Buy filter; items matched by a spelling-independent key because the OCR drops spaces.
- **Sharing.** Local-first sync (`sync.py`) with a Supabase table (`docs/remote-schema.sql`, `docs/supabase-setup.md`) and a PyInstaller package (`packaging/`). Sync is local-first instead of reading the remote on every hover, so popups stay instant and work offline.
- **Supabase set up** (table `observations` with read/add-only policies), tested end to end with two simulated friends; friends' zip built.
- **Search window** opened with a configurable hotkey (default Ctrl+Shift+F), tested by the owner in the game.
- **Open:** try with a real friend; Funcom's rules are unconfirmed; the branch `feature/price-overlay` is not merged.

## 2026-10-19 (session 2)

- **Researched, designed and prototyped a price overlay.** No official Exchange API exists and dune.exchange has poor coverage, so the project builds its own tool: screen reading (OCR) of the Sell and Buy tabs into a price database, plus a popup shown when hovering an inventory item. Friends (2-3, PC, World Andromeda) will share one database later.
- **Why OCR:** the game shows nothing when an item is received, so hover is the trigger; the Sell tab already shows AVG. and LOW prices for backpack items, and the Buy tab lists market listings.
- **Built tasks 1-8** of `docs/superpowers/plans/2026-10-19-price-overlay.md` on branch `feature/price-overlay` (84 tests). Real OCR found two problems the fake tests missed (tooltip name cut by the crop, name split into two spans); both fixed.
- **Open:** real-game check, Funcom permission gate, remote store, grades.

## 2026-10-19

- **Project created.** Live ingame dune market prices
