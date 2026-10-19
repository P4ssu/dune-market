# Dune Market project log

Newer entries are at the top. Each entry: date, what was done, why. Add a new entry at the end of a session.

## 2026-10-19 (session 2)

- **Researched, designed and prototyped a price overlay.** No official Exchange API exists and dune.exchange has poor coverage, so the project builds its own tool: screen reading (OCR) of the Sell and Buy tabs into a price database, plus a popup shown when hovering an inventory item. Friends (2-3, PC, World Andromeda) will share one database later.
- **Why OCR:** the game shows nothing when an item is received, so hover is the trigger; the Sell tab already shows AVG. and LOW prices for backpack items, and the Buy tab lists market listings.
- **Built tasks 1-8** of `docs/superpowers/plans/2026-10-19-price-overlay.md` on branch `feature/price-overlay` (84 tests). Real OCR found two problems the fake tests missed (tooltip name cut by the crop, name split into two spans); both fixed.
- **Open:** real-game check, Funcom permission gate, remote store, grades.

## 2026-10-19

- **Project created.** Live ingame dune market prices
