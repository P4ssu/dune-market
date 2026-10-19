"""Updates: find a newer release on GitHub, download and check it, install it at the next start.

Release process (see docs/releasing.md): pushing a version tag makes GitHub build `DuneMarket-update.zip`
(the program without any settings) and publish it with a `.sha256` file. A running program checks the
newest release now and then. If it is newer, the zip is downloaded in the background, its checksum is
verified, and it is unpacked next to the program. The next time the program starts it hands over to a
small script that waits until the old program has closed, copies the new files over the old ones (never
touching `config.toml` or `prices.db`) and starts the program again.
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

REPO = "P4ssu/dune-market"
API = "https://api.github.com"
ZIP_NAME = "DuneMarket-update.zip"
SHA_NAME = ZIP_NAME + ".sha256"
CHECK_EVERY_S = 6 * 3600
FIRST_CHECK_AFTER_S = 20  # let the game and the other startup notices settle first
_PENDING = "pending.json"
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_MAX_NOTES = 200


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    notes: str
    page_url: str
    zip_url: str  # "" when the release has no (trusted) update file: the user is only told about it
    sha256_url: str


def parse_version(text: str) -> tuple[int, int, int]:
    """"1.2.3", "v1.2" or "2" -> (1, 2, 3), (1, 2, 0), (2, 0, 0). Raises ValueError for anything else."""
    parts = text.strip().lower().removeprefix("v").split(".")
    if not 1 <= len(parts) <= 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"not a version number: {text!r}")
    numbers = [int(part) for part in parts] + [0] * (3 - len(parts))
    return numbers[0], numbers[1], numbers[2]


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)


def install_dir() -> Path | None:
    """Where the packaged program lives; None when running from source (then nothing is self-updated)."""
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else None


# --- finding a newer release -------------------------------------------------------------------


def check_for_update(current: str, repo: str = REPO, client: httpx.Client | None = None, api: str = API) -> UpdateInfo | None:
    """The newest release if it is newer than `current`; None otherwise (also on any error)."""
    try:
        response = (client or httpx.Client(timeout=20)).get(
            f"{api}/repos/{repo}/releases/latest",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "DuneMarket-updater"},
        )
        response.raise_for_status()
        data = response.json()
        version = str(data["tag_name"]).strip().removeprefix("v")
        if not is_newer(version, current):
            return None
        trusted = f"https://github.com/{repo}/releases/download/"
        files = {a["name"]: a["browser_download_url"] for a in data.get("assets", []) if str(a.get("browser_download_url", "")).startswith(trusted)}
        notes = next((line.strip() for line in str(data.get("body") or "").splitlines() if line.strip()), "")[:_MAX_NOTES]
        return UpdateInfo(version, notes, str(data.get("html_url") or ""), files.get(ZIP_NAME, ""), files.get(SHA_NAME, ""))
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        log.debug("update check failed", exc_info=True)
        return None


# --- downloading and staging -------------------------------------------------------------------


def _extract(archive: zipfile.ZipFile, target: Path) -> None:
    root = target.resolve()
    for member in archive.infolist():
        destination = (root / member.filename).resolve()
        if root != destination and root not in destination.parents:
            raise ValueError(f"unsafe path in the update: {member.filename!r}")
    archive.extractall(root)


def stage_update(info: UpdateInfo, home: Path, client: httpx.Client | None = None) -> Path | None:
    """Download, verify and unpack the update into `home/updates/<version>/app`; the folder, or None."""
    if not info.zip_url or not info.sha256_url:
        return None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    version_dir = home / "updates" / info.version
    try:
        shutil.rmtree(version_dir, ignore_errors=True)
        version_dir.mkdir(parents=True)
        zip_path = version_dir / ZIP_NAME
        digest = hashlib.sha256()
        with client.stream("GET", info.zip_url, follow_redirects=True) as response, open(zip_path, "wb") as out:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                digest.update(chunk)
                out.write(chunk)
        expected = client.get(info.sha256_url, follow_redirects=True)
        expected.raise_for_status()
        if digest.hexdigest() != expected.text.split()[0].strip().lower():
            raise ValueError("checksum does not match")
        app = version_dir / "app"
        with zipfile.ZipFile(zip_path) as archive:
            _extract(archive, app)
        if not (app / "DuneMarket.exe").is_file():
            raise ValueError("the update does not contain DuneMarket.exe")
        zip_path.unlink()
        (home / "updates" / _PENDING).write_text(json.dumps({"version": info.version, "path": str(app)}), encoding="utf-8")
        for old in (home / "updates").iterdir():  # drop older staged versions
            if old.is_dir() and old != version_dir:
                shutil.rmtree(old, ignore_errors=True)
        return app
    except (httpx.HTTPError, zipfile.BadZipFile, OSError, ValueError, IndexError):
        log.warning("could not prepare the update", exc_info=True)
        shutil.rmtree(version_dir, ignore_errors=True)
        return None


def read_pending(home: Path) -> tuple[str, Path] | None:
    """(version, folder) of an update that is downloaded and waiting to be installed."""
    try:
        record = json.loads((home / "updates" / _PENDING).read_text(encoding="utf-8"))
        path = Path(record["path"])
        parse_version(record["version"])
        return (record["version"], path) if (path / "DuneMarket.exe").is_file() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


# --- installing at the next start ------------------------------------------------------------


def build_apply_script(home: Path, staged: Path, pid: int, relaunch: str | None = None, wait_s: int = 2) -> str:
    """A batch file that waits for the program to close, copies the new files over it and starts it again."""
    relaunch = relaunch or f'start "" "{home}\\DuneMarket.exe"'
    sleep = f"ping -n {wait_s + 1} 127.0.0.1 >nul"  # `timeout` does not work without a console
    return f"""@echo off
