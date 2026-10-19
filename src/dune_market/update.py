"""Tells the user when a newer version of the program has been published.

The owner adds a row to the shared database's `releases` table (version, download link, notes); every
running copy asks for the newest row now and then and shows a notice when it is newer than itself.
Nothing is downloaded or installed automatically.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

CHECK_EVERY_S = 6 * 3600
FIRST_CHECK_AFTER_S = 20  # let the game and the other startup notices settle first


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    url: str
    notes: str


def parse_version(text: str) -> tuple[int, int, int]:
    """"1.2.3", "v1.2" or "2" -> (1, 2, 3), (1, 2, 0), (2, 0, 0). Raises ValueError for anything else."""
    parts = text.strip().lower().removeprefix("v").split(".")
    if not 1 <= len(parts) <= 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"not a version number: {text!r}")
    numbers = [int(part) for part in parts] + [0] * (3 - len(parts))
    return numbers[0], numbers[1], numbers[2]


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def check_for_update(url: str, key: str, current: str, client: httpx.Client | None = None) -> UpdateInfo | None:
    """The newest published release if it is newer than `current`; None otherwise (also on any error)."""
    try:
        response = (client or httpx.Client(timeout=15)).get(
            url.rstrip("/") + "/rest/v1/releases",
            params={"order": "created_at.desc", "limit": "1"},
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return None
        row = rows[0]
        if not is_newer(row["version"], current):
            return None
        return UpdateInfo(row["version"].strip(), str(row.get("download_url") or ""), str(row.get("notes") or "").strip())
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        log.debug("update check failed", exc_info=True)
        return None


def update_toast_lines(info: UpdateInfo, current: str) -> list[str]:
    """The in-game notice for a new version."""
    lines = ["Dune Market · update available", f"Version {info.version} is out (you have {current})"]
    if info.notes:
        lines.append(info.notes)
    if info.url:
        lines.append(f"Download: {info.url}")
    return lines


def start_update_checks(
    url: str,
    key: str,
    current: str,
    on_update: Callable[[UpdateInfo], None],
    first_after_s: float = FIRST_CHECK_AFTER_S,
    every_s: float = CHECK_EVERY_S,
    stop: threading.Event | None = None,
) -> threading.Thread:
    """Check shortly after start and then every few hours, in the background."""
    stop = stop or threading.Event()

    def loop() -> None:
        wait = first_after_s
        while not stop.wait(wait):
            info = check_for_update(url, key, current)
            if info:
                on_update(info)
            wait = every_s

    thread = threading.Thread(target=loop, daemon=True, name="update-check")
    thread.start()
    return thread
