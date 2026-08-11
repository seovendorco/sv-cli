"""Generic tool execution layer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console

from .adapters import get_adapter
from .api_client import APIClient
from .config import resolve_api_key
from .definitions import DefinitionsManager
from .errors import ConfigError, InvalidInputError
from .formatter import print_output
from .resolver import extract_option_sets, resolve_api_field, resolve_enum_value
from .tasks import extract_task_id, save_task, wait_for_task
from .utils import coerce_mapping_values, mask_mapping, maybe_read_file_value


@dataclass
class RuntimeOptions:
    profile: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    output_format: str = "pretty"
    output: str | None = None
    quiet: bool = False
    verbose: bool = False
    debug: bool = False
    strict: bool = False
    no_fuzzy: bool = False
    non_interactive: bool = False


@dataclass
class WaitOptions:
    wait: bool = False
    timeout: int = 600
    poll_interval: int = 5
    no_progress: bool = False


def load_json_payload(
    *, json_payload: str | None = None, file_path: str | None = None, stdin_payload: str | None = None
) -> dict[str, Any]:
    supplied = [json_payload is not None, file_path is not None, stdin_payload is not None]
    if sum(bool(item) for item in supplied) != 1:
        raise InvalidInputError("Provide exactly one of --json, --file, or --stdin for raw call payloads.")
    if json_payload is not None:
        source = json_payload
    elif file_path is not None:
        source = Path(file_path).expanduser().read_text(encoding="utf-8")
    else:
        source = stdin_payload or ""
    try:
        payload = json.loads(source)
    except json.JSONDecodeError as exc:
        raise InvalidInputError(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidInputError("Raw call payload must be a JSON object.")
    return payload


def build_payload(
    *,
    tool: str,
    action: str | None,
    params: dict[str, Any],
    definition: Any,
    strict: bool,
    fuzzy: bool,
    non_interactive: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if action and action != "raw":
        payload["action"] = normalize_action(action)

    params = coerce_mapping_values({key: value for key, value in params.items() if value is not None})
    option_sets = extract_option_sets(definition)

    for cli_field, value in params.items():
        if cli_field in {"json", "file", "stdin"}:
            continue
        if cli_field == "keywords" and isinstance(value, str):
            value = maybe_read_file_value(value)
        if cli_field == "outline" and isinstance(value, str):
            value = maybe_read_file_value(value)

        api_field, candidates = resolve_api_field(tool, cli_field, definition)
        if candidates is None:
            candidates = option_sets.get(api_field)
        if candidates:
            value = resolve_enum_value(
                api_field,
                value,
                candidates,
                strict=strict,
                fuzzy=fuzzy,
                non_interactive=non_interactive,
            )
        payload[api_field] = value
    return payload


def normalize_action(action: str) -> str:
    parts = action.split("-")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def execute_tool(
    *,
    tool_name: str,
    action: str | None,
    params: dict[str, Any],
    runtime: RuntimeOptions,
    wait_options: WaitOptions | None = None,
    raw_payload: dict[str, Any] | None = None,
    method: str = "POST",
    console: Console | None = None,
    client_type: str | None = None,
) -> Any:
    console = console or Console()
    definitions = DefinitionsManager(runtime.base_url)
    entry = definitions.get_tool(tool_name)
    tool = entry["tool"]
    endpoint = entry.get("endpoint")
    if not endpoint:
        raise ConfigError(f'Tool "{tool}" does not have an endpoint in the API root.')
    definition = entry.get("definition") or {}
    api_key = resolve_api_key(
        cli_api_key=runtime.api_key,
        profile=runtime.profile,
        allow_prompt=not runtime.non_interactive,
        non_interactive=runtime.non_interactive,
    )

    if raw_payload is not None:
        payload = dict(raw_payload)
    else:
        payload = build_payload(
            tool=tool,
            action=action,
            params=params,
            definition=definition,
            strict=runtime.strict,
            fuzzy=not runtime.no_fuzzy,
            non_interactive=runtime.non_interactive,
        )

    client = APIClient(debug=runtime.debug, console=Console(stderr=True), client_type=client_type)
    response = client.request_tool(endpoint=str(endpoint), payload=payload, api_key=api_key, method=method)
    data = response.data

    task_id = extract_task_id(data)
    if task_id:
        save_task(task_id, tool, str(endpoint))

    if wait_options and wait_options.wait:
        if not task_id:
            if runtime.verbose or runtime.debug:
                Console(stderr=True).print("[yellow]--wait was set, but no task ID was found in the response.[/yellow]")
        else:
            data = wait_for_task(
                task_id=task_id,
                tool=tool,
                api_key=api_key,
                definitions=definitions,
                client=client,
                timeout_seconds=wait_options.timeout,
                poll_interval=wait_options.poll_interval,
                no_progress=wait_options.no_progress or runtime.quiet,
                console=Console(stderr=True),
            )

    if runtime.debug:
        Console(stderr=True).print("[dim]Resolved payload:[/dim]")
        Console(stderr=True).print_json(json.dumps(mask_mapping(payload), ensure_ascii=False))

    if not runtime.quiet:
        print_output(console, data, runtime.output_format, runtime.output)
    return data


def adapter_default_action(tool: str) -> str:
    adapter = get_adapter(tool)
    return adapter.default_action if adapter else "run"
