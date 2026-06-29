from __future__ import annotations

from typing import Any

from sv_cli.formatter import to_text


def render(data: Any) -> str:
    return to_text(data)
