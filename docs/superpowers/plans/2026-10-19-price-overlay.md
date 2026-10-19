# Dune Market Price Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Windows program that reads Dune: Awakening Exchange screens (Sell and Buy tabs) into a price database and shows a price popup when the player hovers an item in the inventory.

**Architecture:** A background program captures the screen, runs OCR, and turns the text into typed rows. Parsers are pure functions over OCR words so they are tested against the owner's screenshots. A `PriceStore` interface has a local SQLite implementation first and a shared remote implementation later (after the Funcom permission gate). A transparent always-on-top window shows the popup.

**Tech Stack:** Python 3.11+, `mss` (screen capture), `rapidocr-onnxruntime` (OCR), `Pillow`, `PyQt6` (popup window), `sqlite3` (stdlib), `httpx` (remote store), `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-19-price-overlay-design.md`

## Global Constraints

- Windows, PC only. The program never reads game memory, injects into the game, intercepts network traffic or sends input to the game.
- Game language is English. Owner's resolution is 2560x1600; friends use other resolutions, so every screen region is derived from the detected frame size (no per-user calibration).
- World is Andromeda (Europe) only. One shared database for 2-3 friends.
- The program must never read, store or upload the character name or Solari balance shown in the screen corners.
- The My Orders tab is never scanned.
- Popup shows: item name, average price with trend, cheapest price, listing count (only when known from a Buy scan), data age and contributor name. Data older than 24 hours is marked "old".
- Every stored price has a grade: "unknown" when scanned with GRADE: ALL, the specific grade otherwise.
- Contributor name comes from a local config file entered once.
- Code, docs and commit messages are in English. Commit messages follow the repo's attribution rules.
- Test screenshots live in `screenshots/` (names: `sell.png`, `buy tab.png`, `my orders tab.png`, `item hover.png`, `blueprint hover.png`, `schematic hover.png`). They contain the owner's character name, so they are local-only fixtures: tests skip when a file is missing, and the owner confirms before `screenshots/` is added to `.gitignore`.

## Review Focus

1. OCR misreads a digit (for example "46,000" read as "4,000"): a price that jumps more than 5x or below 0.2x of the stored value is not accepted until it is seen twice in a row. Pinned in Task 7.
2. The My Orders tab (or any other screen) is open when the scanner runs: nothing is stored. Pinned in Tasks 2 and 7.
3. The hovered item has no price data yet: popup says "No price data yet" instead of failing. Pinned in Task 8.
4. Hovering an empty slot or a non-item tooltip (stats, character panel): no popup and no crash. Pinned in Task 5.
5. The game is closed, minimised or the frame is black: scanner and hover loop keep running without errors. Pinned in Task 7.

---

## File Structure

- `pyproject.toml`: package metadata and dependencies.
- `src/dune_market/models.py`: dataclasses and enums shared by all modules.
- `src/dune_market/ocr.py`: OCR wrapper returning `Word` lists.
- `src/dune_market/screens.py`: classifies which Exchange screen (or none) is shown.
- `src/dune_market/parse_sell.py`, `parse_buy.py`, `parse_tooltip.py`: pure parsers over words.
- `src/dune_market/stats.py`: average, cheapest, trend, staleness from observations.
- `src/dune_market/store.py`: `PriceStore` protocol; `store_sqlite.py`: local implementation; `store_remote.py`: shared implementation (Task 11).
- `src/dune_market/capture.py`: screen capture and cursor position.
- `src/dune_market/scanner.py`: scan loop and misread guard.
- `src/dune_market/overlay.py`: popup window and hover loop.
- `src/dune_market/config.py`: reads `config.toml`.
- `src/dune_market/__main__.py`: commands `scan` and `overlay`.
- `tests/`: one test file per module, plus `tests/conftest.py` with cached OCR of the screenshots.

---

### Task 1: Project scaffold, shared models and OCR wrapper

**Files:**
- Create: `pyproject.toml`, `src/dune_market/__init__.py`, `src/dune_market/models.py`, `src/dune_market/ocr.py`, `tests/conftest.py`, `tests/test_ocr.py`

