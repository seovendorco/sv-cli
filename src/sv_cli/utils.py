"""Shared utility functions."""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_SECRET_KEYS = {"k", "key", "api_key", "apikey", "apiKey", "token", "authorization", "Authorization"}


def app_dir() -> Path:
    """Return the CLI state directory, overridable for tests.

    SV_HOME is the current override. SEOVENDOR_HOME is accepted as a legacy
    fallback so existing automation can migrate without losing local state.
    """

    override = os.environ.get("SV_HOME") or os.environ.get("SEOVENDOR_HOME")
    return Path(override).expanduser() if override else Path.home() / ".sv"


def legacy_app_dir() -> Path:
    """Return the pre-brand-change state directory."""

    return Path.home() / ".seovendor"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json_file(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def write_json_file(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def mask_secret(value: Any, visible: int = 4) -> Any:
    if value is None:
        return None
    text = str(value)
    if len(text) <= visible:
        return "***masked***"
    return f"***masked***{text[-visible:]}"


def mask_mapping(data: Any) -> Any:
    """Return a deep-copy-like structure with common secret fields masked."""

    if isinstance(data, dict):
        masked: dict[str, Any] = {}
        for key, value in data.items():
            if key in _SECRET_KEYS or key.lower() in _SECRET_KEYS:
                masked[key] = mask_secret(value)
            else:
                masked[key] = mask_mapping(value)
        return masked
    if isinstance(data, list):
        return [mask_mapping(item) for item in data]
    return data


def normalize_text(value: Any) -> str:
    """Normalize text according to the spec's enum matching rules."""

    text = str(value).lower().strip()
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact_text(value: Any) -> str:
    return normalize_text(value).replace(" ", "")


def slugify(value: Any) -> str:
    text = normalize_text(value)
    return re.sub(r"\s+", "-", text).strip("-")


def parse_key_value_args(args: Iterable[str]) -> dict[str, Any]:
    """Parse unknown CLI args such as --foo bar, --foo=bar, and --flag.

    Hyphenated option names are converted to underscores because the API definitions
    overwhelmingly use compact/snake names, while the command line should remain human-friendly.
    """

    result: dict[str, Any] = {}
    args = list(args)
    i = 0
    while i < len(args):
        token = args[i]
        if not token.startswith("--"):
            i += 1
            continue
        key = token[2:]
        value: Any = True
        if "=" in key:
            key, value = key.split("=", 1)
        elif i + 1 < len(args) and not args[i + 1].startswith("--"):
            value = args[i + 1]
            i += 1
        key = key.strip().replace("-", "_")
        if key:
            if key in result:
                existing = result[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    result[key] = [existing, value]
            else:
                result[key] = value
        i += 1
    return result


def read_text_source(
    *,
    text: str | None = None,
    file_path: str | None = None,
    use_stdin: bool = False,
    field_name: str = "text",
) -> tuple[str, str] | None:
    """Read text from explicit text, file, or stdin.

    Returns (field_name, content) when data is present.
    """

    supplied = [text is not None, file_path is not None, use_stdin]
    if sum(bool(x) for x in supplied) > 1:
        raise ValueError(f"Use only one of --{field_name}, --file, or --stdin")
    if text is not None:
        return field_name, text
    if file_path is not None:
        return field_name, Path(file_path).expanduser().read_text(encoding="utf-8")
    if use_stdin:
        return field_name, sys.stdin.read()
    return None


def maybe_read_file_value(value: str | None) -> str | None:
    """If value names an existing file, return its contents; otherwise return the value."""

    if not value:
        return value
    path = Path(value).expanduser()
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")
    return value


def coerce_jsonish(value: str) -> Any:
    """Best-effort conversion for extra params."""

    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if re.fullmatch(r"-?\d+\.\d+", value):
            return float(value)
    except ValueError:
        pass
    if value.startswith("{") or value.startswith("["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def coerce_mapping_values(data: dict[str, Any]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, list):
            coerced[key] = [coerce_jsonish(v) if isinstance(v, str) else v for v in value]
        elif isinstance(value, str):
            coerced[key] = coerce_jsonish(value)
        else:
            coerced[key] = value
    return coerced
