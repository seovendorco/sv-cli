from __future__ import annotations

import json
from pathlib import Path

import pytest

from sv_cli.errors import AmbiguousMatchError, InvalidInputError
from sv_cli.resolver import (
    extract_option_sets,
    is_cli_field_relevant,
    resolve_api_field,
    resolve_enum_value,
)

FIXTURE = Path(__file__).parent / "fixtures" / "seogpt_definitions.json"
RANKLENS_FIXTURE = Path(__file__).parent / "fixtures" / "ranklens_definitions.json"
SEOGPT2_FIXTURE = Path(__file__).parent / "fixtures" / "seogpt2_definitions.json"


def load_definition():
    return json.loads(FIXTURE.read_text())


def test_extract_option_sets_finds_nested_options():
    option_sets = extract_option_sets(load_definition())
    assert "contenttype" in option_sets
    assert "language" in option_sets
    assert option_sets["contenttype"][1].slug == "meta-description"


def test_resolves_numeric_id_slug_label_alias_and_fuzzy():
    candidates = extract_option_sets(load_definition())["contenttype"]
    assert resolve_enum_value("contenttype", "15", candidates) == 15
    assert resolve_enum_value("contenttype", "meta-description", candidates) == 15
    assert resolve_enum_value("contenttype", "Meta Description", candidates) == 15
    assert resolve_enum_value("contenttype", "meta desc", candidates) == 15
    assert resolve_enum_value("contenttype", "seo descrption", candidates) == 15


def test_ambiguous_contains_match_exits_as_invalid_input():
    candidates = extract_option_sets(load_definition())["contenttype"]
    with pytest.raises(AmbiguousMatchError):
        resolve_enum_value("contenttype", "description", candidates)


def test_strict_mode_rejects_alias():
    candidates = extract_option_sets(load_definition())["contenttype"]
    with pytest.raises(InvalidInputError):
        resolve_enum_value("contenttype", "meta desc", candidates, strict=True)


def test_resolve_api_field_uses_adapter_alias():
    field, candidates = resolve_api_field("seogpt", "type", load_definition())
    assert field == "contenttype"
    assert candidates is not None


def test_resolve_api_field_length_resolves_to_content_length_for_seogpt2():
    definition = json.loads(SEOGPT2_FIXTURE.read_text())
    field, candidates = resolve_api_field("seogpt2", "length", definition)
    assert field == "contentlength"
    assert candidates is not None


def test_resolve_api_field_length_matches_literal_field_name():
    definition = {
        "api_input": [
            {"field": "length", "type": "integer", "description": ["0: 10", "1: 20"], "required": "no"},
        ]
    }
    field, candidates = resolve_api_field("content-transformer", "length", definition)
    assert field == "length"
    assert candidates is not None


def test_extract_option_sets_from_valid_values_description():
    definition = {
        "api_input": [
            {
                "field": "category",
                "type": "string",
                "description": "Service category filter. Valid values: SEO, PPC, DEV.",
                "required": "no",
            }
        ]
    }
    options = extract_option_sets(definition)
    assert [candidate.id for candidate in options["category"]] == ["SEO", "PPC", "DEV"]
    assert resolve_enum_value("category", "seo", options["category"]) == "SEO"


def test_is_cli_field_relevant_true_for_real_fields():
    definition = json.loads(RANKLENS_FIXTURE.read_text())
    assert is_cli_field_relevant("ranklens", "entity", definition) is True
    assert is_cli_field_relevant("ranklens", "brand", definition) is True


def test_is_cli_field_relevant_false_for_unrelated_fields():
    definition = json.loads(RANKLENS_FIXTURE.read_text())
    assert is_cli_field_relevant("ranklens", "price", definition) is False
    assert is_cli_field_relevant("ranklens", "theme", definition) is False


def test_is_cli_field_relevant_seogpt2_topic_vs_price():
    definition = json.loads(SEOGPT2_FIXTURE.read_text())
    assert is_cli_field_relevant("seogpt2", "topic", definition) is True
    assert is_cli_field_relevant("seogpt2", "keyword", definition) is True
    assert is_cli_field_relevant("seogpt2", "length", definition) is True
    assert is_cli_field_relevant("seogpt2", "price", definition) is False


def test_is_cli_field_relevant_defaults_true_with_no_definition():
    """No live definition cached yet -> never hide anything (safe fallback)."""

    assert is_cli_field_relevant("seogpt2", "price", {}) is True
    assert is_cli_field_relevant("seogpt2", "price", None) is True