**Interfaces:**
- Produces (in `models.py`): `Word(text: str, x: float, y: float, w: float, h: float)` (top-left pixel box); `Screen` enum `SELL | BUY | MY_ORDERS | OTHER`; `SellRow(category: str, name: str, quantity: int, avg_price: int, low_price: int)`; `BuyRow(category: str, name: str, price: int, expires_in_s: int)`; `ItemKey(name: str, category: str, grade: str)`; `Observation(key: ItemKey, kind: Literal["sell", "buy"], observed_at: datetime, contributor: str, avg: int | None, low: int | None, price: int | None, expires_in_s: int | None)`; `ItemStats(key: ItemKey, avg: int | None, cheapest: int | None, trend_pct: float | None, listing_count: int | None, updated_at: datetime, contributor: str, stale: bool)`.
- Produces (in `ocr.py`): `read_words(image: PIL.Image.Image, offset: tuple[int, int] = (0, 0)) -> list[Word]` (word positions shifted by `offset`); `parse_price(text: str) -> int | None` (strips thousands commas and a trailing Solari symbol read as `S`, `$` or `5`-lookalikes only when it follows a space).
- Produces (in `conftest.py`): fixture `shot_words(name: str) -> list[Word]` that OCRs `screenshots/<name>.png` once per session and skips the test if the file is missing.

- [ ] **Step 1: Write the failing tests** in `tests/test_ocr.py`: `test_parse_price_handles_commas` (`parse_price("56,359") == 56359`), `test_parse_price_strips_solari_symbol` (`parse_price("56,359 S") == 56359`), `test_parse_price_rejects_text` (`parse_price("abc") is None`), `test_read_words_finds_atmospheric_fabric` (uses `shot_words("sell")`; assert a word `"Fabric"` exists).
- [ ] **Step 2: Run** `pytest tests/test_ocr.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Create the package and implement** the models and `ocr.py`. One shared `RapidOCR` instance created lazily; convert its boxes to `Word`.
- [ ] **Step 4: Run** `pytest tests/test_ocr.py -v`. Expected: PASS (or SKIP for the screenshot test if the file is absent).
- [ ] **Step 5: Commit** (`feat: project scaffold, models and OCR wrapper`).

### Task 2: Screen classifier

**Files:**
- Create: `src/dune_market/screens.py`, `tests/test_screens.py`

**Interfaces:**
- Consumes: `Word`, `Screen`, `shot_words`.
- Produces: `classify(words: list[Word]) -> Screen`.

Rules (header text, not colours, so scale does not matter): `SELL` when the words contain `AVG.` and `LOW`; `MY_ORDERS` when they contain `QUANTITY` and `EXPIRATION`, or `COMPLETED` and `ACTIVE`; `BUY` when they contain `EXPIRATION` and `FILTER` and no `QUANTITY`; otherwise `OTHER`.

- [ ] **Step 1: Write the failing tests**: `test_classify_sell` (`shot_words("sell")` -> `Screen.SELL`), `test_classify_buy` (`"buy tab"` -> `BUY`), `test_classify_my_orders` (`"my orders tab"` -> `MY_ORDERS`), `test_classify_inventory_is_other` (`"item hover"` -> `OTHER`), `test_classify_empty_words_is_other` (`classify([]) == Screen.OTHER`).
- [ ] **Step 2: Run** `pytest tests/test_screens.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `classify` following the rules above.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** (`feat: classify Exchange screens`).

### Task 3: Sell tab parser

**Files:**
- Create: `src/dune_market/parse_sell.py`, `tests/test_parse_sell.py`

**Interfaces:**
- Consumes: `Word`, `SellRow`, `parse_price`.
- Produces: `parse_sell(words: list[Word]) -> list[SellRow]`.

Approach: find the column header words (`QUANTITY`, `AVG.`, `LOW`) to get column x positions; group the words below the header into rows by the category line (a line matching `^[A-Z][A-Z &]+ - [A-Z][A-Z &]+$`); the item name is the next line down in the name column; numbers are the words nearest each column x. Ignore everything left of the name column and above the header (this skips the character name and Solari balance).

