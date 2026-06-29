from __future__ import annotations

import json

import pytest

from sv_cli.config import clear_api_key, resolve_api_key, set_api_key
from sv_cli.errors import AuthError


def test_api_key_priority_cli_env_config(tmp_path, monkeypatch):
    monkeypatch.setenv("SV_HOME", str(tmp_path))
    monkeypatch.delenv("SEOVENDOR_API_KEY", raising=False)
    set_api_key("stored-key")
    monkeypatch.setenv("SV_API_KEY", "env-key")
    assert resolve_api_key(cli_api_key="cli-key") == "cli-key"
    assert resolve_api_key() == "env-key"
    monkeypatch.delenv("SV_API_KEY")
    assert resolve_api_key() == "stored-key"


def test_missing_api_key_is_auth_error(tmp_path, monkeypatch):
    monkeypatch.setenv("SV_HOME", str(tmp_path))
    monkeypatch.delenv("SV_API_KEY", raising=False)
    monkeypatch.delenv("SEOVENDOR_API_KEY", raising=False)
    clear_api_key()
    with pytest.raises(AuthError):
        resolve_api_key(non_interactive=True)


def test_legacy_env_key_is_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("SV_HOME", str(tmp_path))
    monkeypatch.delenv("SV_API_KEY", raising=False)
    monkeypatch.setenv("SEOVENDOR_API_KEY", "legacy-env-key")
    assert resolve_api_key() == "legacy-env-key"


def test_legacy_config_is_read_when_new_config_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SV_HOME", raising=False)
    monkeypatch.delenv("SEOVENDOR_HOME", raising=False)
    monkeypatch.delenv("SV_API_KEY", raising=False)
    monkeypatch.delenv("SEOVENDOR_API_KEY", raising=False)

    legacy_dir = tmp_path / ".seovendor"
    legacy_dir.mkdir()
    (legacy_dir / "config.json").write_text(
        json.dumps({
            "default_profile": "default",
            "profiles": {"default": {"api_key": "legacy-stored-key"}},
        }),
        encoding="utf-8",
    )

    assert resolve_api_key() == "legacy-stored-key"
