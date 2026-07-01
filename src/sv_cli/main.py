"""SV CLI entry point."""

from __future__ import annotations

import copy
import getpass
import sys
from typing import Any, Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .adapters import TOOL_ADAPTERS, ToolAdapter, adapter_as_dict, all_command_names
from .api_client import APIClient
from .config import (
    DEFAULT_BASE_URL,
    clear_api_key,
    create_profile,
    delete_profile,
    get_config_value,
    load_config,
    masked_config,
    reset_config,
    set_api_key,
    set_config_value,
    use_profile,
)
from .definitions import DefinitionsManager
from .errors import CLIError, ConfigError, InvalidInputError
from .executor import RuntimeOptions, WaitOptions, execute_tool, load_json_payload
from .formatter import print_output
from .resolver import extract_option_sets, resolve_api_field, search_candidates
from .tasks import get_task_tool, result_payload, status_payload
from .utils import coerce_jsonish, coerce_mapping_values, parse_key_value_args, read_text_source

console = Console()
err_console = Console(stderr=True)
COMMON_CONTEXT_SETTINGS = {"allow_extra_args": True, "ignore_unknown_options": True}

app = typer.Typer(
    name="sv",
    help="Definition-driven CLI for SV AI API tools.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"sv-cli {__version__}")
        raise typer.Exit(0)


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", callback=version_callback, is_eager=True, help="Show version and exit."),
    profile: Optional[str] = typer.Option(None, "--profile", help="Configuration profile to use."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="SV API key. Prefer SV_API_KEY or auth set."),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Override API base URL."),
    output_format: Optional[str] = typer.Option(None, "--format", help="pretty|json|table|csv|markdown|text"),
    output: Optional[str] = typer.Option(None, "--output", help="Write output to a file."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress normal output."),
    verbose: bool = typer.Option(False, "--verbose", help="Show additional progress details."),
    debug: bool = typer.Option(False, "--debug", help="Show masked payloads, endpoints, and HTTP timing."),
    strict: bool = typer.Option(False, "--strict", help="Use strict enum matching for agents and CI."),
    no_fuzzy: bool = typer.Option(False, "--no-fuzzy", help="Disable fuzzy enum matching."),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Disable prompts and interactive choices."),
) -> None:
    cfg = load_config()
    defaults = cfg.get("defaults", {})
    if api_key:
        err_console.print("[yellow]Warning:[/yellow] --api-key can be stored in shell history. Prefer SV_API_KEY or `sv auth set`.")
    ctx.obj = RuntimeOptions(
        profile=profile,
        api_key=api_key,
        base_url=base_url,
        output_format=output_format or defaults.get("format", "pretty"),
        output=output,
        quiet=quiet,
        verbose=verbose,
        debug=debug,
        strict=strict or bool(defaults.get("strict", False)),
        no_fuzzy=no_fuzzy or not bool(defaults.get("fuzzy", True)),
        non_interactive=non_interactive,
    )


def fail(exc: Exception) -> None:
    if isinstance(exc, CLIError):
        err_console.print(f"[red]Error:[/red] {exc.message}")
        raise typer.Exit(exc.exit_code) from exc
    err_console.print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(1) from exc


def runtime_from_ctx(ctx: typer.Context) -> RuntimeOptions:
    runtime = ctx.obj if isinstance(ctx.obj, RuntimeOptions) else RuntimeOptions()
    return copy.copy(runtime)


def apply_runtime_overrides(runtime: RuntimeOptions, overrides: dict[str, Any]) -> RuntimeOptions:
    runtime = copy.copy(runtime)
    mapping = {
        "profile": "profile",
        "api_key": "api_key",
        "base_url": "base_url",
        "format": "output_format",
        "output_format": "output_format",
        "output": "output",
        "quiet": "quiet",
        "verbose": "verbose",
        "debug": "debug",
        "strict": "strict",
        "no_fuzzy": "no_fuzzy",
        "non_interactive": "non_interactive",
    }
    for cli_key, attr in mapping.items():
        if cli_key in overrides and overrides[cli_key] is not None:
            value = overrides.pop(cli_key)
            if attr in {"quiet", "verbose", "debug", "strict", "no_fuzzy", "non_interactive"}:
                value = bool(value)
            setattr(runtime, attr, value)
    return runtime


def pop_wait_options(params: dict[str, Any]) -> WaitOptions:
    wait = bool(params.pop("wait", False))
    timeout = int(params.pop("timeout", 600) or 600)
    poll_interval = int(params.pop("poll_interval", 5) or 5)
    no_progress = bool(params.pop("no_progress", False))
    return WaitOptions(wait=wait, timeout=timeout, poll_interval=poll_interval, no_progress=no_progress)


def run_tool_action(
    ctx: typer.Context,
    *,
    tool: str,
    action: str,
    params: dict[str, Any],
    method: str = "POST",
) -> None:
    try:
        runtime = runtime_from_ctx(ctx)
        params = {key: value for key, value in params.items() if value not in (None, False)}
        params.update(parse_key_value_args(ctx.args))
        params = coerce_mapping_values(params)
        runtime = apply_runtime_overrides(runtime, params)
        wait_options = pop_wait_options(params)
        execute_tool(
            tool_name=tool,
            action=action,
            params=params,
            runtime=runtime,
            wait_options=wait_options,
            method=method,
            console=console,
        )
    except Exception as exc:  # noqa: BLE001
        fail(exc)


# ---------------------------------------------------------------------------
# Auth commands
# ---------------------------------------------------------------------------
auth_app = typer.Typer(help="Configure API-key authentication.", no_args_is_help=True)


def auth_set_impl(ctx: typer.Context, api_key: str | None, profile: str | None) -> None:
    runtime = runtime_from_ctx(ctx)
    target_profile = profile or runtime.profile
    if not api_key:
        api_key = getpass.getpass("SV API key: ").strip()
    if not api_key:
        raise InvalidInputError("API key cannot be empty.")
    set_api_key(api_key, target_profile)
    console.print("API key saved to local profile config. It will be masked in status and debug output.")


@auth_app.command("set")
def auth_set(
    ctx: typer.Context,
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key to store. Omit to enter securely."),
    profile: Optional[str] = typer.Option(None, "--profile", help="Profile to update."),
) -> None:
    try:
        auth_set_impl(ctx, api_key, profile)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@auth_app.command("login")
def auth_login(
    ctx: typer.Context,
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key to store. Omit to enter securely."),
    profile: Optional[str] = typer.Option(None, "--profile", help="Profile to update."),
) -> None:
    try:
        auth_set_impl(ctx, api_key, profile)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@auth_app.command("status")
def auth_status(ctx: typer.Context) -> None:
    try:
        cfg = masked_config()
        runtime = runtime_from_ctx(ctx)
        profile_name = runtime.profile or cfg.get("default_profile") or "default"
        profile = cfg.get("profiles", {}).get(profile_name, {})
        env = __import__("os").environ
        env_present = "SV_API_KEY" in env
        legacy_env_present = "SEOVENDOR_API_KEY" in env
        table = Table("Source", "Status")
        table.add_row("--api-key", "provided" if runtime.api_key else "not provided")
        table.add_row("SV_API_KEY", "set" if env_present else "not set")
        table.add_row("SEOVENDOR_API_KEY", "set (legacy)" if legacy_env_present else "not set")
        table.add_row(f"profile:{profile_name}", "set" if profile.get("api_key") else "not set")
        table.add_row("base_url", str(profile.get("base_url") or DEFAULT_BASE_URL))
        console.print(table)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@auth_app.command("clear")
def auth_clear(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(None, "--profile", help="Profile to clear."),
) -> None:
    try:
        runtime = runtime_from_ctx(ctx)
        clear_api_key(profile or runtime.profile)
        console.print("API key cleared from local profile config.")
    except Exception as exc:  # noqa: BLE001
        fail(exc)


app.add_typer(auth_app, name="auth")


# ---------------------------------------------------------------------------
# Profile commands
# ---------------------------------------------------------------------------
profile_app = typer.Typer(help="Manage profiles for separate keys/environments.", no_args_is_help=True)


@profile_app.command("list")
def profile_list() -> None:
    try:
        cfg = masked_config()
        default_profile = cfg.get("default_profile")
        table = Table("Profile", "Default", "Base URL", "API Key")
        for name, prof in sorted(cfg.get("profiles", {}).items()):
            table.add_row(name, "yes" if name == default_profile else "", str(prof.get("base_url")), "set" if prof.get("api_key") else "")
        console.print(table)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@profile_app.command("create")
def profile_create(
    name: str = typer.Argument(..., help="Profile name."),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="Profile base URL."),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Optional API key."),
) -> None:
    try:
        create_profile(name, base_url=base_url, api_key=api_key)
        console.print(f'Profile "{name}" created.')
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@profile_app.command("use")
def profile_use(name: str = typer.Argument(..., help="Profile name.")) -> None:
    try:
        use_profile(name)
        console.print(f'Now using profile "{name}" by default.')
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@profile_app.command("delete")
def profile_delete(name: str = typer.Argument(..., help="Profile name.")) -> None:
    try:
        delete_profile(name)
        console.print(f'Profile "{name}" deleted.')
    except Exception as exc:  # noqa: BLE001
        fail(exc)


