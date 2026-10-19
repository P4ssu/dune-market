"""Read `config.toml`."""

import tomllib
from dataclasses import dataclass


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


def load_config(path: str) -> Config:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    contributor = data.get("contributor")
    if not contributor or contributor == PLACEHOLDER_NAME:
        raise ValueError("config.toml: write your own name on the `contributor = ...` line")
    remote = data.get("remote")
    return Config(contributor, RemoteConfig(remote["url"], remote["key"], remote.get("world", "Andromeda")) if remote else None)
