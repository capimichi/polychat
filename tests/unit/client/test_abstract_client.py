import asyncio

import requests

from polychat.client.abstract_client import AbstractClient


class _FakePage:
    def __init__(self):
        self.handlers = {}
        self.last_goto = None

    def on(self, event_name, handler):
        self.handlers[event_name] = handler

    async def goto(self, url: str, **kwargs):
        self.last_goto = (url, kwargs)
        return "ok"


class _FakeRequest:
    def __init__(self, method: str, url: str):
        self.method = method
        self.url = url


def test_attach_page_request_logger_logs_method_and_url(caplog):
    client = AbstractClient()
    page = _FakePage()
    caplog.set_level("INFO", logger="polychat.http")

    client._attach_page_request_logger(page)
    page.handlers["request"](_FakeRequest("POST", "https://example.com/path"))

    assert "POST https://example.com/path" in caplog.text


def test_goto_logs_get_url(caplog):
    client = AbstractClient()
    page = _FakePage()
    caplog.set_level("INFO", logger="polychat.http")

    asyncio.run(client._goto(page, "https://example.com/home", wait_until="domcontentloaded"))

    assert page.last_goto == ("https://example.com/home", {"wait_until": "domcontentloaded"})
    assert "GET https://example.com/home" in caplog.text


def test_requests_request_logs_method_and_url(caplog, monkeypatch):
    client = AbstractClient()
    caplog.set_level("INFO", logger="polychat.http")

    captured = {}

    def _fake_request(self, method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["kwargs"] = kwargs

        class _Response:
            status_code = 200

        return _Response()

    monkeypatch.setattr(requests.Session, "request", _fake_request)

    with requests.Session() as session:
        client._requests_request(session, "post", "https://example.com/api", timeout=3)

    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.com/api"
    assert captured["kwargs"] == {"timeout": 3}
    assert "POST https://example.com/api" in caplog.text
