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


def test_remote_world_defaults_to_andromeda_and_can_be_set(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('contributor = "Mari"\n[remote]\nurl = "https://x.example"\nkey = "k"\n', encoding="utf-8")
    assert load_config(str(path)).remote.world == "Andromeda"
    path.write_text('contributor = "Mari"\n[remote]\nurl = "https://x.example"\nkey = "k"\nworld = "Orion"\n', encoding="utf-8")
    assert load_config(str(path)).remote.world == "Orion"


def test_selftest_command_runs(capsys):
    import argparse

    from dune_market.__main__ import _selftest

    _selftest(argparse.Namespace())
    assert "Self-test OK" in capsys.readouterr().out


def test_placeholder_name_from_the_friends_template_is_rejected(tmp_path):
    path = tmp_path / "config.toml"
    for placeholder in ("WRITE-YOUR-NAME-HERE", "KIRJUTA-SIIA-OMA-NIMI"):
        path.write_text(f'contributor = "{placeholder}"\n', encoding="utf-8")
        with pytest.raises(ValueError, match="your own name"):
            load_config(str(path))


def test_auto_update_is_on_by_default_and_can_be_turned_off(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('contributor = "Mari"\n', encoding="utf-8")
    assert load_config(str(path)).auto_update is True
    path.write_text('contributor = "Mari"\nauto_update = false\n', encoding="utf-8")
    assert load_config(str(path)).auto_update is False
