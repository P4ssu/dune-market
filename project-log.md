# Dune Market project log

Newer entries are at the top. Each entry: date, what was done, why. Add a new entry at the end of a session.

## 2026-10-19 (session 5)

- **Chest hover fix.** Hovering items in chests/storage showed no price popup: the storage screen has the same Q/E tab bar as the Exchange, only about 0.012 of the width nearer the middle, so `exchange_tab_open` called it the Exchange and the popup stayed silent on purpose. The check now looks at narrow strips only the Exchange's key boxes fill (Exchange 0.38-0.40, chest 0.09-0.12; threshold 0.25). Test on the four chest screenshots added; 213 tests pass.
- **Release 1.2.1** (chest popups). Trend arrows (▲/▼) need two Sell scans of an item at least 12 hours apart (at most 7 days old); checked with the owner.

## 2026-10-19 (session 4)

- **Public GitHub repository** (P4ssu/dune-market). Before publishing, the history was rewritten to use the GitHub noreply email (tree identical), `.gitignore` and a README were added.
- **Self-update.** Pushing a tag `vX.Y.Z` makes GitHub Actions test, build and publish `DuneMarket-update.zip` (program only, no settings or keys) plus a `.sha256`. The program checks the newest release, downloads it in the background, verifies the checksum and installs it at the next start through a small script that never touches `config.toml` or `prices.db`. Tested on the packaged exe in a temporary folder and against the real release. Steps: `docs/releasing.md`.
- **Fixes:** armor tooltips (header far above the cursor), 16:9 monitors without black bars.
- **Release 1.2.0 published** on GitHub (https://github.com/P4ssu/dune-market/releases/tag/v1.2.0), verified against the real GitHub API (check, verified download, no `config.toml` in the package). 212 tests pass.
- **Bridge for 1.1.0 copies.** Added a row to the shared Supabase `releases` table: version 1.2.0, download link to the installer zip on the owner's Google Drive, note "Reinstall once with this new zip". Copies on 1.1.0 check that table, so they show an in-game notice and reinstall once; from 1.2.0 on, copies update themselves from GitHub. Copies older than 1.1.0 have no update check and must be told on Discord.
- **Open:** friends reinstall once with the 1.2.0 zip; tell pre-1.1.0 users on Discord.

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
