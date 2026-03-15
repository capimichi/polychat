from pathlib import Path

import pytest

from polychat.client.chat_gpt_client import ChatGptClient


class _FakeKeyboard:
    async def press(self, _key: str) -> None:
        return None

    async def type(self, _content: str) -> None:
        return None

    async def insert_text(self, _content: str) -> None:
        return None


class _FakePage:
    def __init__(self):
        self.url = "https://chatgpt.com/c/test-conversation"
        self.keyboard = _FakeKeyboard()
        self.waited_timeouts = []

    async def goto(self, _url: str, **_kwargs) -> None:
        return None

    async def wait_for_load_state(self, _state: str) -> None:
        return None

    async def wait_for_timeout(self, _timeout: int) -> None:
        self.waited_timeouts.append(_timeout)
        return None

    async def query_selector(self, _selector: str):
        return None

    async def wait_for_selector(self, _selector: str, timeout=None):
        return {"timeout": timeout}

    async def click(self, _selector: str) -> None:
        return None

    async def type(self, _selector: str, _content: str) -> None:
        return None

    async def wait_for_url(self, _pattern: str, timeout: int = 0) -> None:
        return None

    async def screenshot(self, path: str, full_page: bool = True) -> None:
        Path(path).write_bytes(b"image")

    async def close(self) -> None:
        return None

    async def query_selector_all(self, _selector: str):
        return []


class _FakeContext:
    def __init__(self, page: _FakePage):
        self._page = page

    async def add_cookies(self, _cookies) -> None:
        return None

    async def new_page(self) -> _FakePage:
        return self._page

    async def storage_state(self, path: str) -> None:
        Path(path).write_text("{}", encoding="utf-8")

    async def close(self) -> None:
        return None


class _FakeBrowser:
    def __init__(self, page: _FakePage):
        self._context = _FakeContext(page)

    async def new_context(self, **_kwargs) -> _FakeContext:
        return self._context


class _FakeAsyncCamoufox:
    def __init__(self, **_kwargs):
        self._browser = _FakeBrowser(_FakePage())

    async def __aenter__(self) -> _FakeBrowser:
        return self._browser

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeElement:
    def __init__(self, text: str = "", button=None, items=None):
        self._text = text
        self._button = button
        self._items = items or []
        self.clicked = False

    async def inner_text(self) -> str:
        return self._text

    async def query_selector(self, selector: str):
        if selector == "button":
            return self._button
        return None

    async def click(self) -> None:
        self.clicked = True

    async def query_selector_all(self, _selector: str):
        return self._items


class _WorkspacePage:
    def __init__(self, popover, candidates):
        self.popover = popover
        self.candidates = candidates

    async def query_selector(self, selector: str):
        if selector == ".popover":
            return self.popover
        return None

    async def query_selector_all(self, _selector: str):
        return self.candidates

    async def wait_for_timeout(self, _timeout: int) -> None:
        return None


class _OnboardingPage:
    def __init__(self, show_prompt: bool = True, with_other_button: bool = True):
        self.show_prompt = show_prompt
        self.with_other_button = with_other_button
        self.other = _FakeElement("Other")

    async def query_selector(self, selector: str):
        if selector == "text=What kind of work do you do?" and self.show_prompt:
            return _FakeElement("What kind of work do you do?")
        if selector == "button:has-text('Other')" and self.with_other_button:
            return self.other
        return None

    async def query_selector_all(self, _selector: str):
        if self.with_other_button:
            return [self.other]
        return []

    async def wait_for_timeout(self, _timeout: int) -> None:
        return None


class _AppsAtWorkPage:
    def __init__(self, show_prompt: bool = True, with_skip_button: bool = True):
        self.show_prompt = show_prompt
        self.with_skip_button = with_skip_button
        self.skip = _FakeElement("Skip")

    async def query_selector(self, selector: str):
        if selector == "text=Select apps you use at work" and self.show_prompt:
            return _FakeElement("Select apps you use at work")
        if selector == "button:has-text('Skip')" and self.with_skip_button:
            return self.skip
        return None

    async def query_selector_all(self, _selector: str):
        if self.with_skip_button:
            return [self.skip]
        return []

    async def wait_for_timeout(self, _timeout: int) -> None:
        return None


@pytest.mark.asyncio
async def test_ask_raises_when_session_cookie_is_missing(tmp_path):
    client = ChatGptClient(str(tmp_path), session_cookie=" ")

    with pytest.raises(ValueError, match="CHATGPT_SESSION_COOKIE mancante o vuoto"):
        await client.ask("hello")


def test_get_conversations_raises_when_session_cookie_is_missing(tmp_path):
    client = ChatGptClient(str(tmp_path), session_cookie="")

    with pytest.raises(ValueError, match="CHATGPT_SESSION_COOKIE mancante o vuoto"):
        client.get_conversations()


def test_load_session_cookie_reads_persisted_file(tmp_path):
    client = ChatGptClient(str(tmp_path), session_cookie="")
    Path(client.cookie_path).write_text("persisted-cookie", encoding="utf-8")

    assert client._load_session_cookie() == "persisted-cookie"


