"""Output formatters for human and machine use."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from .errors import UnsupportedFeatureError
from .utils import ensure_parent, mask_mapping

SUPPORTED_FORMATS = {"pretty", "json", "table", "csv", "markdown", "text"}


def render_output(data: Any, fmt: str = "pretty") -> str | None:
    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise UnsupportedFeatureError(
            f'Unsupported output format "{fmt}". Use one of: {", ".join(sorted(SUPPORTED_FORMATS))}'
        )
    safe_data = mask_mapping(data)
    if fmt == "json":
        return json.dumps(safe_data, indent=2, ensure_ascii=False)
    if fmt == "csv":
        return to_csv(safe_data)
    if fmt == "markdown":
        return to_markdown(safe_data)
    if fmt == "text":
        return to_text(safe_data)
    if fmt == "table":
        return to_table_text(safe_data)
    return None


def print_output(console: Console, data: Any, fmt: str = "pretty", output: str | None = None) -> None:
    rendered = render_output(data, fmt)
    if output:
        path = Path(output).expanduser()
        ensure_parent(path)
        if rendered is None:
            rendered = to_text(mask_mapping(data))
        path.write_text(rendered + ("" if rendered.endswith("\n") else "\n"), encoding="utf-8")
        return
    if rendered is not None:
        console.print(rendered)
        return
    print_pretty(console, mask_mapping(data))


def print_pretty(console: Console, data: Any) -> None:
    if isinstance(data, dict):
        primary_text = extract_primary_text(data)
        rows = find_tabular_data(data)
        if primary_text and not rows:
            console.print(primary_text)
            return
        if rows:
            print_table(console, rows)
            extra = {k: v for k, v in data.items() if v is not rows and not isinstance(v, list)}
            if extra:
                console.print_json(json.dumps(extra, ensure_ascii=False))
            return
        console.print_json(json.dumps(data, ensure_ascii=False))
        return
    if isinstance(data, list):
        if data and all(isinstance(item, dict) for item in data):
            print_table(console, data)
        else:
            console.print_json(json.dumps(data, ensure_ascii=False))
        return
    console.print(str(data))


def extract_primary_text(data: dict[str, Any]) -> str | None:
    for key in ("text", "content", "result", "output", "answer", "message", "data"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    return None


def find_tabular_data(data: Any) -> list[dict[str, Any]] | None:
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        return data
    if isinstance(data, dict):
        for key in ("keywords", "results", "items", "data", "rows", "records"):
            value = data.get(key)
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return value
    return None


def to_csv(data: Any) -> str:
    rows = find_tabular_data(data)
    if not rows:
        raise UnsupportedFeatureError("CSV output requires a list of records in the API response.")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: serialize_cell(row.get(key)) for key in fieldnames})
    return buffer.getvalue().rstrip("\n")


def to_markdown(data: Any) -> str:
    rows = find_tabular_data(data)
    if rows:
        return rows_to_markdown(rows)
    if isinstance(data, dict):
        primary = extract_primary_text(data)
        if primary:
            return primary
        lines = []
        for key, value in data.items():
            lines.append(f"## {key}\n")
            lines.append(value if isinstance(value, str) else f"```json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```")
        return "\n\n".join(lines)
    if isinstance(data, list):
        return "\n".join(f"- {serialize_cell(item)}" for item in data)
    return str(data)


def rows_to_markdown(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    header = "| " + " | ".join(fieldnames) + " |"
    divider = "| " + " | ".join("---" for _ in fieldnames) + " |"
    body = [
        "| " + " | ".join(escape_markdown_table(serialize_cell(row.get(key))) for key in fieldnames) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def to_text(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        primary = extract_primary_text(data)
        if primary:
            return primary
    return json.dumps(data, indent=2, ensure_ascii=False)


def to_table_text(data: Any) -> str:
    rows = find_tabular_data(data)
    if not rows:
        raise UnsupportedFeatureError("Table output requires a list of records in the API response.")
    # Plain text table for file output and non-rich paths.
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    widths = {
        key: max(len(str(key)), *(len(serialize_cell(row.get(key))) for row in rows)) for key in fieldnames
    }
    lines = []
    lines.append("  ".join(str(key).ljust(widths[key]) for key in fieldnames))
    lines.append("  ".join("-" * widths[key] for key in fieldnames))
    for row in rows:
        lines.append("  ".join(serialize_cell(row.get(key)).ljust(widths[key]) for key in fieldnames))
    return "\n".join(lines)


def print_table(console: Console, rows: list[dict[str, Any]]) -> None:
    if not rows:
        console.print("No rows returned.")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(str(key))
    table = Table(show_header=True, header_style="bold")
    for key in fieldnames:
        table.add_column(str(key))
    for row in rows:
        table.add_row(*(serialize_cell(row.get(key)) for key in fieldnames))
    console.print(table)


def print_markdown(console: Console, text: str) -> None:
    console.print(Markdown(text))


def serialize_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def escape_markdown_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")
