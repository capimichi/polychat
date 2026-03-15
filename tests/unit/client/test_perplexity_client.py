import asyncio

import pytest

from polychat.client.perplexity_client import PerplexityClient


class _FakeResponse:
    def __init__(self, url: str, payload=None, json_error: Exception | None = None):
        self.url = url
        self._payload = payload
        self._json_error = json_error

    async def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class _FakePage:
    def __init__(self, responses=None):
        self._handlers: dict[str, list] = {}
        self._responses = responses or []

    def on(self, event_name: str, handler) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    async def emit_responses(self) -> None:
        for response in self._responses:
            for handler in self._handlers.get("response", []):
                await handler(response)


@pytest.mark.asyncio
async def test_detect_login_state_from_session_response_returns_true_for_non_empty_payload(tmp_path):
    client = PerplexityClient(str(tmp_path), session_cookie="cookie")
    page = _FakePage(
        responses=[
            _FakeResponse("https://www.perplexity.ai/api/auth/session", {"user": {"id": "123"}}),
        ]
    )

    detection = asyncio.create_task(client._detect_login_state_from_session_response(page))
    await asyncio.sleep(0)
    await page.emit_responses()

    response_seen, payload = await detection

    assert response_seen is True
    assert payload == {"user": {"id": "123"}}
    assert client._is_non_empty_session_payload(payload) is True


@pytest.mark.asyncio
async def test_detect_login_state_from_session_response_returns_false_for_empty_payload(tmp_path):
    client = PerplexityClient(str(tmp_path), session_cookie="cookie")
    page = _FakePage(
        responses=[
            _FakeResponse("https://www.perplexity.ai/api/auth/session", {}),
        ]
    )

    detection = asyncio.create_task(client._detect_login_state_from_session_response(page))
    await asyncio.sleep(0)
    await page.emit_responses()

    response_seen, payload = await detection

    assert response_seen is True
    assert payload == {}
    assert client._is_non_empty_session_payload(payload) is False


@pytest.mark.asyncio
async def test_detect_login_state_from_session_response_returns_false_when_json_is_invalid(tmp_path):
    client = PerplexityClient(str(tmp_path), session_cookie="cookie")
    page = _FakePage(
        responses=[
            _FakeResponse(
                "https://www.perplexity.ai/api/auth/session",
                json_error=ValueError("invalid json"),
            ),
        ]
    )

    detection = asyncio.create_task(client._detect_login_state_from_session_response(page))
    await asyncio.sleep(0)
    await page.emit_responses()

    response_seen, payload = await detection

    assert response_seen is True
    assert payload is None
    assert client._is_non_empty_session_payload(payload) is False


@pytest.mark.asyncio
async def test_detect_login_state_from_session_response_times_out_when_request_is_not_seen(tmp_path):
    client = PerplexityClient(str(tmp_path), session_cookie="cookie")
    client.SESSION_RESPONSE_TIMEOUT_MS = 10
    page = _FakePage()

    response_seen, payload = await client._detect_login_state_from_session_response(page)

    assert response_seen is False
    assert payload is None


@pytest.mark.asyncio
async def test_status_returns_unavailable_when_browser_bootstrap_fails(tmp_path, monkeypatch):
    client = PerplexityClient(str(tmp_path), session_cookie="cookie")

    class _FailingAsyncCamoufox:
        def __init__(self, **_kwargs):
            return None

        async def __aenter__(self):
            raise RuntimeError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("polychat.client.perplexity_client.AsyncCamoufox", _FailingAsyncCamoufox)

    status = await client.status()

    assert status["provider"] == "perplexity"
    assert status["is_available"] is False
    assert status["is_logged_in"] is False
    assert "Status check failed: boom" in status["detail"]


def test_resolve_session_cookie_from_cookie_export(tmp_path):
    client = PerplexityClient(str(tmp_path), session_cookie="")

    cookie = client._resolve_session_cookie_from_login_content(
        '[{"name":"__Secure-next-auth.session-token","value":"perplexity-123","domain":".perplexity.ai"}]'
    )

    assert cookie == "perplexity-123"