app.add_typer(profile_app, name="profile")


# ---------------------------------------------------------------------------
# Config commands
# ---------------------------------------------------------------------------
config_app = typer.Typer(help="Show and edit CLI configuration.", no_args_is_help=True)


@config_app.command("show")
def config_show(ctx: typer.Context) -> None:
    try:
        runtime = runtime_from_ctx(ctx)
        print_output(console, masked_config(), runtime.output_format, runtime.output)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@config_app.command("get")
def config_get(
    key: str = typer.Argument(..., help="Config key, e.g. base_url or cache_ttl_seconds."),
    profile: Optional[str] = typer.Option(None, "--profile", help="Profile for profile-scoped keys."),
) -> None:
    try:
        console.print(get_config_value(key, profile))
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(...),
    value: str = typer.Argument(...),
    profile: Optional[str] = typer.Option(None, "--profile", help="Profile for profile-scoped keys."),
) -> None:
    try:
        set_config_value(key, coerce_jsonish(value), profile)
        console.print(f"Set {key}.")
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@config_app.command("reset")
def config_reset() -> None:
    try:
        reset_config()
        console.print("Configuration reset.")
    except Exception as exc:  # noqa: BLE001
        fail(exc)


app.add_typer(config_app, name="config")


# ---------------------------------------------------------------------------
# Definition commands
# ---------------------------------------------------------------------------
definitions_app = typer.Typer(help="Fetch, inspect, refresh, and clear API definitions cache.", no_args_is_help=True)


