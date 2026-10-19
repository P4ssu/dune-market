"""Self-update: finding a newer GitHub release, downloading and checking it, installing it at the next start."""

import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import httpx
import pytest

import dune_market
from dune_market.update import (
    UpdateInfo,
    apply_pending_update,
    build_apply_script,
    check_for_update,
    is_newer,
    parse_version,
    read_pending,
    stage_update,
    update_toast_lines,
)

REPO = "P4ssu/dune-market"
BASE = f"https://github.com/{REPO}/releases/download/v1.2.0"


# --- version numbers ---------------------------------------------------------------------------


def test_parse_version():
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("v1.2") == (1, 2, 0)
    assert parse_version(" 2 ") == (2, 0, 0)


@pytest.mark.parametrize("text", ["", "abc", "1.x", "1.2.3.4", "-1"])
def test_parse_version_rejects_nonsense(text):
    with pytest.raises(ValueError):
        parse_version(text)


def test_is_newer_compares_numbers_not_text():
    assert is_newer("1.10.0", "1.9.0") and is_newer("1.1.1", "1.1.0")
    assert not is_newer("1.1.0", "1.1.0") and not is_newer("1.0.9", "1.1.0")


# --- asking GitHub -----------------------------------------------------------------------------


def release_json(tag="v1.2.0", body="Armor fix", zip_url=f"{BASE}/DuneMarket-update.zip", sha_url=f"{BASE}/DuneMarket-update.zip.sha256"):
    assets = []
    if zip_url:
        assets.append({"name": "DuneMarket-update.zip", "browser_download_url": zip_url})
    if sha_url:
        assets.append({"name": "DuneMarket-update.zip.sha256", "browser_download_url": sha_url})
    return {"tag_name": tag, "body": body, "html_url": f"https://github.com/{REPO}/releases/tag/{tag}", "assets": assets}


