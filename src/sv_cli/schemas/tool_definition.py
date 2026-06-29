"""Pydantic models used by tests and downstream consumers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    tool: str
    endpoint: str | None = None
    definitions_url: str | None = Field(default=None, alias="definitionsUrl")
    definition: Any = None
    last_fetched: str | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}
