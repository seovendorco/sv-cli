"""APIClient behavior against the SV API's per-key rate limit (HTTP 429)."""

from __future__ import annotations

import httpx
import pytest

from sv_cli import api_client
from sv_cli.api_client import APIClient
from sv_cli.errors import APIError


def _install_transport(monkeypatch, responses):
    """Route APIClient's internal httpx.Client through a scripted MockTransport."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return responses.pop(0)

    real_client = httpx.Client

    def client_with_mock(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(api_client.httpx, "Client", client_with_mock)
    sleeps = []
    monkeypatch.setattr(api_client.time, "sleep", sleeps.append)
    return calls, sleeps


def _rate_limited():
    return httpx.Response(
        429,
        headers={"Retry-After": "1"},
        json={"success": False, "error": {"code": "RATE_LIMITED", "message": "Too many requests."}},
    )


def test_retries_after_rate_limit_then_succeeds(monkeypatch):
    calls, sleeps = _install_transport(
        monkeypatch, [_rate_limited(), httpx.Response(200, json={"success": True, "data": {"ok": 1}})]
    )
    response = APIClient().request_tool(endpoint="https://api.test/tool/", payload={}, api_key="k123")
    assert response.status_code == 200
    assert response.data["data"] == {"ok": 1}
    assert len(calls) == 2
    assert sleeps == [pytest.approx(1.1)]  # Retry-After: 1, plus a small margin


def test_gives_up_after_three_retries(monkeypatch):
    calls, sleeps = _install_transport(monkeypatch, [_rate_limited() for _ in range(4)])
    with pytest.raises(APIError) as excinfo:
        APIClient().request_tool(endpoint="https://api.test/tool/", payload={}, api_key="k123")
    assert len(calls) == 4  # 1 attempt + 3 retries
    assert len(sleeps) == 3
    assert excinfo.value.status_code == 429
    assert excinfo.value.data["error"]["code"] == "RATE_LIMITED"


def test_other_errors_are_not_retried(monkeypatch):
    calls, sleeps = _install_transport(
        monkeypatch, [httpx.Response(402, json={"success": False, "error": {"code": "INSUFFICIENT_POINTS"}})]
    )
    with pytest.raises(APIError):
        APIClient().request_tool(endpoint="https://api.test/tool/", payload={}, api_key="k123")
    assert len(calls) == 1
    assert sleeps == []


def test_retry_after_header_fallback():
    assert api_client._retry_after_seconds(httpx.Response(429)) == api_client.RATE_LIMIT_DEFAULT_WAIT
    assert api_client._retry_after_seconds(httpx.Response(429, headers={"Retry-After": "2"})) == pytest.approx(2.1)
    assert api_client._retry_after_seconds(httpx.Response(429, headers={"Retry-After": "999"})) == 10.0
