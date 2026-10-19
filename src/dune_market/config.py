"""Read `config.toml`."""

import tomllib
from dataclasses import dataclass

from dune_market.hotkey import parse_hotkey


PLACEHOLDER_NAME = "KIRJUTA-SIIA-OMA-NIMI"  # what the friends' config template holds until they type their name


@dataclass(frozen=True)
class RemoteConfig:
    url: str
    key: str
    world: str = "Andromeda"  # prices differ per World, so only rows of this World are shared


@dataclass(frozen=True)
class Config:
    contributor: str
    remote: RemoteConfig | None = None
    search_hotkey: str = "ctrl+shift+f"  # opens and closes the item search


def load_config(path: str) -> Config:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    contributor = data.get("contributor")
    if not contributor or contributor == PLACEHOLDER_NAME:
        raise ValueError("config.toml: write your own name on the `contributor = ...` line")
    remote = data.get("remote")
    hotkey = data.get("search_hotkey", "ctrl+shift+f")
    parse_hotkey(hotkey)  # fail now, with a clear message, rather than when the program is running
    return Config(
        contributor,
        RemoteConfig(remote["url"], remote["key"], remote.get("world", "Andromeda")) if remote else None,
        hotkey,
    )