def github(payload, status=200, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_newer_release_is_reported_with_its_files_and_notes():
    info = check_for_update("1.1.0", client=github(release_json()))
    assert info == UpdateInfo("1.2.0", "Armor fix", f"https://github.com/{REPO}/releases/tag/v1.2.0",
                              f"{BASE}/DuneMarket-update.zip", f"{BASE}/DuneMarket-update.zip.sha256")


def test_request_goes_to_the_latest_release_of_the_repository():
    seen = []
    check_for_update("1.1.0", client=github(release_json(), seen=seen))
    assert seen[0].url.path == f"/repos/{REPO}/releases/latest"
    assert "application/vnd.github" in seen[0].headers["accept"] and seen[0].headers["user-agent"]


def test_nothing_is_reported_when_up_to_date_ahead_or_nothing_published():
    assert check_for_update("1.2.0", client=github(release_json())) is None
    assert check_for_update("1.3.0", client=github(release_json())) is None
    assert check_for_update("1.1.0", client=github({"message": "Not Found"}, status=404)) is None


def test_failures_and_garbage_never_raise():
    assert check_for_update("1.1.0", client=github({"tag_name": "banana"})) is None
    assert check_for_update("1.1.0", client=github(["not", "an", "object"])) is None
    assert check_for_update("1.1.0", client=github({}, status=403)) is None

    def offline(request):
        raise httpx.ConnectError("offline")

    assert check_for_update("1.1.0", client=httpx.Client(transport=httpx.MockTransport(offline))) is None


def test_files_from_somewhere_else_are_never_trusted():
    info = check_for_update("1.1.0", client=github(release_json(zip_url="https://evil.example/DuneMarket-update.zip")))
    assert info is not None and info.zip_url == ""  # notice only, nothing will be downloaded


def test_a_release_without_the_update_files_is_notice_only():
    info = check_for_update("1.1.0", client=github(release_json(zip_url="", sha_url="")))
    assert info is not None and info.zip_url == "" and info.sha256_url == ""


def test_long_release_notes_are_shortened_to_one_line():
    info = check_for_update("1.1.0", client=github(release_json(body="First line\n\nSecond paragraph " + "x" * 500)))
    assert info.notes == "First line"


# --- downloading and staging -------------------------------------------------------------------


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


GOOD_FILES = {"DuneMarket.exe": b"new exe", "_internal/lib.dll": b"new lib", "start-solid.bat": b"@echo off"}


def download_server(zip_bytes, sha=None, fail=False):
    sha = hashlib.sha256(zip_bytes).hexdigest() if sha is None else sha

    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("down")
        if request.url.path.endswith(".zip"):
            return httpx.Response(200, content=zip_bytes)
        if request.url.path.endswith(".sha256"):
            return httpx.Response(200, text=f"{sha}  DuneMarket-update.zip\n")
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


INFO = UpdateInfo("1.2.0", "Armor fix", "page", f"{BASE}/DuneMarket-update.zip", f"{BASE}/DuneMarket-update.zip.sha256")


def test_a_good_download_is_staged_and_recorded(tmp_path):
    staged = stage_update(INFO, tmp_path, client=download_server(make_zip(GOOD_FILES)))
    assert staged is not None and (staged / "DuneMarket.exe").read_bytes() == b"new exe"
    assert (staged / "_internal" / "lib.dll").exists()
    assert read_pending(tmp_path) == ("1.2.0", staged)
    assert not list((tmp_path / "updates").glob("**/*.zip"))  # the zip itself is removed again


def test_a_download_with_the_wrong_checksum_is_refused(tmp_path):
    assert stage_update(INFO, tmp_path, client=download_server(make_zip(GOOD_FILES), sha="0" * 64)) is None
    assert read_pending(tmp_path) is None


def test_a_download_without_a_checksum_is_refused(tmp_path):
    no_sha = UpdateInfo("1.2.0", "", "page", INFO.zip_url, "")
    assert stage_update(no_sha, tmp_path, client=download_server(make_zip(GOOD_FILES))) is None


def test_files_that_would_escape_the_folder_are_refused(tmp_path):
    evil = make_zip({**GOOD_FILES, "../../evil.txt": b"x"})
    assert stage_update(INFO, tmp_path, client=download_server(evil)) is None
    assert not (tmp_path.parent / "evil.txt").exists() and read_pending(tmp_path) is None


def test_an_update_without_the_program_in_it_is_refused(tmp_path):
    assert stage_update(INFO, tmp_path, client=download_server(make_zip({"readme.txt": b"hi"}))) is None


def test_a_broken_zip_or_network_is_refused_quietly(tmp_path):
    assert stage_update(INFO, tmp_path, client=download_server(b"this is not a zip")) is None
    assert stage_update(INFO, tmp_path, client=download_server(b"", fail=True)) is None
    assert read_pending(tmp_path) is None


def test_read_pending_ignores_a_record_whose_files_are_gone(tmp_path):
    staged = stage_update(INFO, tmp_path, client=download_server(make_zip(GOOD_FILES)))
    (staged / "DuneMarket.exe").unlink()
    assert read_pending(tmp_path) is None


# --- installing at the next start ------------------------------------------------------------


def make_install(home: Path):
    (home / "_internal").mkdir(parents=True)
    (home / "DuneMarket.exe").write_bytes(b"old exe")
    (home / "_internal" / "lib.dll").write_bytes(b"old lib")
    (home / "_internal" / "old_only.dll").write_bytes(b"old only")
    (home / "config.toml").write_text('contributor = "Mari"\n', encoding="utf-8")
    (home / "prices.db").write_bytes(b"my prices")


def test_apply_script_really_replaces_the_program_and_keeps_settings_and_prices(tmp_path):
    home = tmp_path / "install"
    make_install(home)
    staged = stage_update(INFO, home, client=download_server(make_zip(GOOD_FILES)))
    marker = tmp_path / "relaunched.txt"
    script = build_apply_script(home, staged, pid=99999999, relaunch=f'echo relaunched> "{marker}"')
    script_path = tmp_path / "apply.bat"
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(["cmd", "/c", str(script_path)], capture_output=True, text=True, timeout=120)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (home / "DuneMarket.exe").read_bytes() == b"new exe"
    assert (home / "_internal" / "lib.dll").read_bytes() == b"new lib"
    assert (home / "config.toml").read_text(encoding="utf-8") == 'contributor = "Mari"\n'  # settings kept
    assert (home / "prices.db").read_bytes() == b"my prices"  # saved prices kept
    assert read_pending(home) is None and not staged.exists()  # cleaned up
    assert marker.exists()  # and the program was started again


def test_apply_script_starts_the_old_program_if_copying_fails(tmp_path):
    home = tmp_path / "install"
    make_install(home)
    marker = tmp_path / "relaunched.txt"
    script = build_apply_script(home, tmp_path / "does-not-exist", pid=99999999, relaunch=f'echo relaunched> "{marker}"', wait_s=0)
    script_path = tmp_path / "apply.bat"
    script_path.write_text(script, encoding="utf-8")
    subprocess.run(["cmd", "/c", str(script_path)], capture_output=True, text=True, timeout=120)
    assert (home / "DuneMarket.exe").read_bytes() == b"old exe" and marker.exists()


def test_apply_pending_update_starts_the_script_and_asks_the_program_to_exit(tmp_path):
    staged = stage_update(INFO, tmp_path, client=download_server(make_zip(GOOD_FILES)))
    started = []
    assert apply_pending_update(tmp_path, "1.1.0", spawn=lambda *a, **k: started.append((a, k))) is True
    assert len(started) == 1 and (tmp_path / "updates" / "apply.bat").exists()
    assert staged.exists()  # the script, not Python, moves the files


def test_apply_pending_update_does_nothing_for_an_old_or_missing_update(tmp_path):
    assert apply_pending_update(tmp_path, "1.1.0", spawn=lambda *a, **k: pytest.fail("must not start")) is False
    stage_update(INFO, tmp_path, client=download_server(make_zip(GOOD_FILES)))
    assert apply_pending_update(tmp_path, "1.2.0", spawn=lambda *a, **k: pytest.fail("already up to date")) is False
    assert read_pending(tmp_path) is None  # the leftover record was cleaned up


# --- the notice ---------------------------------------------------------------------------------


def test_toast_for_a_downloaded_update_says_it_installs_next_start():
    lines = update_toast_lines(INFO, "1.1.0", downloaded=True)
    assert lines[0] == "Dune Market · update ready"
    assert "1.2.0" in lines[1] and "next time" in " ".join(lines).lower() and "Armor fix" in lines


def test_toast_when_the_update_could_not_be_downloaded_gives_the_link():
    lines = update_toast_lines(INFO, "1.1.0", downloaded=False)
    assert lines[0] == "Dune Market · update available" and any("page" in line for line in lines)


def test_the_program_has_a_version_and_prints_it():
    parse_version(dune_market.__version__)
    result = subprocess.run([sys.executable, "-m", "dune_market", "--version"], capture_output=True, text=True, timeout=60)
    assert dune_market.__version__ in result.stdout
