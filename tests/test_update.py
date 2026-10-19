"""The "new version available" notice: version comparison, asking the shared database, notice text."""

import subprocess
import sys

import httpx
import pytest

import dune_market
from dune_market.update import UpdateInfo, check_for_update, is_newer, parse_version, update_toast_lines

URL = "https://example.supabase.co"


def client_for(rows, status=200, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if status != 200:
            return httpx.Response(status, json={"message": "nope"})
        return httpx.Response(200, json=rows)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parse_version():
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("v1.2") == (1, 2, 0)
    assert parse_version(" 2 ") == (2, 0, 0)


@pytest.mark.parametrize("text", ["", "abc", "1.x", "1.2.3.4", "-1"])
def test_parse_version_rejects_nonsense(text):
    with pytest.raises(ValueError):
        parse_version(text)


def test_is_newer_compares_numbers_not_text():
    assert is_newer("1.10.0", "1.9.0") is True
    assert is_newer("1.1.1", "1.1.0") is True
    assert is_newer("1.1.0", "1.1.0") is False
    assert is_newer("1.0.9", "1.1.0") is False


def test_a_newer_release_is_reported_with_its_download_link_and_notes():
    rows = [{"version": "1.2.0", "download_url": "https://drive.example/zip", "notes": "Armor fix"}]
    info = check_for_update(URL, "key", "1.1.0", client=client_for(rows))
    assert info == UpdateInfo("1.2.0", "https://drive.example/zip", "Armor fix")


def test_nothing_is_reported_when_up_to_date_or_ahead_or_empty():
    row = [{"version": "1.1.0", "download_url": "u", "notes": ""}]
    assert check_for_update(URL, "key", "1.1.0", client=client_for(row)) is None
    assert check_for_update(URL, "key", "1.2.0", client=client_for(row)) is None
    assert check_for_update(URL, "key", "1.1.0", client=client_for([])) is None


def test_failures_and_garbage_never_raise():
    assert check_for_update(URL, "key", "1.1.0", client=client_for([], status=401)) is None
    assert check_for_update(URL, "key", "1.1.0", client=client_for([{"version": "banana"}])) is None
    assert check_for_update(URL, "key", "1.1.0", client=client_for([{"nothing": 1}])) is None

    def down(request):
        raise httpx.ConnectError("offline")

    assert check_for_update(URL, "key", "1.1.0", client=httpx.Client(transport=httpx.MockTransport(down))) is None


def test_request_asks_for_the_newest_release_with_the_shared_key():
    seen = []
    check_for_update(URL, "friend-key", "1.1.0", client=client_for([], seen=seen))
    request = seen[0]
    assert request.url.path == "/rest/v1/releases"
    assert request.url.params["order"] == "created_at.desc" and request.url.params["limit"] == "1"
    assert request.headers["apikey"] == "friend-key" and request.headers["authorization"] == "Bearer friend-key"


def test_toast_lines_say_what_is_new_and_where_to_get_it():
    lines = update_toast_lines(UpdateInfo("1.2.0", "https://drive.example/zip", "Armor fix"), "1.1.0")
    assert lines[0] == "Dune Market · update available"
    assert "1.2.0" in lines[1] and "1.1.0" in lines[1]
    assert "Armor fix" in lines
    assert any("https://drive.example/zip" in line for line in lines)


def test_toast_lines_without_notes():
    lines = update_toast_lines(UpdateInfo("1.2.0", "https://x.example", ""), "1.1.0")
    assert "" not in lines


def test_the_program_has_a_version_and_prints_it():
    parse_version(dune_market.__version__)
    result = subprocess.run([sys.executable, "-m", "dune_market", "--version"], capture_output=True, text=True, timeout=60)
    assert dune_market.__version__ in result.stdout