def test_resolve_session_cookie_from_cookie_export(tmp_path):
    client = ChatGptClient(str(tmp_path), session_cookie="")

    cookie = client._resolve_session_cookie_from_login_content(
        '[{"name":"__Secure-next-auth.session-token","value":"cookie-123","domain":"chatgpt.com"}]'
    )

    assert cookie == "cookie-123"


@pytest.mark.asyncio
async def test_ask_does_not_select_workspace_when_workspace_name_is_empty(tmp_path, monkeypatch):
    client = ChatGptClient(str(tmp_path), session_cookie="cookie", workspace_name="")
    monkeypatch.setattr("polychat.client.chat_gpt_client.AsyncCamoufox", _FakeAsyncCamoufox)

    called = False

    async def _unexpected_call(_page, _workspace_name):
        nonlocal called
        called = True

    monkeypatch.setattr(client, "_select_workspace_by_name", _unexpected_call)

    result = await client.ask("hello")

    assert result.chat_id == "test-conversation"
    assert called is False


@pytest.mark.asyncio
async def test_ask_waits_five_seconds_after_submit_before_close(tmp_path, monkeypatch):
    client = ChatGptClient(str(tmp_path), session_cookie="cookie", workspace_name="")
    page = _FakePage()

    class _TrackingAsyncCamoufox:
        def __init__(self, **_kwargs):
            self._browser = _FakeBrowser(page)

        async def __aenter__(self) -> _FakeBrowser:
            return self._browser

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("polychat.client.chat_gpt_client.AsyncCamoufox", _TrackingAsyncCamoufox)

    await client.ask("hello")

    assert 5_000 in page.waited_timeouts


@pytest.mark.asyncio
async def test_select_workspace_by_name_clicks_matching_workspace(tmp_path):
    client = ChatGptClient(str(tmp_path), session_cookie="cookie", workspace_name="Team Alpha")
    candidate = _FakeElement("  TEAM   alpha ")
    popover = _FakeElement("Seleziona area di lavoro", items=[candidate])
    page = _WorkspacePage(popover, [candidate])

    await client._select_workspace_by_name(page, "Team Alpha")

    assert candidate.clicked is True


@pytest.mark.asyncio
async def test_select_workspace_by_name_returns_when_popover_is_missing(tmp_path):
    client = ChatGptClient(str(tmp_path), session_cookie="cookie", workspace_name="Team Alpha")
    page = _WorkspacePage(None, [])

    await client._select_workspace_by_name(page, "Team Alpha")


@pytest.mark.asyncio
async def test_select_workspace_by_name_raises_when_workspace_missing(tmp_path):
    client = ChatGptClient(str(tmp_path), session_cookie="cookie", workspace_name="Team Alpha")
    popover = _FakeElement("workspace", items=[_FakeElement("Team Beta")])
    page = _WorkspacePage(popover, [_FakeElement("Team Beta")])

    with pytest.raises(Exception, match="Workspace 'Team Alpha' non trovato."):
        await client._select_workspace_by_name(page, "Team Alpha")


@pytest.mark.asyncio
async def test_raise_input_timeout_creates_screenshot_and_hint(tmp_path):
    session_dir = tmp_path / "var" / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    client = ChatGptClient(str(session_dir), session_cookie="cookie")
    page = _FakePage()

    with pytest.raises(TimeoutError, match="CHATGPT_WORKSPACE_NAME"):
        await client._raise_input_timeout(page, TimeoutError("missing input"))

    screenshots = list((tmp_path / "var" / "session" / "screenshots").glob("chatgpt-input-timeout-*.png"))
    assert len(screenshots) == 1


@pytest.mark.asyncio
async def test_ask_creates_screenshot_when_input_interaction_fails(tmp_path, monkeypatch):
    session_dir = tmp_path / "var" / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    client = ChatGptClient(str(session_dir), session_cookie="cookie")
    monkeypatch.setattr("polychat.client.chat_gpt_client.AsyncCamoufox", _FakeAsyncCamoufox)

    async def _broken_type_message(_page, _message):
        raise Exception("element detached from DOM")

    monkeypatch.setattr(client, "_type_into_focused_input", _broken_type_message)

    with pytest.raises(RuntimeError, match="Screenshot creato"):
        await client.ask("hello")

    screenshots = list((tmp_path / "var" / "session" / "screenshots").glob("chatgpt-input-interaction-*.png"))
    assert len(screenshots) == 1


@pytest.mark.asyncio
async def test_try_select_other_work_category_clicks_other(tmp_path):
    client = ChatGptClient(str(tmp_path), session_cookie="cookie")
    page = _OnboardingPage(show_prompt=True, with_other_button=True)

    selected = await client._try_select_other_work_category(page)

    assert selected is True
    assert page.other.clicked is True


@pytest.mark.asyncio
async def test_try_skip_apps_at_work_selection_clicks_skip(tmp_path):
    client = ChatGptClient(str(tmp_path), session_cookie="cookie")
    page = _AppsAtWorkPage(show_prompt=True, with_skip_button=True)

    selected = await client._try_skip_apps_at_work_selection(page)

    assert selected is True
    assert page.skip.clicked is True
