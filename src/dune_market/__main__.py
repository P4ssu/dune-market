"""Command line entry: `python -m dune_market scan` and `python -m dune_market overlay`."""

import argparse
import logging
import time
from datetime import datetime, timezone

from dune_market.capture import game_is_active
from dune_market.config import load_config
from dune_market.scanner import Scanner
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
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass


def _overlay(args: argparse.Namespace) -> None:
    from dune_market.overlay import run_overlay

    run_overlay(SqliteStore(args.db), debug=args.debug)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(prog="dune_market")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--db", default="prices.db")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan", help="read Sell/Buy tabs from the screen into the price database")
    overlay = sub.add_parser("overlay", help="show the price popup when hovering inventory items")
    overlay.add_argument("--debug", action="store_true", help="log every lookup and save the screen it found nothing on")
    args = parser.parse_args()
    if args.command == "scan":
        _scan(args)
    else:
        _overlay(args)


if __name__ == "__main__":
    main()