@definitions_app.command("refresh")
def definitions_refresh(
    ctx: typer.Context,
    tool: Optional[str] = typer.Option(None, "--tool", help="Refresh one tool only."),
) -> None:
    try:
        runtime = runtime_from_ctx(ctx)
        manager = DefinitionsManager(runtime.base_url)
        if tool:
            entry = manager.refresh_tool(tool)
            console.print(f'Refreshed definitions for {entry["tool"]}.')
        else:
            cache = manager.refresh_all()
            console.print(f"Refreshed API root and {len(cache.get('tools', {}))} tool definitions.")
            for warning in cache.get("warnings", []):
                err_console.print(f"[yellow]Warning:[/yellow] {warning}")
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@definitions_app.command("list")
def definitions_list(ctx: typer.Context) -> None:
    try:
        runtime = runtime_from_ctx(ctx)
        manager = DefinitionsManager(runtime.base_url)
        cache = manager.get_cache(allow_stale=True)
        rows = []
        for tool_name, entry in sorted(cache.get("tools", {}).items()):
            rows.append(
                {
                    "tool": tool_name,
                    "command": entry.get("display_name") or tool_name,
                    "endpoint": entry.get("endpoint"),
                    "definitions_url": entry.get("definitions_url"),
                    "last_fetched": entry.get("last_fetched"),
                }
            )
        print_output(console, rows, "table" if runtime.output_format == "pretty" else runtime.output_format, runtime.output)
        for warning in cache.get("warnings", []):
            err_console.print(f"[yellow]Warning:[/yellow] {warning}")
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@definitions_app.command("show")
def definitions_show(
    ctx: typer.Context,
    tool: str = typer.Argument(..., help="Tool name or alias, e.g. seogpt or geo-audit."),
) -> None:
    try:
        runtime = runtime_from_ctx(ctx)
        manager = DefinitionsManager(runtime.base_url)
        entry = manager.get_tool(tool)
        print_output(console, entry, "json" if runtime.output_format == "pretty" else runtime.output_format, runtime.output)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@definitions_app.command("clear")
