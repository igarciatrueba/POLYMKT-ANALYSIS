import os

import pytest
from pydantic import ValidationError

from polymkt.config import Settings


def test_settings_default_top_n_traders_is_300():
    settings = Settings(_env_file=None)
    assert settings.top_n_traders == 300


def test_settings_reads_top_n_traders_from_env(monkeypatch):
    monkeypatch.setenv("TOP_N_TRADERS", "500")
    settings = Settings(_env_file=None)
    assert settings.top_n_traders == 500


@pytest.mark.parametrize("top_n", [0, -1, 1001])
def test_settings_rejects_top_n_outside_supported_range(monkeypatch, top_n):
    monkeypatch.setenv("TOP_N_TRADERS", str(top_n))

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