setlocal EnableExtensions
set "HOME_DIR={home}"
set "STAGED={staged}"
set "LOG=%HOME_DIR%\\updates\\apply.log"
echo %date% %time% started, waiting for process {pid} to exit > "%LOG%"
set /a waits=0
:waitexit
tasklist /fi "PID eq {pid}" /nh 2>nul | find "{pid}" >nul
if errorlevel 1 goto copy
set /a waits+=1
if %waits% gtr 60 goto failed
{sleep}
goto waitexit
:copy
echo %date% %time% program closed, copying files >> "%LOG%"
set /a tries=0
:retry
robocopy "%STAGED%" "%HOME_DIR%" /E /XF config.toml prices.db /XD updates /R:3 /W:1 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto retrywait
goto done
:retrywait
set /a tries+=1
if %tries% geq 5 goto failed
{sleep}
goto retry
:done
echo %date% %time% copied, starting the new version >> "%LOG%"
del /q "%HOME_DIR%\\updates\\{_PENDING}" 2>nul
rd /s /q "%STAGED%" 2>nul
rd "{staged.parent}" 2>nul
{relaunch}
exit /b 0
:failed
echo %date% %time% FAILED, starting the old version >> "%LOG%"
del /q "%HOME_DIR%\\updates\\{_PENDING}" 2>nul
{relaunch}
exit /b 1
"""


def apply_pending_update(home: Path, current: str, spawn: Callable = subprocess.Popen) -> bool:
    """If a newer update is waiting, start the installer script and return True: the program must exit now."""
    pending = read_pending(home)
    if pending is None:
        return False
    version, staged = pending
    if not is_newer(version, current):  # already installed: tidy up
        (home / "updates" / _PENDING).unlink(missing_ok=True)
        shutil.rmtree(staged.parent, ignore_errors=True)
        return False
    script = home / "updates" / "apply.bat"
    script.write_text(build_apply_script(home, staged, os.getpid()), encoding="utf-8")
    # A hidden console (a batch file needs one) in its own process group, outside the parent's job if allowed,
    # so the script keeps running after this program exits.
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    command = ["cmd", "/c", str(script)]
    try:
        spawn(command, creationflags=flags | _CREATE_BREAKAWAY_FROM_JOB, close_fds=True)
    except OSError:  # the job does not allow breaking away
        spawn(command, creationflags=flags, close_fds=True)
    return True


# --- the notice and the background check ---------------------------------------------------


def update_toast_lines(info: UpdateInfo, current: str, downloaded: bool) -> list[str]:
    """The in-game notice for a new version."""
    if downloaded:
        lines = ["Dune Market · update ready", f"Version {info.version} is downloaded (you have {current})"]
        if info.notes:
            lines.append(info.notes)
        lines.append("It installs automatically the next time you start Dune Market.")
        return lines
    lines = ["Dune Market · update available", f"Version {info.version} is out (you have {current})"]
    if info.notes:
        lines.append(info.notes)
    if info.page_url:
        lines.append(f"Get it here: {info.page_url}")
    return lines


def start_update_checks(
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
            info = check_for_update(current)
            if info:
                on_update(info)
            wait = every_s

    thread = threading.Thread(target=loop, daemon=True, name="update-check")
    thread.start()
    return thread
