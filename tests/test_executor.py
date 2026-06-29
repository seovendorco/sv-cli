from __future__ import annotations

import json
from pathlib import Path

from sv_cli.executor import build_payload

DEF = json.loads((Path(__file__).parent / "fixtures" / "seogpt_definitions.json").read_text())


def test_build_payload_resolves_friendly_type_to_enum_id():
    payload = build_payload(
        tool="seogpt",
        action="generate",
        params={"type": "meta desc", "keyword": "white label seo"},
        definition=DEF,
        strict=False,
        fuzzy=True,
        non_interactive=True,
    )
    assert payload["action"] == "generate"
    assert payload["contenttype"] == 15
    assert payload["kw"] == "white label seo"


def test_build_payload_for_new_top_competitors_tool():
    payload = build_payload(
        tool="top-competitors",
        action="analyze",
        params={"keyword": "white label seo"},
        definition={},
        strict=False,
        fuzzy=True,
        non_interactive=True,
    )
    assert payload == {"action": "analyze", "kw": "white label seo"}


def test_build_payload_for_new_marketplace_services_tool():
    payload = build_payload(
        tool="marketplace-services",
        action="search",
        params={"search": "seo audit", "price": "500", "category": "SEO"},
        definition={},
        strict=False,
        fuzzy=True,
        non_interactive=True,
    )
    assert payload == {
        "action": "search",
        "searchterm": "seo audit",
        "price": 500,
        "category": "SEO",
    }


def test_build_payload_for_new_content_quality_tool():
    payload = build_payload(
        tool="content-quality",
        action="analyze",
        params={
            "keyword": "white label seo",
            "url": "https://example.com",
            "url_b": "https://competitor.example",
        },
        definition={},
        strict=False,
        fuzzy=True,
        non_interactive=True,
    )
    assert payload == {
        "action": "analyze",
        "kw": "white label seo",
        "url1": "https://example.com",
        "url2": "https://competitor.example",
    }
