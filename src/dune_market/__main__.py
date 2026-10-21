"""Command line entry: `python -m dune_market run` (scanner and price popups together)."""

import argparse
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone

from dune_market import __version__
from dune_market.capture import game_is_active
from dune_market.config import load_config
from dune_market.scanner import Scanner
from dune_market.update import apply_pending_update, install_dir
from dune_market.store_sqlite import SqliteStore


def _scan(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    scanner = Scanner(SqliteStore(args.db), config.contributor, active=game_is_active)
    print("Scanning the Exchange screen. Press Ctrl+C to stop.")
    try:
        while True:
            stored = scanner.scan_once(datetime.now(timezone.utc))
            if stored:
                print(f"Read {stored} rows, {scanner.last_new} new items. Items this session: {scanner.session_total}")
            time.sleep(scanner.idle_delay)
    except KeyboardInterrupt:
        pass


def _overlay(args: argparse.Namespace) -> None:
    from dune_market.overlay import run_overlay

    run_overlay(SqliteStore(args.db), debug=args.debug, solid=args.solid)


def _run(args: argparse.Namespace) -> None:
    from dune_market.overlay import run_overlay

    config = load_config(args.config)
    run_overlay(SqliteStore(args.db), debug=args.debug, solid=args.solid, contributor=config.contributor, remote=config.remote,
                search_hotkey=config.search_hotkey, auto_update=config.auto_update,
                log_path=args.log_path)


def _selftest(args: argparse.Namespace) -> None:
    """Check that the OCR engine, screen capture and the window toolkit all load (used on the packaged .exe)."""
    import mss  # noqa: F401
    import httpx  # noqa: F401
    from PIL import Image, ImageDraw
    from PyQt6.QtWidgets import QApplication  # noqa: F401

    from dune_market.ocr import read_words

    image = Image.new("RGB", (300, 80), "black")
    ImageDraw.Draw(image).text((10, 25), "MY ORDERS", fill="white")
    words = read_words(image.resize((900, 240)))
    print(f"Self-test OK (OCR engine ran, {len(words)} text spans found)")


LOG_NAME = "dune-market.log"


def _setup_logging(home: Path) -> None:
    """Log to the console and to dune-market.log next to the program (kept small), for bug reports."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(RotatingFileHandler(home / LOG_NAME, maxBytes=1_000_000, backupCount=1, encoding="utf-8"))
    except OSError:
        pass  # a read-only folder: console only
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)


def main() -> None:
    parser = argparse.ArgumentParser(prog="dune_market")
    # Next to the program for the packaged .exe, the current folder otherwise.
    home = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    _setup_logging(home)
    parser.add_argument("--config", default=str(home / "config.toml"))
    parser.add_argument("--db", default=str(home / "prices.db"))
    parser.add_argument("--version", action="version", version=f"Dune Market {__version__}")
    parser.set_defaults(debug=False, solid=False)
    sub = parser.add_subparsers(dest="command")  # no command (double-clicking the .exe) means "run"

    sub.add_parser("selftest", help="check that everything the program needs loads")
    sub.add_parser("scan", help="only read Sell/Buy tabs from the screen into the price database")
    for name, help_text in (
        ("overlay", "only show the price popup when hovering inventory items"),
        ("run", "scan the Exchange and show price popups and in-game notices (use this one)"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--debug", action="store_true", help="log every lookup and save the screen it found nothing on")
        command.add_argument("--solid", action="store_true", help="use opaque windows (if the popup is not visible over the game)")

    args = parser.parse_args()
    args.log_path = home / LOG_NAME
    command = args.command or "run"
    home = install_dir()
    if home and command in ("run", "overlay") and apply_pending_update(home, __version__):
        return  # a downloaded update is being installed; the program restarts by itself
    try:
        {"scan": _scan, "overlay": _overlay, "run": _run, "selftest": _selftest}[command](args)
    except Exception as error:
        if not getattr(sys, "frozen", False):
            raise
        # A double-clicked .exe closes its window at once; keep the message readable.
        print(f"\nERROR: {error}")
        input("Press Enter to close this window.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
