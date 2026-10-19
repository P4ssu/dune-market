import pytest

from dune_market.config import load_config


def test_load_config_reads_contributor(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('contributor = "Mari"\n', encoding="utf-8")
    config = load_config(str(path))
    assert config.contributor == "Mari"
    assert config.remote is None


def test_load_config_reads_remote_table(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('contributor = "Mari"\n[remote]\nurl = "https://x.example"\nkey = "k"\n', encoding="utf-8")
    config = load_config(str(path))
    assert (config.remote.url, config.remote.key) == ("https://x.example", "k")


def test_load_config_requires_contributor(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="contributor"):
        load_config(str(path))
