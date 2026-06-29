"""Configuration, profiles, and API-key resolution."""

from __future__ import annotations

import getpass
import os
from pathlib import Path
from typing import Any

from .errors import AuthError, ConfigError
from .utils import app_dir, legacy_app_dir, mask_mapping, read_json_file, write_json_file

DEFAULT_BASE_URL = "https://ai.seovendor.co/api/"
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60


def config_path() -> Path:
    return app_dir() / "config.json"


def legacy_config_path() -> Path:
    return legacy_app_dir() / "config.json"


def default_config() -> dict[str, Any]:
    return {
        "default_profile": "default",
        "profiles": {
            "default": {
                "api_key": None,
                "base_url": DEFAULT_BASE_URL,
            }
        },
        "defaults": {
            "format": "pretty",
            "cache_ttl_seconds": DEFAULT_CACHE_TTL_SECONDS,
            "strict": False,
            "fuzzy": True,
        },
    }


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        # When a caller explicitly sets SV_HOME or SEOVENDOR_HOME, keep all
        # reads isolated to that directory. Otherwise, read the legacy default
        # path once as a migration aid for pre-rename installs.
        if os.environ.get("SV_HOME") or os.environ.get("SEOVENDOR_HOME"):
            return default_config()
        legacy_path = legacy_config_path()
        if legacy_path.exists():
            path = legacy_path
        else:
            return default_config()
    try:
        loaded = read_json_file(path, default_config())
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    cfg = default_config()
    cfg.update({k: v for k, v in loaded.items() if k != "profiles"})
    cfg["profiles"].update(loaded.get("profiles", {}))
    cfg.setdefault("defaults", {}).update(loaded.get("defaults", {}))
    if cfg.get("default_profile") not in cfg.get("profiles", {}):
        cfg["default_profile"] = "default"
        cfg["profiles"].setdefault("default", {"api_key": None, "base_url": DEFAULT_BASE_URL})
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    write_json_file(config_path(), cfg)


def masked_config() -> dict[str, Any]:
    return mask_mapping(load_config())


def get_profile_name(cfg: dict[str, Any], profile: str | None = None) -> str:
    return profile or cfg.get("default_profile") or "default"


def get_profile(cfg: dict[str, Any], profile: str | None = None, create: bool = False) -> dict[str, Any]:
    name = get_profile_name(cfg, profile)
    profiles = cfg.setdefault("profiles", {})
    if name not in profiles:
        if not create:
            raise ConfigError(f'Profile "{name}" does not exist. Create it with: sv profile create {name}')
        profiles[name] = {"api_key": None, "base_url": DEFAULT_BASE_URL}
    profiles[name].setdefault("base_url", DEFAULT_BASE_URL)
    profiles[name].setdefault("api_key", None)
    return profiles[name]


def resolve_base_url(cli_base_url: str | None = None, profile: str | None = None) -> str:
    if cli_base_url:
        return normalize_base_url(cli_base_url)
    cfg = load_config()
    value = get_profile(cfg, profile).get("base_url") or DEFAULT_BASE_URL
    return normalize_base_url(value)


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/"


def resolve_api_key(
    *,
    cli_api_key: str | None = None,
    profile: str | None = None,
    allow_prompt: bool = False,
    non_interactive: bool = False,
) -> str:
    if cli_api_key:
        return cli_api_key
    env_key = os.environ.get("SV_API_KEY") or os.environ.get("SEOVENDOR_API_KEY")
    if env_key:
        return env_key
    cfg = load_config()
    stored = get_profile(cfg, profile).get("api_key")
    if stored:
        return stored
    if allow_prompt and not non_interactive:
        entered = getpass.getpass("SV API key: ").strip()
        if entered:
            return entered
    raise AuthError(
        "Missing SV API key. Set SV_API_KEY, run `sv auth set`, "
        "or pass --api-key. SEOVENDOR_API_KEY is also accepted as a legacy fallback. "
        "Avoid --api-key in shared shells because it may be saved in history."
    )


def set_api_key(api_key: str, profile: str | None = None) -> None:
    cfg = load_config()
    prof = get_profile(cfg, profile, create=True)
    prof["api_key"] = api_key
    save_config(cfg)


def clear_api_key(profile: str | None = None) -> None:
    cfg = load_config()
    prof = get_profile(cfg, profile, create=True)
    prof["api_key"] = None
    save_config(cfg)


def set_profile_value(profile: str, key: str, value: Any) -> None:
    cfg = load_config()
    prof = get_profile(cfg, profile, create=True)
    prof[key] = value
    save_config(cfg)


def create_profile(name: str, *, base_url: str | None = None, api_key: str | None = None) -> None:
    cfg = load_config()
    if name in cfg.setdefault("profiles", {}):
        raise ConfigError(f'Profile "{name}" already exists.')
    cfg["profiles"][name] = {
        "api_key": api_key,
        "base_url": normalize_base_url(base_url or DEFAULT_BASE_URL),
    }
    save_config(cfg)


def delete_profile(name: str) -> None:
    cfg = load_config()
    if name == "default":
        raise ConfigError('The "default" profile cannot be deleted.')
    if name not in cfg.setdefault("profiles", {}):
        raise ConfigError(f'Profile "{name}" does not exist.')
    del cfg["profiles"][name]
    if cfg.get("default_profile") == name:
        cfg["default_profile"] = "default"
    save_config(cfg)


def use_profile(name: str) -> None:
    cfg = load_config()
    if name not in cfg.setdefault("profiles", {}):
        raise ConfigError(f'Profile "{name}" does not exist. Create it with: sv profile create {name}')
    cfg["default_profile"] = name
    save_config(cfg)


def set_config_value(key: str, value: Any, profile: str | None = None) -> None:
    cfg = load_config()
    if key == "base_url":
        get_profile(cfg, profile, create=True)[key] = normalize_base_url(str(value))
    elif key == "api_key":
        get_profile(cfg, profile, create=True)[key] = str(value)
    elif key == "default_profile":
        if value not in cfg.get("profiles", {}):
            raise ConfigError(f'Profile "{value}" does not exist.')
        cfg["default_profile"] = str(value)
    else:
        cfg.setdefault("defaults", {})[key] = value
    save_config(cfg)


def get_config_value(key: str, profile: str | None = None) -> Any:
    cfg = load_config()
    if key in {"base_url", "api_key"}:
        value = get_profile(cfg, profile).get(key)
    elif key == "default_profile":
        value = cfg.get("default_profile")
    else:
        value = cfg.setdefault("defaults", {}).get(key)
    if key == "api_key" and value:
        return "***masked***" + str(value)[-4:]
    return value


def reset_config() -> None:
    path = config_path()
    if path.exists():
        path.unlink()
