from __future__ import annotations

import json
from pathlib import Path

from sv_cli.definitions import DefinitionsManager

ROOT = json.loads((Path(__file__).parent / "fixtures" / "api_root.json").read_text())
DEF = json.loads((Path(__file__).parent / "fixtures" / "seogpt_definitions.json").read_text())


def test_resolve_tool_alias_from_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SV_HOME", str(tmp_path))
    manager = DefinitionsManager("https://ai.seovendor.co/api/")
    cache = {
        "version": 1,
        "base_url": "https://ai.seovendor.co/api/",
        "fetched_at": "2099-01-01T00:00:00+00:00",
        "root": {"geogptaudit": {"Endpoint": "x", "Definitions": "y"}},
        "tools": {"geogptaudit": {"tool": "geogptaudit", "endpoint": "x", "definitions_url": "y", "definition": DEF}},
        "warnings": [],
    }
    manager.save_cache(cache)
    assert manager.resolve_tool("geo-audit") == "geogptaudit"
    assert manager.resolve_tool("audit") == "geogptaudit"


def test_supplemental_tools_are_added_when_root_cache_omits_them(tmp_path, monkeypatch):
    monkeypatch.setenv("SV_HOME", str(tmp_path))
    manager = DefinitionsManager("https://ai.seovendor.co/api/")
    cache = {
        "version": 1,
        "base_url": "https://ai.seovendor.co/api/",
        "fetched_at": "2099-01-01T00:00:00+00:00",
        "root": {"seogpt": {"Endpoint": "x", "Definitions": "y"}},
        "tools": {"seogpt": {"tool": "seogpt", "endpoint": "x", "definitions_url": "y"}},
        "warnings": [],
    }
    manager.save_cache(cache)

    loaded = manager.load_cache()

    assert "top-competitors" in loaded["root"]
    assert loaded["tools"]["top-competitors"]["endpoint"].endswith("/top-competitors/")
    assert loaded["tools"]["content-quality"]["definitions_url"].endswith(
        "/content-quality/definitions"
    )
    assert manager.resolve_tool("competitors", loaded) == "top-competitors"
    assert manager.resolve_tool("marketplace", loaded) == "marketplace-services"
    assert manager.resolve_tool("quality", loaded) == "content-quality"
