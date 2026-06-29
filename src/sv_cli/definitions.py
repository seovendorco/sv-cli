"""Dynamic SV API discovery and local definitions cache."""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from .adapters import TOOL_ADAPTERS, all_command_names, tool_display_name
from .config import DEFAULT_BASE_URL, load_config, normalize_base_url
from .errors import ConfigError, NetworkError
from .utils import app_dir, normalize_text, read_json_file, write_json_file

CACHE_VERSION = 1


def cache_path() -> Path:
    return app_dir() / "cache" / "definitions.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return dt.datetime.fromisoformat(value).timestamp()
    except ValueError:
        return 0.0


def default_cache(base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    return {
        "version": CACHE_VERSION,
        "base_url": normalize_base_url(base_url),
        "fetched_at": None,
        "root": {},
        "tools": {},
        "warnings": [],
    }


class DefinitionsManager:
    """Fetch, cache, and resolve API root/tool definitions."""

    def __init__(self, base_url: str | None = None, *, ttl_seconds: int | None = None) -> None:
        cfg = load_config()
        profile_name = cfg.get("default_profile") or "default"
        profile = cfg.get("profiles", {}).get(profile_name, {})
        self.base_url = normalize_base_url(base_url or profile.get("base_url") or DEFAULT_BASE_URL)
        self.ttl_seconds = int(
            ttl_seconds
            if ttl_seconds is not None
            else cfg.get("defaults", {}).get("cache_ttl_seconds", 24 * 60 * 60)
        )
        self.path = cache_path()

    def load_cache(self) -> dict[str, Any]:
        try:
            cached = read_json_file(self.path, default_cache(self.base_url))
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        if not cached:
            return default_cache(self.base_url)
        cached.setdefault("version", CACHE_VERSION)
        cached.setdefault("base_url", self.base_url)
        cached.setdefault("root", {})
        cached.setdefault("tools", {})
        cached.setdefault("warnings", [])
        self.ensure_supplemental_tools(cached)
        return cached

    def save_cache(self, cache: dict[str, Any]) -> None:
        cache["version"] = CACHE_VERSION
        cache["base_url"] = self.base_url
        write_json_file(self.path, cache)

    def clear_cache(self) -> bool:
        if self.path.exists():
            self.path.unlink()
            return True
        return False

    def is_stale(self, cache: dict[str, Any]) -> bool:
        if not cache.get("root"):
            return True
        fetched = parse_timestamp(cache.get("fetched_at"))
        return (time.time() - fetched) > self.ttl_seconds

    def get_cache(self, *, refresh: bool = False, allow_stale: bool = True) -> dict[str, Any]:
        cache = self.load_cache()
        if refresh or self.is_stale(cache):
            try:
                return self.refresh_all()
            except Exception as exc:  # noqa: BLE001 - cache fallback should be broad
                if allow_stale and cache.get("root"):
                    cache.setdefault("warnings", []).append(
                        f"Definitions refresh failed; using stale cache: {exc}"
                    )
                    return cache
                if isinstance(exc, NetworkError):
                    raise
                raise NetworkError(f"Could not fetch API definitions and no usable cache exists: {exc}") from exc
        return cache

    def fetch_json(self, url: str) -> Any:
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Timed out while fetching {url}") from exc
        except httpx.HTTPStatusError as exc:
            raise NetworkError(
                f"Definitions request failed for {url}: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise NetworkError(f"Network error while fetching {url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise NetworkError(f"Definitions endpoint did not return valid JSON: {url}") from exc

    def supplemental_root_entries(self) -> dict[str, dict[str, str]]:
        """Return adapter-provided endpoint hints for tools missing from the API root.

        These entries are a compatibility bridge for newly released tools whose
        definitions endpoints are live before the API root advertises them.
        They are deliberately derived from the active base URL, so profiles and
        staging URLs still work.
        """

        entries: dict[str, dict[str, str]] = {}
        for canonical, adapter in TOOL_ADAPTERS.items():
            if not adapter.endpoint_path:
                continue
            definitions_path = adapter.definitions_path or f"{adapter.endpoint_path.rstrip('/')}/definitions"
            entries[canonical] = {
                "Endpoint": join_base_url(self.base_url, adapter.endpoint_path),
                "Definitions": join_base_url(self.base_url, definitions_path),
                "Source": "local-adapter-fallback",
            }
        return entries

    def ensure_supplemental_tools(self, cache: dict[str, Any]) -> None:
        """Merge local adapter hints into a cache without overwriting live root data."""

        root = cache.setdefault("root", {})
        tools = cache.setdefault("tools", {})
        for tool_name, meta in self.supplemental_root_entries().items():
            if tool_name in root:
                continue
            root[tool_name] = meta
            tools.setdefault(
                tool_name,
                {
                    "tool": tool_name,
                    "display_name": tool_display_name(tool_name),
                    "endpoint": meta.get("Endpoint"),
                    "definitions_url": meta.get("Definitions"),
                    "definition": None,
                    "last_fetched": None,
                    "source": meta.get("Source"),
                },
            )

    def refresh_all(self) -> dict[str, Any]:
        root = self.fetch_json(self.base_url)
        if not isinstance(root, dict):
            raise NetworkError(f"API root {self.base_url} did not return a JSON object")
        cache = default_cache(self.base_url)
        cache["root"] = dict(root)
        self.ensure_supplemental_tools(cache)
        cache["fetched_at"] = utc_now()
        warnings: list[str] = []
        for tool_name, meta in cache["root"].items():
            endpoint = _pick_value(meta, "Endpoint", "endpoint", "url")
            definitions_url = _pick_value(meta, "Definitions", "definitions", "definition", "schema")
            existing_entry = cache.get("tools", {}).get(tool_name, {})
            tool_entry = {
                "tool": tool_name,
                "display_name": tool_display_name(tool_name),
                "endpoint": endpoint or existing_entry.get("endpoint"),
                "definitions_url": definitions_url or existing_entry.get("definitions_url"),
                "definition": existing_entry.get("definition"),
                "last_fetched": existing_entry.get("last_fetched"),
                "source": existing_entry.get("source", "api-root"),
            }
            if tool_entry.get("definitions_url"):
                try:
                    tool_entry["definition"] = self.fetch_json(str(tool_entry["definitions_url"]))
                    tool_entry["last_fetched"] = utc_now()
                except Exception as exc:  # noqa: BLE001 - partial cache is still useful
                    warnings.append(f"Could not fetch definitions for {tool_name}: {exc}")
            cache["tools"][tool_name] = tool_entry
        cache["warnings"] = warnings
        self.save_cache(cache)
        return cache

    def refresh_tool(self, tool_name: str) -> dict[str, Any]:
        cache = self.get_cache(allow_stale=True)
        canonical = self.resolve_tool(tool_name, cache)
        entry = cache.get("tools", {}).get(canonical)
        if not entry:
            raise ConfigError(f'Tool "{tool_name}" is not available in the API root.')
        definitions_url = entry.get("definitions_url")
        if not definitions_url:
            raise NetworkError(f'Tool "{canonical}" does not expose a definitions URL in the root.')
        entry["definition"] = self.fetch_json(str(definitions_url))
        entry["last_fetched"] = utc_now()
        cache["tools"][canonical] = entry
        self.save_cache(cache)
        return entry

    def resolve_tool(self, user_value: str, cache: dict[str, Any] | None = None) -> str:
        cache = cache or self.get_cache(allow_stale=True)
        root_tools = set(cache.get("root", {}).keys()) | set(cache.get("tools", {}).keys())
        if user_value in root_tools:
            return user_value
        alias_map = all_command_names()
        if user_value in alias_map:
            preferred = alias_map[user_value]
            if preferred in root_tools:
                return preferred
        norm_user = normalize_text(user_value).replace(" ", "")
        for name in root_tools:
            if normalize_text(name).replace(" ", "") == norm_user:
                return name
        for alias, canonical in alias_map.items():
            if normalize_text(alias).replace(" ", "") == norm_user and canonical in root_tools:
                return canonical
        known = ", ".join(sorted(root_tools)) or "none"
        raise ConfigError(f'Unknown tool "{user_value}". Available tools: {known}')

    def get_tool(self, user_value: str, *, refresh: bool = False) -> dict[str, Any]:
        cache = self.get_cache(refresh=refresh, allow_stale=True)
        canonical = self.resolve_tool(user_value, cache)
        entry = cache.get("tools", {}).get(canonical)
        if entry:
            if entry.get("definition") is None and entry.get("definitions_url"):
                try:
                    entry["definition"] = self.fetch_json(str(entry["definitions_url"]))
                    entry["last_fetched"] = utc_now()
                    cache.setdefault("tools", {})[canonical] = entry
                    self.save_cache(cache)
                except Exception as exc:  # noqa: BLE001 - callers can still use raw or schema-light tools
                    entry["definition_warning"] = f"Could not fetch definitions: {exc}"
            return entry
        meta = cache.get("root", {}).get(canonical, {})
        entry = {
            "tool": canonical,
            "display_name": tool_display_name(canonical),
            "endpoint": _pick_value(meta, "Endpoint", "endpoint", "url"),
            "definitions_url": _pick_value(meta, "Definitions", "definitions", "definition", "schema"),
            "definition": None,
            "last_fetched": None,
        }
        cache.setdefault("tools", {})[canonical] = entry
        self.save_cache(cache)
        return entry


def join_base_url(base_url: str, path: str) -> str:
    return urljoin(normalize_base_url(base_url), path.lstrip("/"))


def _pick_value(data: Any, *keys: str) -> Any:
    if not isinstance(data, dict):
        return None
    for key in keys:
        if key in data:
            return data[key]
    lowered = {str(k).lower(): v for k, v in data.items()}
    for key in keys:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None
