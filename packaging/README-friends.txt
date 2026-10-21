DUNE MARKET - live Exchange prices for Dune: Awakening
=======================================================

WHAT IT IS
A small free tool that shows Exchange (market) prices right in the game:
  * Hover an item or blueprint in your inventory -> a popup shows the lowest price of the
    last scan, the average price, the price trend and how fresh the data is,
    for that item's grade.
  * Press Ctrl+Shift+F -> a search box opens. Type an item name and see its prices
    and when the cheapest listing expires. Add a colon and a grade for one grade only,
    for example  cobalt paste:5
  * A gold "D" icon sits in the tray (bottom right of the taskbar). Right-click it to search,
    pause the popups or the scanning, open the log file (dune-market.log) or quit.
  * Whenever you open the Exchange (Buy / Sell tab), the tool reads the prices on your screen and
    shares them with everyone using the tool. The more people browse the market, the better the data.

INSTALL (once)
1. Unzip the whole folder to a short location such as your Desktop (very long folder paths can fail).
   Do not run anything from inside the zip.
2. In the game: Settings -> Graphics -> Display Mode = "Windowed Fullscreen" (borderless).
   In exclusive fullscreen the popup cannot be drawn over the game.
3. Open the unzipped folder and double-click  Install.bat
   - Windows may say "Windows protected your PC" (the program is not signed).
     Click "More info", then "Run anyway".
   - Type your in-game name when asked (friends see it next to the prices you scan).
4. A "Dune Market" shortcut appears on your desktop.

USE
1. Start the game, then double-click "Dune Market" on your desktop. A black window stays open
   (do not close it) and a notice "Dune Market - Running" appears over the game.
2. Collect prices: open the Exchange. On the Sell tab the game shows prices for the items in your
   backpack; on the Buy tab scroll through the categories. A notice at the top of the screen shows
   how many rows were read and how many were new.
3. See prices: hover an item in your inventory, or press Ctrl+Shift+F and type a name.
   Esc closes the search.
4. To stop: close the black window.

GETTING GOOD PRICES (tips for scanning the Buy tab)
* Sort by NAME: click the NAME column in the Buy tab. All listings of the same item then sit next to
  each other, so while you scroll the tool sees every listing of an item and finds its cheapest price
  reliably. (With the default order the listings of one item are spread out and the cheapest can be missed.)
* Scan between grades: prices differ by grade. Switch the GRADE filter (bottom left of the Buy tab) and
  scroll each grade you care about. That is how the tool learns grade-specific prices, so the popup shows
  the right price for the exact grade of your item. With GRADE: ALL nothing is saved (the rows mix
  grades); a notice in the game reminds you to choose a grade.
* Scroll steadily; the tool reads the list every second or two and the notice at the top of the screen
  tells you how many new items it found.

SETTINGS
Edit  %LOCALAPPDATA%\DuneMarket\config.toml  with Notepad (press Win+R, paste the path, press Enter):
  contributor    your name
  search_hotkey  the search key, for example "F8" or "ctrl+shift+f"

TROUBLESHOOTING
* The popup does not appear over the game: run "start-solid.bat" from %LOCALAPPDATA%\DuneMarket
  (it uses a plain window), and make sure the game is in Windowed Fullscreen.
* Nothing is found in the search: prices exist only for items someone has already browsed in the Exchange.
* The search hotkey does nothing: another program uses that key. Change search_hotkey in config.toml.
* Updating: new versions download by themselves in the background and install the next time you start
  Dune Market (a notice appears in the game). Your settings and saved prices are kept.
  To turn this off, add the line  auto_update = false  to config.toml; you are then only told about new versions.
* Remove: run Uninstall.bat.

PRIVACY AND IMPORTANT NOTES
* The tool only looks at the screen while Dune: Awakening is the active window. It does not read the
  game's memory or files, does not touch its network traffic and does not send any input to the game.
* The shared database only receives item names, prices and the name you chose.
  No screenshots are saved or sent.
* This is an UNOFFICIAL community tool. It is not made or endorsed by Funcom, and Funcom has not
  confirmed that screen-reading tools like it are allowed. Use it at your own risk.
* Prices are per World. This version shares prices of the World Andromeda only.