def definitions_clear(ctx: typer.Context) -> None:
    try:
        runtime = runtime_from_ctx(ctx)
        manager = DefinitionsManager(runtime.base_url)
        removed = manager.clear_cache()
        console.print("Definitions cache cleared." if removed else "Definitions cache was already empty.")
    except Exception as exc:  # noqa: BLE001
        fail(exc)


app.add_typer(definitions_app, name="definitions")


# ---------------------------------------------------------------------------
# Options discovery command
# ---------------------------------------------------------------------------

def split_positionals_and_options(args: list[str]) -> tuple[list[str], dict[str, Any]]:
    options = parse_key_value_args(args)
    positionals: list[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        if token.startswith("--"):
            if "=" not in token and i + 1 < len(args) and not args[i + 1].startswith("--"):
                i += 2
            else:
                i += 1
            continue
        positionals.append(token)
        i += 1
    return positionals, options


def show_options(ctx: typer.Context, tool: str | None, field: str | None, search: str | None) -> None:
    runtime = runtime_from_ctx(ctx)
    manager = DefinitionsManager(runtime.base_url)
    cache = manager.get_cache(allow_stale=True)
    if not tool:
        rows = []
        for tool_name, entry in sorted(cache.get("tools", {}).items()):
            option_sets = extract_option_sets(entry.get("definition") or {})
            rows.append({"tool": tool_name, "command": entry.get("display_name") or tool_name, "option_sets": len(option_sets)})
        print_output(console, rows, "table" if runtime.output_format == "pretty" else runtime.output_format, runtime.output)
        return

    entry = manager.get_tool(tool)
    canonical = entry["tool"]
    definition = entry.get("definition") or {}
    option_sets = extract_option_sets(definition)
    if not field:
        rows = [{"field": name, "count": len(candidates)} for name, candidates in sorted(option_sets.items())]
        print_output(console, rows, "table" if runtime.output_format == "pretty" else runtime.output_format, runtime.output)
        return

    api_field, candidates = resolve_api_field(canonical, field, definition)
    candidates = candidates or option_sets.get(field.replace("-", "_").lower())
    if not candidates:
        available = ", ".join(sorted(option_sets)) or "none found"
        raise ConfigError(f'No options found for "{field}" on tool "{canonical}". Available fields: {available}')
    candidates = search_candidates(candidates, search)
    rows = [
        {
            "label": candidate.label,
            "slug": candidate.slug,
            "id": candidate.id,
            "description": candidate.description or "",
            "aliases": ", ".join(candidate.aliases),
        }
        for candidate in candidates
    ]
    print_output(console, rows, "table" if runtime.output_format == "pretty" else runtime.output_format, runtime.output)


@app.command("options", context_settings=COMMON_CONTEXT_SETTINGS)
def options_command(ctx: typer.Context) -> None:
    """List/search dynamic enum options.

    Examples:
      sv options list
      sv options seogpt
      sv options seogpt contenttype --search meta
    """
    try:
        positionals, parsed_options = split_positionals_and_options(list(ctx.args))
        runtime = runtime_from_ctx(ctx)
        runtime = apply_runtime_overrides(runtime, parsed_options)
        ctx.obj = runtime
        search = parsed_options.pop("search", None)
        if positionals and positionals[0] == "list":
            show_options(ctx, None, None, search)
            return
        tool = positionals[0] if positionals else None
        field = positionals[1] if len(positionals) > 1 else None
        show_options(ctx, tool, field, search)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


# ---------------------------------------------------------------------------
# Raw calls and task commands
# ---------------------------------------------------------------------------
@app.command("call")
def raw_call(
    ctx: typer.Context,
    tool: str = typer.Argument(..., help="Tool name or alias."),
    json_payload: Optional[str] = typer.Option(None, "--json", help="Raw JSON object payload."),
    file_path: Optional[str] = typer.Option(None, "--file", help="Read raw JSON object payload from file."),
    stdin_flag: bool = typer.Option(False, "--stdin", help="Read raw JSON object payload from stdin."),
    method: str = typer.Option("POST", "--method", help="HTTP method, usually POST."),
) -> None:
    try:
        stdin_payload = sys.stdin.read() if stdin_flag else None
        payload = load_json_payload(json_payload=json_payload, file_path=file_path, stdin_payload=stdin_payload)
        runtime = runtime_from_ctx(ctx)
        # Raw calls intentionally bypass fuzzy matching. Users can pass exact API payloads.
        runtime.no_fuzzy = True
        execute_tool(tool_name=tool, action=None, params={}, runtime=runtime, raw_payload=payload, method=method, console=console)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


task_app = typer.Typer(help="Check async task status/results.", no_args_is_help=True)


def task_call(ctx: typer.Context, task_id: str, action: str, tool: str | None) -> None:
    runtime = runtime_from_ctx(ctx)
    manager = DefinitionsManager(runtime.base_url)
    canonical = manager.resolve_tool(get_task_tool(task_id, tool))
    entry = manager.get_tool(canonical)
    api_key = __import__("sv_cli.config", fromlist=["resolve_api_key"]).resolve_api_key(
        cli_api_key=runtime.api_key,
        profile=runtime.profile,
        allow_prompt=not runtime.non_interactive,
        non_interactive=runtime.non_interactive,
    )
    payload = status_payload(task_id) if action == "status" else result_payload(task_id)
    data = APIClient(debug=runtime.debug, console=err_console).request_tool(
        endpoint=str(entry.get("endpoint")), payload=payload, api_key=api_key
    ).data
    print_output(console, data, runtime.output_format, runtime.output)


@task_app.command("status")
def task_status(
    ctx: typer.Context,
    task_id: str = typer.Argument(...),
    tool: Optional[str] = typer.Option(None, "--tool", help="Tool that created the task, if not in local task cache."),
) -> None:
    try:
        task_call(ctx, task_id, "status", tool)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


@task_app.command("result")
def task_result(
    ctx: typer.Context,
    task_id: str = typer.Argument(...),
    tool: Optional[str] = typer.Option(None, "--tool", help="Tool that created the task, if not in local task cache."),
) -> None:
    try:
        task_call(ctx, task_id, "result", tool)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


app.add_typer(task_app, name="task")


# ---------------------------------------------------------------------------
# Tool command groups
# ---------------------------------------------------------------------------
def build_params(
    *,
    keyword: str | None,
    keywords: str | None,
    url: str | None,
    url_a: str | None,
    url_b: str | None,
    brand: str | None,
    type_value: str | None,
    language: str | None,
    engine: str | None,
    country: str | None,
    location: str | None,
    text: str | None,
    file_path: str | None,
    stdin_flag: bool,
    search: str | None,
    query: str | None,
    price: str | None,
    series: str | None,
    category: str | None,
    outline: str | None,
    theme: str | None,
    background: str | None,
    color: str | None,
    size: str | None,
    wait: bool,
    timeout: int,
    poll_interval: int,
    no_progress: bool,
    output_format: str | None,
    output: str | None,
    quiet: bool,
    verbose: bool,
    debug: bool,
    strict: bool,
    no_fuzzy: bool,
    non_interactive: bool,
    api_key: str | None,
    base_url: str | None,
    profile: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "keyword": keyword,
        "keywords": keywords,
        "url": url,
        "url_a": url_a,
        "url_b": url_b,
        "brand": brand,
        "type": type_value,
        "language": language,
        "engine": engine,
        "country": country,
        "location": location,
        "search": search,
        "query": query,
        "price": price,
        "series": series,
        "category": category,
        "outline": outline,
        "theme": theme,
        "background": background,
        "color": color,
        "size": size,
        "wait": wait,
        "timeout": timeout,
        "poll_interval": poll_interval,
        "no_progress": no_progress,
        "format": output_format,
        "output": output,
        "quiet": quiet,
        "verbose": verbose,
        "debug": debug,
        "strict": strict,
        "no_fuzzy": no_fuzzy,
        "non_interactive": non_interactive,
        "api_key": api_key,
        "base_url": base_url,
        "profile": profile,
    }
    try:
        source = read_text_source(text=text, file_path=file_path, use_stdin=stdin_flag, field_name="text")
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc
    if source:
        field, content = source
        params[field] = content
    return params


def make_action_command(tool: str, action: str):
    def command(
        ctx: typer.Context,
        keyword: Optional[str] = typer.Option(None, "--keyword", "--kw", help="Primary keyword."),
        keywords: Optional[str] = typer.Option(None, "--keywords", help="Comma-separated keywords or path to a keyword file."),
        url: Optional[str] = typer.Option(None, "--url", help="Target URL/domain."),
        url_a: Optional[str] = typer.Option(None, "--url-a", "--url1", help="First URL for comparison or URL 1."),
        url_b: Optional[str] = typer.Option(None, "--url-b", "--url2", help="Second URL for comparison or URL 2."),
        brand: Optional[str] = typer.Option(None, "--brand", help="Brand or company name."),
        type_value: Optional[str] = typer.Option(None, "--type", help="Type/content type/image type by ID, slug, label, or alias."),
        language: Optional[str] = typer.Option(None, "--language", help="Language by ID, slug, label, or alias."),
        engine: Optional[str] = typer.Option(None, "--engine", help="Engine/model by ID, slug, label, or alias."),
        country: Optional[str] = typer.Option(None, "--country", help="Country/market code where supported."),
        location: Optional[str] = typer.Option(None, "--location", help="Location/market where supported."),
        text: Optional[str] = typer.Option(None, "--text", help="Text input for transformer-style tools."),
        file_path: Optional[str] = typer.Option(None, "--file", help="Read text input from file."),
        stdin_flag: bool = typer.Option(False, "--stdin", help="Read text input from stdin."),
        search: Optional[str] = typer.Option(None, "--search", "--searchterm", help="Search term for marketplace/service-style tools."),
        query: Optional[str] = typer.Option(None, "--query", help="Query/search term where supported."),
        price: Optional[str] = typer.Option(None, "--price", help="Price ceiling or price filter where supported."),
        series: Optional[str] = typer.Option(None, "--series", help="Service series filter where supported."),
        category: Optional[str] = typer.Option(None, "--category", help="Service category filter where supported."),
        outline: Optional[str] = typer.Option(None, "--outline", help="Outline text or path to outline file."),
        theme: Optional[str] = typer.Option(None, "--theme", help="Image theme by ID, slug, label, or alias."),
        background: Optional[str] = typer.Option(None, "--background", help="Image background by ID, slug, label, or alias."),
        color: Optional[str] = typer.Option(None, "--color", help="Image color/palette by ID, slug, label, or alias."),
        size: Optional[str] = typer.Option(None, "--size", help="Image size by ID, slug, label, or alias."),
        wait: bool = typer.Option(False, "--wait", help="Wait for async task completion."),
        timeout: int = typer.Option(600, "--timeout", help="Task wait timeout in seconds."),
        poll_interval: int = typer.Option(5, "--poll-interval", help="Task poll interval in seconds."),
        no_progress: bool = typer.Option(False, "--no-progress", help="Disable progress display."),
        output_format: Optional[str] = typer.Option(None, "--format", help="pretty|json|table|csv|markdown|text"),
        output: Optional[str] = typer.Option(None, "--output", help="Write output to a file."),
        quiet: bool = typer.Option(False, "--quiet", help="Suppress normal output."),
        verbose: bool = typer.Option(False, "--verbose", help="Verbose output."),
        debug: bool = typer.Option(False, "--debug", help="Debug output with secrets masked."),
        strict: bool = typer.Option(False, "--strict", help="Strict enum matching."),
        no_fuzzy: bool = typer.Option(False, "--no-fuzzy", help="Disable fuzzy enum matching."),
        non_interactive: bool = typer.Option(False, "--non-interactive", help="Disable prompts."),
        api_key: Optional[str] = typer.Option(None, "--api-key", help="API key override."),
        base_url: Optional[str] = typer.Option(None, "--base-url", help="Base URL override."),
        profile: Optional[str] = typer.Option(None, "--profile", help="Profile override."),
    ) -> None:
        params = build_params(
            keyword=keyword,
            keywords=keywords,
            url=url,
            url_a=url_a,
            url_b=url_b,
            brand=brand,
            type_value=type_value,
            language=language,
            engine=engine,
            country=country,
            location=location,
            text=text,
            file_path=file_path,
            stdin_flag=stdin_flag,
            search=search,
            query=query,
            price=price,
            series=series,
            category=category,
            outline=outline,
            theme=theme,
            background=background,
            color=color,
            size=size,
            wait=wait,
            timeout=timeout,
            poll_interval=poll_interval,
            no_progress=no_progress,
            output_format=output_format,
            output=output,
            quiet=quiet,
            verbose=verbose,
            debug=debug,
            strict=strict,
            no_fuzzy=no_fuzzy,
            non_interactive=non_interactive,
            api_key=api_key,
            base_url=base_url,
            profile=profile,
        )
        run_tool_action(ctx, tool=tool, action=action, params=params)

    command.__name__ = f"{tool.replace('-', '_')}_{action.replace('-', '_')}"
    return command


def make_option_alias_command(tool: str, field_aliases: tuple[str, ...]):
    def command(
        ctx: typer.Context,
        search: Optional[str] = typer.Option(None, "--search", help="Filter options."),
        output_format: Optional[str] = typer.Option(None, "--format", help="Output format."),
        output: Optional[str] = typer.Option(None, "--output", help="Write output to file."),
    ) -> None:
        try:
            runtime = runtime_from_ctx(ctx)
            overrides: dict[str, Any] = {"format": output_format, "output": output}
            runtime = apply_runtime_overrides(runtime, overrides)
            ctx.obj = runtime
            show_options(ctx, tool, field_aliases[0], search)
        except Exception as exc:  # noqa: BLE001
            fail(exc)

    command.__name__ = f"{tool.replace('-', '_')}_{field_aliases[0]}_options"
    return command


def make_tool_app(adapter: ToolAdapter) -> typer.Typer:
    tool_app = typer.Typer(
        help=f"Commands for {adapter.command} ({adapter.canonical}).",
        invoke_without_command=True,
        context_settings=COMMON_CONTEXT_SETTINGS,
    )

    @tool_app.callback(invoke_without_command=True, context_settings=COMMON_CONTEXT_SETTINGS)
    def tool_callback(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is not None:
            return
        try:
            params = parse_key_value_args(ctx.args)
            runtime = runtime_from_ctx(ctx)
            runtime = apply_runtime_overrides(runtime, params)
            wait_options = pop_wait_options(params)
            execute_tool(
                tool_name=adapter.canonical,
                action=adapter.default_action,
                params=params,
                runtime=runtime,
                wait_options=wait_options,
                console=console,
            )
        except Exception as exc:  # noqa: BLE001
            fail(exc)

    for action in adapter.actions:
        if action == "raw":
            continue
        tool_app.command(action, context_settings=COMMON_CONTEXT_SETTINGS)(make_action_command(adapter.canonical, action))

    @tool_app.command("raw")
    def raw(
        ctx: typer.Context,
        json_payload: Optional[str] = typer.Option(None, "--json", help="Raw JSON payload."),
        file_path: Optional[str] = typer.Option(None, "--file", help="Read raw JSON from file."),
        stdin_flag: bool = typer.Option(False, "--stdin", help="Read raw JSON from stdin."),
        method: str = typer.Option("POST", "--method", help="HTTP method."),
    ) -> None:
        try:
            stdin_payload = sys.stdin.read() if stdin_flag else None
            payload = load_json_payload(json_payload=json_payload, file_path=file_path, stdin_payload=stdin_payload)
            runtime = runtime_from_ctx(ctx)
            runtime.no_fuzzy = True
            execute_tool(
                tool_name=adapter.canonical,
                action=None,
                params={},
                runtime=runtime,
                raw_payload=payload,
                method=method,
                console=console,
            )
        except Exception as exc:  # noqa: BLE001
            fail(exc)

    for command_name, fields in adapter.option_aliases.items():
        tool_app.command(command_name)(make_option_alias_command(adapter.canonical, fields))

    return tool_app


registered_names: set[str] = set()
for adapter in TOOL_ADAPTERS.values():
    group = make_tool_app(adapter)
    for name in (adapter.command, *adapter.aliases):
        if name not in registered_names:
            app.add_typer(group, name=name)
            registered_names.add(name)


# ---------------------------------------------------------------------------
# Beginner-friendly presets
# ---------------------------------------------------------------------------
@app.command("meta", context_settings=COMMON_CONTEXT_SETTINGS)
def preset_meta(
    ctx: typer.Context,
    keyword: str = typer.Option(..., "--keyword", "--kw"),
    url: Optional[str] = typer.Option(None, "--url"),
    output_format: Optional[str] = typer.Option(None, "--format"),
    output: Optional[str] = typer.Option(None, "--output"),
) -> None:
    params = {"type": "meta-description", "keyword": keyword, "url": url, "format": output_format, "output": output}
    run_tool_action(ctx, tool="seogpt", action="generate", params=params)


@app.command("title", context_settings=COMMON_CONTEXT_SETTINGS)
def preset_title(
    ctx: typer.Context,
    keyword: str = typer.Option(..., "--keyword", "--kw"),
    url: Optional[str] = typer.Option(None, "--url"),
    brand: Optional[str] = typer.Option(None, "--brand"),
    output_format: Optional[str] = typer.Option(None, "--format"),
    output: Optional[str] = typer.Option(None, "--output"),
) -> None:
    params = {
        "type": "page-title",
        "keyword": keyword,
        "url": url,
        "brand": brand,
        "format": output_format,
        "output": output,
    }
    run_tool_action(ctx, tool="seogpt", action="generate", params=params)


@app.command("registry")
def registry(ctx: typer.Context) -> None:
    """Show local command adapters used on top of live definitions."""

    try:
        runtime = runtime_from_ctx(ctx)
        data = {name: adapter_as_dict(adapter) for name, adapter in TOOL_ADAPTERS.items()}
        data["command_aliases"] = all_command_names()
        print_output(console, data, "json" if runtime.output_format == "pretty" else runtime.output_format, runtime.output)
    except Exception as exc:  # noqa: BLE001
        fail(exc)


if __name__ == "__main__":  # pragma: no cover
    app()
