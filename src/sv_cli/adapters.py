"""Local command adapters.

Adapters intentionally contain only human-friendly command metadata. Endpoints,
required fields, and enums are still discovered from SV API definitions
at runtime whenever possible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolAdapter:
    canonical: str
    command: str
    aliases: tuple[str, ...] = ()
    default_action: str = "run"
    actions: tuple[str, ...] = ("run",)
    field_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    option_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    async_likely: bool = False
    # Optional local discovery hints. These are used only when the live API root
    # has not yet exposed a known tool. The API root remains the source of truth
    # and overrides these values whenever it contains the tool.
    endpoint_path: str | None = None
    definitions_path: str | None = None


COMMON_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "keyword": ("keyword", "kw", "query", "seed_keyword"),
    "keywords": ("keywords", "kws", "keyword_list", "kwlist"),
    "url": ("url", "domain", "page_url", "website"),
    "url_a": ("url_a", "urla", "url1", "first_url", "competitor_url"),
    "url_b": ("url_b", "urlb", "url2", "second_url", "comparison_url"),
    "brand": ("brand", "brand_name", "company", "company_name"),
    "type": ("contenttype", "content_type", "imagetype", "image_type", "type"),
    "language": ("language", "lang", "language_id"),
    "engine": ("engine", "ai_engine", "model"),
    "country": ("country", "country_code", "location", "gl"),
    "location": ("location", "geo", "country", "market"),
    "text": ("text", "content", "input", "body"),
    "search": ("searchterm", "search_term", "search", "query", "term"),
    "query": ("searchterm", "search_term", "query", "search", "term"),
    "price": ("price", "max_price", "price_ceiling"),
    "series": ("series", "service_series"),
    "category": ("category", "service_category"),
    "outline": ("outline", "outline_text"),
    "theme": ("theme", "image_theme"),
    "background": ("background", "bg", "image_background"),
    "color": ("color", "colour", "palette"),
    "size": ("size", "image_size", "dimensions"),
}

TOOL_ADAPTERS: dict[str, ToolAdapter] = {
    "better-keywords": ToolAdapter(
        canonical="better-keywords",
        command="better-keywords",
        aliases=("keywords",),
        default_action="research",
        actions=("research", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
    ),
    "content-transformer": ToolAdapter(
        canonical="content-transformer",
        command="content-transformer",
        aliases=("transform",),
        default_action="rewrite",
        actions=("rewrite", "summarize", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
    ),
    "core-analysis": ToolAdapter(
        canonical="core-analysis",
        command="core-analysis",
        aliases=("core",),
        default_action="analyze",
        actions=("analyze", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
    ),
    "geogptaudit": ToolAdapter(
        canonical="geogptaudit",
        command="geo-audit",
        aliases=("geogpt-audit", "audit"),
        default_action="run",
        actions=("run", "create-task", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
        async_likely=True,
    ),
    "insight-igniter": ToolAdapter(
        canonical="insight-igniter",
        command="insight-igniter",
        aliases=("insights",),
        default_action="generate",
        actions=("generate", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
    ),
    "preliminaryaudit": ToolAdapter(
        canonical="preliminaryaudit",
        command="preliminary-audit",
        aliases=("prelim-audit",),
        default_action="run",
        actions=("run", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
    ),
    "ranklens": ToolAdapter(
        canonical="ranklens",
        command="ranklens",
        aliases=(),
        default_action="analyze",
        actions=("analyze", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
    ),
    "seo-image": ToolAdapter(
        canonical="seo-image",
        command="seo-image",
        aliases=("image",),
        default_action="generate",
        actions=("generate", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
        option_aliases={
            "themes": ("theme", "themes"),
            "backgrounds": ("background", "backgrounds"),
            "colors": ("color", "colors", "colour", "colours"),
            "sizes": ("size", "sizes"),
            "types": ("imagetype", "image_type", "type", "types"),
        },
    ),
    "seogpt": ToolAdapter(
        canonical="seogpt",
        command="seogpt",
        aliases=("seo-gpt",),
        default_action="generate",
        actions=("generate", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
        option_aliases={
            "types": ("contenttype", "content_type", "type", "types"),
            "languages": ("language", "lang", "languages"),
            "engines": ("engine", "model", "engines"),
        },
    ),
    "seogpt2": ToolAdapter(
        canonical="seogpt2",
        command="seogpt2",
        aliases=("seo-gpt2",),
        default_action="article",
        actions=("article", "create-task", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
        async_likely=True,
    ),
    "seogptcompare": ToolAdapter(
        canonical="seogptcompare",
        command="seogpt-compare",
        aliases=("compare",),
        default_action="run",
        actions=("run", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
    ),
    "seogptmapping": ToolAdapter(
        canonical="seogptmapping",
        command="seo-mapping",
        aliases=("mapping",),
        default_action="run",
        actions=("run", "create-task", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
        async_likely=True,
    ),
    "topical-authority": ToolAdapter(
        canonical="topical-authority",
        command="topical-authority",
        aliases=("topical",),
        default_action="generate",
        actions=("generate", "raw"),
        field_aliases=COMMON_FIELD_ALIASES,
    ),
    "top-competitors": ToolAdapter(
        canonical="top-competitors",
        command="top-competitors",
        aliases=("competitors",),
        default_action="analyze",
        actions=("analyze", "raw"),
        field_aliases={
            **COMMON_FIELD_ALIASES,
            "keyword": ("kw", "keyword", "query", "seed_keyword"),
        },
        endpoint_path="top-competitors/",
        definitions_path="top-competitors/definitions",
    ),
    "marketplace-services": ToolAdapter(
        canonical="marketplace-services",
        command="marketplace-services",
        aliases=("marketplace", "services"),
        default_action="search",
        actions=("search", "raw"),
        field_aliases={
            **COMMON_FIELD_ALIASES,
            "keyword": ("searchterm", "search_term", "kw", "keyword", "query"),
            "search": ("searchterm", "search_term", "search", "query", "term"),
            "query": ("searchterm", "search_term", "query", "search", "term"),
        },
        option_aliases={
            "series": ("series", "service_series"),
            "categories": ("category", "service_category", "categories"),
        },
        endpoint_path="marketplace-services/",
        definitions_path="marketplace-services/definitions",
    ),
    "content-quality": ToolAdapter(
        canonical="content-quality",
        command="content-quality",
        aliases=("quality", "hcu-quality", "eeat-quality"),
        default_action="analyze",
        actions=("analyze", "raw"),
        field_aliases={
            **COMMON_FIELD_ALIASES,
            "keyword": ("kw", "keyword", "query", "seed_keyword"),
            "url": ("url1", "url", "domain", "page_url", "website"),
            "url_a": ("url1", "url_a", "urla", "first_url"),
            "url_b": ("url2", "url_b", "urlb", "second_url", "comparison_url"),
        },
        endpoint_path="content-quality/",
        definitions_path="content-quality/definitions",
    ),
}



def all_command_names() -> dict[str, str]:
    """Return command/alias -> adapter canonical mapping."""

    names: dict[str, str] = {}
    for canonical, adapter in TOOL_ADAPTERS.items():
        names[adapter.command] = canonical
        names[canonical] = canonical
        for alias in adapter.aliases:
            names[alias] = canonical
    return names


def get_adapter(tool: str) -> ToolAdapter | None:
    return TOOL_ADAPTERS.get(tool)


def field_candidates(tool: str, cli_field: str) -> tuple[str, ...]:
    adapter = TOOL_ADAPTERS.get(tool)
    if adapter and cli_field in adapter.field_aliases:
        return adapter.field_aliases[cli_field]
    return COMMON_FIELD_ALIASES.get(cli_field, (cli_field,))


def tool_display_name(canonical: str) -> str:
    adapter = TOOL_ADAPTERS.get(canonical)
    return adapter.command if adapter else canonical


def adapter_as_dict(adapter: ToolAdapter) -> dict[str, Any]:
    return {
        "canonical": adapter.canonical,
        "command": adapter.command,
        "aliases": list(adapter.aliases),
        "default_action": adapter.default_action,
        "actions": list(adapter.actions),
        "async_likely": adapter.async_likely,
        "endpoint_path": adapter.endpoint_path,
        "definitions_path": adapter.definitions_path,
    }
