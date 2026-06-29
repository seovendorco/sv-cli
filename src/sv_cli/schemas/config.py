from __future__ import annotations

from pydantic import BaseModel


class ProfileConfig(BaseModel):
    api_key: str | None = None
    base_url: str


class CLIConfig(BaseModel):
    default_profile: str = "default"
    profiles: dict[str, ProfileConfig]
