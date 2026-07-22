"""HTTP client for SV API calls."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from rich.console import Console

from .errors import APIError, NetworkError, TimeoutError
from .utils import mask_mapping


@dataclass
class APIResponse:
    data: Any
    status_code: int
    elapsed_seconds: float
    url: str


class APIClient:
    def __init__(self, *, debug: bool = False, console: Console | None = None) -> None:
        self.debug = debug
        self.console = console or Console(stderr=True)

    def request_tool(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        api_key: str | None,
        method: str = "POST",
        timeout: float = 300.0,
    ) -> APIResponse:
        final_payload = dict(payload)
        if api_key and not any(key in final_payload for key in ("k", "api_key", "apikey", "key")):
            final_payload["k"] = api_key

        method = method.upper()
        if self.debug:
            parsed = urlparse(endpoint)
            shown_path = parsed.path or endpoint
            self.console.print(f"[dim]{method} {shown_path}[/dim]")
            self.console.print_json(json.dumps(mask_mapping(final_payload)))

        started = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                if method == "GET":
                    response = client.get(endpoint, params=final_payload)
                elif method in {"POST", "PUT", "PATCH"}:
                    response = client.request(method, endpoint, json=final_payload)
                else:
                    raise APIError(f"Unsupported HTTP method: {method}")
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Request timed out after {timeout:g} seconds.") from exc
        except httpx.RequestError as exc:
            raise NetworkError(f"Network error while calling SV API: {exc}") from exc

        elapsed = time.perf_counter() - started
        if self.debug:
            self.console.print(f"[dim]HTTP {response.status_code} in {elapsed:.2f}s[/dim]")

        try:
            data = response.json()
        except json.JSONDecodeError:
            data = response.text

        if response.status_code in {401, 403}:
            raise APIError(f"API authentication failed: HTTP {response.status_code}. Check your API key.")
        if response.status_code == 429:
            raise APIError("API rate limit exceeded. Retry later or increase --poll-interval for async tasks.")
        if response.status_code >= 400:
            message = data if isinstance(data, str) else json.dumps(mask_mapping(data), ensure_ascii=False)
            raise APIError(f"API request failed: HTTP {response.status_code}. {message}")

        return APIResponse(data=data, status_code=response.status_code, elapsed_seconds=elapsed, url=endpoint)
