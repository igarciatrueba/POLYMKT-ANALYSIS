import os

from polymkt.config import Settings


def test_settings_default_top_n_traders_is_300():
    settings = Settings(_env_file=None)
    assert settings.top_n_traders == 300


def test_settings_reads_top_n_traders_from_env(monkeypatch):
    monkeypatch.setenv("TOP_N_TRADERS", "500")
    settings = Settings(_env_file=None)
    assert settings.top_n_traders == 500
