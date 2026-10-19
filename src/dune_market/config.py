"""Read `config.toml`."""

import tomllib
from dataclasses import dataclass


@dataclass(frozen=True)
class RemoteConfig:
    url: str
    key: str


@dataclass(frozen=True)
class Config:
    contributor: str
    remote: RemoteConfig | None = None


def load_config(path: str) -> Config:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    contributor = data.get("contributor")
    if not contributor:
        raise ValueError("config.toml needs a non-empty `contributor` name")
    remote = data.get("remote")
    return Config(contributor, RemoteConfig(remote["url"], remote["key"]) if remote else None)
