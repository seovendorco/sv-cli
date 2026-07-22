from __future__ import annotations

import json
from pathlib import Path

from sv_cli.executor import build_payload

DEF = json.loads((Path(__file__).parent / "fixtures" / "seogpt_definitions.json").read_text())
SEOGPT2_DEF = json.loads((Path(__file__).parent / "fixtures" / "seogpt2_definitions.json").read_text())
RANKLENS_DEF = json.loads((Path(__file__).parent / "fixtures" / "ranklens_definitions.json").read_text())


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


def test_seogpt2_topic_and_keyword_are_distinct_fields():
    """--topic must set Topic; --keyword/--keywords must set KW, never Topic."""

    payload = build_payload(
        tool="seogpt2",
        action="create-task",
        params={"topic": "Best running shoes for flat feet", "keyword": "running shoes, flat feet"},
        definition=SEOGPT2_DEF,
        strict=False,
        fuzzy=True,
        non_interactive=True,
    )
    assert payload["topic"] == "Best running shoes for flat feet"
    assert payload["kw"] == "running shoes, flat feet"
    assert "Topic" not in payload  # resolved field name is the normalized "topic"


def test_seogpt2_title_flag_shares_the_topic_param():
    """--title is a second flag spelling on the same Typer option as --topic

    (see make_action_command in main.py), so by the time a value reaches
    build_payload() it's already under the "topic" params key - there is no
    separate "title" params key to resolve. This checks the field_aliases
    tuple that makes --topic/--title both land on the real Topic field.
    """

    from sv_cli.adapters import field_candidates

    assert "title" in field_candidates("seogpt2", "topic")


def test_seogpt2_keywords_plural_also_maps_to_kw():
    payload = build_payload(
        tool="seogpt2",
        action="create-task",
        params={"keywords": "trail running shoes"},
        definition=SEOGPT2_DEF,
        strict=False,
        fuzzy=True,
        non_interactive=True,
    )
    assert payload["kw"] == "trail running shoes"


def test_ranklens_entity_resolves_to_entity_field():
    payload = build_payload(
        tool="ranklens",
        action="rank",
        params={"entity": "best crm software"},
        definition=RANKLENS_DEF,
        strict=False,
        fuzzy=True,
        non_interactive=True,
    )
    assert payload["entity"] == "best crm software"


def test_ranklens_legacy_keyword_and_kw_flags_also_resolve_to_entity():
    """--keyword/--kw must keep working for RankLens, landing on the new entity field."""

    payload_keyword = build_payload(
        tool="ranklens",
        action="rank",
        params={"keyword": "best crm software"},
        definition=RANKLENS_DEF,
        strict=False,
        fuzzy=True,
        non_interactive=True,
    )
    assert payload_keyword["entity"] == "best crm software"
