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

RATE_LIMIT_RETRIES = 3
# Just over the API's one-call-per-second window, so a retry lands in the next window.
RATE_LIMIT_DEFAULT_WAIT = 1.1


def _retry_after_seconds(response: httpx.Response) -> float:
    """Seconds to wait before retrying a 429, from its Retry-After header if usable."""
    try:
        seconds = float(response.headers.get("Retry-After", ""))
    except ValueError:
        return RATE_LIMIT_DEFAULT_WAIT
    return min(max(seconds, 0.0) + 0.1, 10.0)


@dataclass
class APIResponse:
    data: Any
    status_code: int
    elapsed_seconds: float
    url: str


class APIClient:
    def __init__(self, *, debug: bool = False, console: Console | None = None, client_type: str | None = None) -> None:
        self.debug = debug
        self.console = console or Console(stderr=True)
        # Identifies this process to the SV API as "cli" or "mcp" (X-SV-Client header)
        # for usage tracking. None means the caller didn't specify one - the header is
        # simply omitted, and the API buckets the call as generic "api" usage.
        self.client_type = client_type

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
        headers = {"X-SV-Client": self.client_type} if self.client_type else None
        if self.debug:
            parsed = urlparse(endpoint)
            shown_path = parsed.path or endpoint
            self.console.print(f"[dim]{method} {shown_path}[/dim]")
            self.console.print_json(json.dumps(mask_mapping(final_payload)))

        started = time.perf_counter()
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
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

            # The SV API allows one call per second per API key and rejects anything faster
            # with 429 *before* doing any work - nothing is charged and no task is created -
            # so retrying is always safe, including for task creation. This keeps --wait
            # polling (which checks status right after creating a task, and fetches the
            # result right after a "done" status) and parallel tool calls from MCP clients
            # working under the limit.
            if response.status_code != 429 or attempt == RATE_LIMIT_RETRIES:
                break
            wait = _retry_after_seconds(response)
            if self.debug:
                self.console.print(f"[dim]Rate limited; retrying in {wait:.1f}s[/dim]")
            time.sleep(wait)

        elapsed = time.perf_counter() - started
        if self.debug:
            self.console.print(f"[dim]HTTP {response.status_code} in {elapsed:.2f}s[/dim]")

        try:
            data = response.json()
        except json.JSONDecodeError:
            data = response.text

        if response.status_code in {401, 403}:
            raise APIError(
                f"API authentication failed: HTTP {response.status_code}. Check your API key.",
                status_code=response.status_code,
                data=data,
            )
        if response.status_code == 429:
            raise APIError(
                "API rate limit exceeded. Retry later or increase --poll-interval for async tasks.",
                status_code=response.status_code,
                data=data,
            )
        if response.status_code >= 400:
            message = data if isinstance(data, str) else json.dumps(mask_mapping(data), ensure_ascii=False)
            raise APIError(
                f"API request failed: HTTP {response.status_code}. {message}",
                status_code=response.status_code,
                data=data,
            )

        return APIResponse(data=data, status_code=response.status_code, elapsed_seconds=elapsed, url=endpoint)
