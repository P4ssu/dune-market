# Dune Market price overlay: design

Date: 2026-10-19

## Intent and why

A small group of Dune: Awakening players (the owner plus 2-3 friends, all on PC, all on the World **Andromeda**, region Europe) wants to know, the moment they receive a new item or blueprint, whether it is worth selling. Today they have to open the Exchange terminal and look it up by hand.

No official market API exists, and the community site dune.exchange covers few Worlds and has no public API. So the group builds its own tool and pools the prices each member sees.

The owner is learning programming. Code should be simple and readable, and the design favours few moving parts.

## What it does

The game shows nothing when an item or blueprint is received, so the trigger is the player hovering the mouse over an item, blueprint or schematic in the backpack (the inventory tooltip appears). A small popup then appears next to the tooltip (the owner chose the "B" layout):

- Item name
- Average price, with a trend arrow and percentage (up or down)
- Cheapest current listing
- Number of listings seen (only available from Buy tab scans, so it may be partial or missing)
- Age of the data and the name of the member who captured it (for example "Updated 2 h ago by Mari")

Prices come from a **shared database**. Whenever any member opens an item in the Exchange terminal, the program reads the listings from the screen and uploads them. Everyone then sees the combined data.

## Goals

- Show the popup within about a second or two of receiving an item.
- Pool price observations from all members into one shared database for the World Andromeda.
- Be easy for a beginner to read, run and change.
- Work on Windows PC next to the game without touching game files, memory or network traffic.

## Non-goals

- No price threshold or "worth selling" verdict. The owner wants raw numbers (average and cheapest) and decides alone.
- No support for other Worlds, regions, consoles or the public at launch.
- No API from dune.exchange or any other site.
- No game automation: the program never sends input to the game.

## Anti-goals (a failure even if it technically works)

- Anything that risks a ban: reading game memory, injecting into the game, intercepting its network traffic, or sending input.
- Wrong numbers shown with confidence (misread digits, stale data presented as fresh).
- A setup so heavy that friends will not install it.

## Constraints

- Windows, PC only. Game language and screen resolution of the members are not yet known.
- Screen capture plus text recognition (OCR) is the only data source. Funcom's rules forbid third-party add-ons and traffic interception. The TH.GL companion app claims to be allowed for its read-only approach, but no official confirmation covers a self-built tool. Before sharing the tool with friends, the owner should check the Terms of Service or ask Funcom.
- The shared database must be free or nearly free and must not require friends to run a server.
- Project language: code, docs and commit messages are written in English.

## Decisions made together

- Popup layout "B" (name, average with trend, cheapest, listing count, data age and contributor).
- Shared database for all friends, one World (Andromeda).
- Prices are captured automatically from the Exchange screen while a member browses it. Two scanners: one for the Sell tab, one for the Buy tab. The My Orders tab must never be scanned.
- The popup is triggered by hovering an item in the inventory, not by a "new item" message (the game shows none). A "drop history" tab (what was received, with prices and totals) is a later idea, possibly built by comparing backpack contents between scans.

## Left to the builder (builder's call, proposed defaults)

These were proposed by the assistant and not yet confirmed by the owner:

- Language: Python, because it is easy to learn and has ready-made screen-capture and OCR libraries.
- Local component: a background program that captures the screen, runs OCR, shows the popup in a transparent always-on-top window.
- Shared storage: a hosted free-tier database service so friends need no server of their own. The builder picks the service and the sign-in method.
- Reading the Exchange screen: how to find the listing table and parse item, quantity and price reliably.
- How to define "average" and "trend" (for example over the last 7 days, ignoring outliers) and how to filter obvious OCR mistakes.
- How to match an item seen on screen to an entry in the database (name normalisation).

## Assistant's calls (from the builder check, to be confirmed by the owner)