- [ ] **Step 1: Write the failing tests**: `test_parse_sell_rows_from_screenshot` asserting the first row equals `SellRow("MISC - COMPONENTS", "Atmospheric Filtered Fabric", 24, 56359, 46000)` and that `Calibrated Servok` has `(11, 105825, 77110)`, `Cobalt Paste` `(14, 19283, 8900)`, `Complex Machinery` `(48, 267820, 40000)`, `Duraluminum Ingot` `(3, 19988, 17888)`, `EMF Generator` `(3, 2508, 1899)`; `test_parse_sell_never_includes_character_name` (no row's name contains `Passu`); `test_parse_sell_scaled_screenshot` (the same screenshot resized to 1920x1200 yields the same six rows); `test_parse_sell_empty` (`parse_sell([]) == []`).
- [ ] **Step 2: Run** `pytest tests/test_parse_sell.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `parse_sell` per the approach. Rows with an unparseable number are dropped, not guessed.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** (`feat: parse Sell tab rows`).

### Task 4: Buy tab parser with grade label

**Files:**
- Create: `src/dune_market/parse_buy.py`, `tests/test_parse_buy.py`

**Interfaces:**
- Consumes: `Word`, `BuyRow`, `parse_price`.
- Produces: `parse_buy(words: list[Word]) -> tuple[str, list[BuyRow]]` where the first value is the grade label read from the bottom-left `GRADE: <value>` text, lowercased (`"all"` when ALL, otherwise the value as shown), and `"all"` when the label is not readable; `parse_expiration(text: str) -> int | None` returning seconds for strings like `2h 21m 13s`, `2d 6h 42m`, `9h 23m 1s`.

- [ ] **Step 1: Write the failing tests**: `test_parse_expiration_formats` (`"2h21m13s" -> 8473`, `"2d 6h 42m" -> 196920`, `"abc" -> None`); `test_parse_buy_rows_from_screenshot` asserting the first row is `BuyRow("GARMENTS - LIGHT ARMOR", "The Forge Boots", 10000000, 8473)` and the rows `The Forge Chestpiece`, `The Forge Gloves`, `The Forge Helmet`, `The Forge Pants` are present; `test_parse_buy_grade_all` (grade `"all"`); `test_parse_buy_scaled_screenshot` (1920x1200 gives the same rows); `test_parse_buy_ignores_partial_last_row` (the cut-off row at the bottom is not returned).
- [ ] **Step 2: Run** `pytest tests/test_parse_buy.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `parse_buy` and `parse_expiration`, using the `PRICE` and `EXPIRATION` header positions as column anchors, same grouping idea as Task 3.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** (`feat: parse Buy tab rows and grade label`).

### Task 5: Hover tooltip parser

**Files:**
- Create: `src/dune_market/parse_tooltip.py`, `tests/test_parse_tooltip.py`

**Interfaces:**
- Consumes: `Word`.
- Produces: `parse_tooltip(words: list[Word], cursor: tuple[int, int]) -> tuple[str, str] | None` returning `(name, category)` of the tooltip header closest to the cursor, or `None`.

Approach: group words into lines; a header is a line matching the category pattern from Task 3 with a non-empty line directly below it; choose the header with the smallest distance to the cursor. Names or categories that look like other UI (`CHARACTER`, `LOADOUT`, `Show Stats`) never match because they lack the ` - ` pattern.

- [ ] **Step 1: Write the failing tests** (cursor positions are the hovered slot centres in original pixels): `test_tooltip_item` (`item hover` with cursor `(842, 927)` -> `("Spice-infused Plastanium Dust", "MISC - COMPONENTS")`); `test_tooltip_schematic_trigger` (`schematic hover`, cursor `(531, 620)` -> `("Quick-release Trigger", "SCHEMATIC - UNIQUE")`); `test_tooltip_blueprint_gauntlets` (`blueprint hover`, cursor `(223, 620)` -> `("Mendek's Gauntlets", "SCHEMATIC - UNIQUE")`); `test_tooltip_none_without_tooltip` (`parse_tooltip([], (0, 0)) is None`; Review Focus 4); `test_tooltip_ignores_ui_labels` (a word list containing only `CHARACTER`, `LOADOUT` and `Show Stats` gives `None`).
- [ ] **Step 2: Run** `pytest tests/test_parse_tooltip.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `parse_tooltip` per the approach.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Look for grade information.** Search the three hover screenshots' OCR words for a grade marker; write the finding (found or not found, and where) as a short note in the spec under "Grades". If not found, the hover popup shows every known grade of the item.
- [ ] **Step 6: Commit** (`feat: parse inventory tooltip header`).

### Task 6: Statistics and local store

**Files:**
- Create: `src/dune_market/stats.py`, `src/dune_market/store.py`, `src/dune_market/store_sqlite.py`, `tests/test_stats.py`, `tests/test_store_sqlite.py`

**Interfaces:**
- Consumes: `Observation`, `ItemKey`, `ItemStats`.
- Produces (`store.py`): `class PriceStore(Protocol)` with `add(self, observations: list[Observation]) -> None`, `latest_sell(self, key: ItemKey) -> Observation | None`, and `lookup(self, name: str, category: str, now: datetime) -> list[ItemStats]` (one entry per grade, newest first).
- Produces (`stats.py`): `compute_stats(key: ItemKey, observations: list[Observation], now: datetime) -> ItemStats | None`.
- Produces (`store_sqlite.py`): `SqliteStore(path: str)` implementing `PriceStore`.

Definitions: `avg` is the `avg` of the newest `sell` observation. `cheapest` is the lowest of the newest sell `low` and the buy `price` values from the newest buy scan within 24 hours. `listing_count` is the number of buy observations at the newest buy-scan timestamp, or `None` if there is none. `trend_pct` compares the newest sell `avg` with the newest sell `avg` that is at least 12 hours older (within 7 days), or `None`. `stale` is true when the newest observation is older than 24 hours. A buy price above 20 times the known avg is ignored as an outlier.

- [ ] **Step 1: Write the failing tests**: `test_avg_is_newest_sell`; `test_cheapest_uses_lower_of_sell_low_and_buy`; `test_listing_count_from_newest_buy_scan`; `test_trend_up_ten_percent` (older avg 100, newest avg 110 -> `10.0`); `test_trend_none_without_older_data`; `test_stale_after_24_hours`; `test_buy_outlier_ignored` (avg 10 000, a 10 000 000 listing does not become cheapest or counted); `test_lookup_returns_one_entry_per_grade`; `test_sqlite_roundtrip` (add observations, reopen the file, `lookup` returns the same stats); `test_lookup_unknown_item_is_empty`.
- [ ] **Step 2: Run** `pytest tests/test_stats.py tests/test_store_sqlite.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `compute_stats`, the `PriceStore` protocol and `SqliteStore`. One table `observations` with the `Observation` fields flattened; an index on `(name, category)`.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** (`feat: price statistics and local SQLite store`).

### Task 7: Scanner service and config

**Files:**
- Create: `src/dune_market/capture.py`, `src/dune_market/config.py`, `src/dune_market/scanner.py`, `src/dune_market/__main__.py`, `tests/test_scanner.py`, `config.example.toml`

**Interfaces:**
- Consumes: `classify`, `parse_sell`, `parse_buy`, `read_words`, `PriceStore`, `Observation`.
- Produces (`capture.py`): `grab_frame() -> PIL.Image.Image | None` (primary monitor, `None` on failure); `cursor_position() -> tuple[int, int]`.
- Produces (`config.py`): `load_config(path: str) -> Config` with `contributor: str` and an optional `[remote]` table (`url`, `key`).
- Produces (`scanner.py`): `observations_from_words(words: list[Word], contributor: str, now: datetime) -> list[Observation]` (empty for `MY_ORDERS` and `OTHER`; Buy grade from the grade label, `"unknown"` when `all`); `class Scanner` with `__init__(store: PriceStore, contributor: str, grab=grab_frame)` and `scan_once(now: datetime) -> int` returning the number of observations stored; `accept(obs: Observation, previous: Observation | None) -> bool`, the misread guard.
- `__main__.py`: `python -m dune_market scan` runs `scan_once` about once per second until Ctrl+C.

- [ ] **Step 1: Write the failing tests**: `test_sell_screenshot_becomes_sell_observations` (six observations, kind `sell`, contributor set, grade `"unknown"`); `test_buy_all_grade_is_unknown`; `test_my_orders_yields_nothing` (Review Focus 2); `test_inventory_yields_nothing`; `test_guard_rejects_big_jump` (avg 56 359 -> 4 000 rejected, Review Focus 1); `test_guard_accepts_value_seen_twice` (same odd value in two consecutive scans is accepted the second time); `test_scan_once_with_black_frame_stores_nothing` (a fake `grab` returning an all-black image; no exception, returns `0`, Review Focus 5); `test_scan_once_when_grab_returns_none` (returns `0`).
- [ ] **Step 2: Run** `pytest tests/test_scanner.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the modules. The scanner OCRs only when the frame changed noticeably since the last scan (cheap pixel-difference check) to keep CPU use low.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** (`feat: scanner service with misread guard`).

### Task 8: Popup overlay and hover loop

**Files:**
- Create: `src/dune_market/overlay.py`, `tests/test_popup_text.py`
- Modify: `src/dune_market/__main__.py` (add the `overlay` command)

**Interfaces:**
- Consumes: `parse_tooltip`, `PriceStore.lookup`, `grab_frame`, `cursor_position`, `read_words`.
- Produces: `format_popup(name: str, stats: list[ItemStats]) -> list[str]` (pure, returns the popup lines); `class OverlayApp` that runs the hover loop and shows a frameless, transparent, click-through, always-on-top PyQt6 window near the tooltip.

`format_popup` lines (layout "B"): title; `Avg price: <n> <▲|▼> <pct>%` (trend omitted when `None`); `Cheapest now: <n>`; `Listings: <n>` (omitted when `None`); `Updated <age> by <contributor>` with ` (old)` appended when stale; the grade shown as `Grade: <g>` or `Grade unknown`. With several grades, one block per grade, newest first. With no stats the lines are the title and `No price data yet`.

Hover loop: Exchange tabs list items with the same category-line pattern as tooltips, so the loop calls `parse_tooltip` only when the top header band of the frame (OCR of the top 12%) does not contain `MY ORDERS`, which means no Exchange tab is open. When the cursor has been still for 0.4 s, crop a region around the cursor (about 30% of the frame width and 25% of its height), OCR it with `offset` set to the crop origin, call `parse_tooltip`, and show or hide the popup. Errors in the loop are logged and the loop continues.

- [ ] **Step 1: Write the failing tests**: `test_popup_full_data` (title, avg with `▲ 8%`, cheapest, listings, `Updated 2 h ago by Mari`); `test_popup_stale_marked_old`; `test_popup_omits_missing_listing_count`; `test_popup_no_data` (lines are the title and `No price data yet`, Review Focus 3); `test_popup_grade_unknown_label`; `test_popup_multiple_grades_listed`.
- [ ] **Step 2: Run** `pytest tests/test_popup_text.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `format_popup`, then `OverlayApp`. Document in the module docstring that the game must run in borderless windowed mode for the overlay to appear over it.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** (`feat: price popup and hover loop`).

### Task 9: Real-game check (manual)

**Files:**
- Modify: `docs/superpowers/specs/2026-10-19-price-overlay-design.md` (record findings under a "Prototype findings" heading)

- [ ] **Step 1:** Copy `config.example.toml` to `config.toml` and enter the contributor name.
- [ ] **Step 2:** Start `python -m dune_market scan`, open the Sell tab, then scroll the Buy tab through two categories. Expected: the console reports stored observations; `My Orders` stores nothing.
- [ ] **Step 3:** Stop it, start `python -m dune_market overlay`, open the inventory and hover a scanned item, a schematic and an unscanned item. Expected: popup next to the tooltip with values matching the Sell tab; "No price data yet" for the unscanned item.
- [ ] **Step 4:** Record in the spec: OCR mistakes seen, popup position problems, whether grade is visible anywhere, CPU use while scanning.
- [ ] **Step 5: Commit** (`docs: prototype findings`).

### Task 10: Gate: Funcom permission (no code)

- [ ] **Step 1:** The owner checks the Funcom Terms of Service and rules of conduct, and asks Funcom (support or Discord) whether screen reading with an overlay is allowed. The owner records the answer in the spec.
- [ ] **Step 2:** Tasks 11 and onward, and sharing the program with friends, start only after the owner confirms the answer is acceptable.

### Task 11: Shared remote store

**Files:**
- Create: `src/dune_market/store_remote.py`, `tests/test_store_remote.py`
- Modify: `src/dune_market/config.py`, `src/dune_market/__main__.py` (use `RemoteStore` when `[remote]` is configured)

**Interfaces:**
- Consumes: `PriceStore`, `Observation`, `compute_stats`.
- Produces: `RemoteStore(url: str, key: str, client: httpx.Client | None = None)` implementing `PriceStore` against a hosted Postgres REST API (Supabase free tier, chosen by the plan author; the owner creates the account and shares one key with the friends). Uploads batched; reads fetch the item's recent observations and use `compute_stats`.

- [ ] **Step 1: Write the failing tests** with `httpx.MockTransport`: `test_add_posts_batch`; `test_lookup_builds_stats_from_remote_rows`; `test_remote_error_does_not_raise_in_scanner` (network failure returns quietly and keeps the observations queued for retry); `test_key_sent_in_header`.
- [ ] **Step 2: Run** `pytest tests/test_store_remote.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `RemoteStore`, the SQL table definition in `docs/remote-schema.sql`, and the config wiring.
- [ ] **Step 4: Run** the full suite `pytest -v`. Expected: PASS.
- [ ] **Step 5: Manual check** with two machines (the owner and one friend): scan on one, see the popup data on the other.
- [ ] **Step 6: Commit** (`feat: shared remote price store`).

### Task 12: Project memory

**Files:**
- Modify: `roadmap.md`, `project-log.md`

- [ ] **Step 1:** Update `roadmap.md` (done, in progress, planned) and add a new top entry to `project-log.md` (date, what was done, why), as required by `CLAUDE.md`.
- [ ] **Step 2: Commit** (`docs: update roadmap and project log`).

---

## Out of this plan (later)

Packaging as a single `.exe`, a drop history tab, other Worlds, and any change to how grades are matched once Task 9 shows what the game exposes.
