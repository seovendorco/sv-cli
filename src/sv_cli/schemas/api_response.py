from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class APIResponseModel(BaseModel):
    data: Any
    status_code: int
    elapsed_seconds: float
    url: str