- **Order of work:** build a single-user prototype first (screen reading and popup using only the owner's own setup, with screen regions in a config file). Add the shared database and friends only after the Funcom permission check.
- **Shared database trust model:** the owner creates the account and shares one access key with the 2-3 friends. Everyone is trusted; no per-user logins. Basic sanity checks drop obviously wrong prices.
- **Contributor name:** entered once in a local config file.
- **Packaging:** start as a Python script. A single .exe for friends comes after the prototype works.
- **Stale data:** show the age always; mark data older than 24 hours as "old" in the popup.

## Setup facts from the owner

- Game language: English (all members assumed).
- Owner's resolution: 2560x1600. Friends use other, unknown resolutions, so the program must detect the screen size itself and scale its screen regions accordingly. No manual per-user calibration should be needed in the normal case.
- UI scale: not yet confirmed; assume default.

## What the owner's screenshots show

Screenshots are in `screenshots/` (2560x1600, English). Facts read from them:

- **Sell tab** (`sell.png`): table of the items in the player's own backpack with columns NAME (category line above the item name), QUANTITY, AVG. PRICE, LOW PRICE. One screen gives many items with game-provided average and lowest prices. Only items in the backpack appear.
- **Buy tab** (`buy tab.png`): one row per listing with category line, item name, PRICE and EXPIRATION (time left, counting down). Filtered by category (Garments, Weapons and so on) and grade; the player scrolls to see more. No average price. Some listings are obvious outliers (for example 10,000,000 for common armor pieces), so the scanner must filter extreme prices. Expiration times can help tell listings apart between scans.
- **My Orders tab** (`my orders tab.png`): the player's own listings (QUANTITY, PRICE, EXPIRATION). These are not market prices and must be ignored. The active tab (BUY, SELL, MY ORDERS) is highlighted in the header at the top, which the program can use to decide which scanner to run, or none.
- **Inventory hover** (`item hover.png`, `blueprint hover.png`, `schematic hover.png`): a tooltip with a gold-outlined header that has a category line (for example "MISC - COMPONENTS" or "SCHEMATIC - UNIQUE") and the item name below it. The tooltip appears in different places depending on which backpack slot is hovered (right of, over, or below the slot), so its position cannot be fixed. Blueprints and schematics both show as "SCHEMATIC - UNIQUE". Tooltips carry no price.
- All screens show the player's character name and Solari balance in the corners. The program must not read or upload those. An FPS counter appears in the top-left corner (from the owner's own tool).

Grades: the owner confirmed that the same item can exist in different grades with different prices (the Buy tab has a "GRADE" filter). Decision: every stored price has a grade field. If the Buy tab was scanned with "GRADE: ALL", the grade is stored as "unknown". If it was scanned with a specific grade, that grade is stored. The popup shows the grade when known and marks it "grade unknown" otherwise. How the Sell tab and the hover tooltip expose the grade is not yet known; the builder should check this early and the owner wants to experiment with it. The owner is open to a better idea.

## Open risks

- OCR accuracy on the game UI at different resolutions and UI scales.
- The data only exists for items a member has recently looked at in the Exchange; coverage grows with use.
- Funcom permission is not confirmed.
- Names shown in the popup identify friends; that is acceptable inside the group, since the owner chose to show the contributor.

Tooltip finding (Task 5): the three hover screenshots show no grade marker in the tooltip (the only "Grade" text is the crafting component "Schematic Pattern Grade 1"). Until a grade source is found, the hover popup shows every known grade of the item.

## Findings from the owner's first real-game run (2026-10-19)

- The first `scan` run kept OCR-ing continuously at about 95% CPU, competing with the game (OCR with default thread count took about 5 s per frame instead of about 1.2 s). The overlay lookups were so slow that the cursor had left before the popup appeared. Fixes: OCR limited to 6 threads; scanner and hover lookups do nothing unless the game window is in front; the list is only OCR'd when the Exchange tab bar is visible; the scan reads only the list area (never the screen corners).
- Grades: the tooltip header shows the grade as a number at its right end; no number means grade 0. The Buy tab's `GRADE:` filter label is stored with each listing (grades 0-5 seen). On the Sell tab only the selected row's grade is visible, in the detail panel title.
- The OCR drops spaces unpredictably ("Robeofthe Sisterhood"), so items are matched by a spelling-independent key (lowercase letters and digits only).
