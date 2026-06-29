from __future__ import annotations

from sv_cli.formatter import to_csv, to_markdown, to_text


def test_csv_from_tabular_response():
    data = {"keywords": [{"keyword": "white label seo", "volume": 1900}]}
    csv_text = to_csv(data)
    assert "keyword,volume" in csv_text
    assert "white label seo,1900" in csv_text


def test_markdown_table_from_tabular_response():
    data = {"results": [{"label": "Meta Description", "id": 15}]}
    md = to_markdown(data)
    assert "| label | id |" in md


def test_text_prefers_primary_output():
    assert to_text({"result": "hello"}) == "hello"
