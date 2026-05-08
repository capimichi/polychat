import pytest

from polychat.client.kimi_client import KimiClient


def test_load_auth_tokens_returns_values_from_env(tmp_path):
    client = KimiClient(str(tmp_path), access_token=" access-123 ", refresh_token=" refresh-456 ")

    assert client._load_auth_tokens() == ("access-123", "refresh-456")


def test_load_auth_tokens_raises_when_missing(tmp_path):
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")

    with pytest.raises(ValueError, match="KIMI_ACCESS_TOKEN o KIMI_REFRESH_TOKEN"):
        client._load_auth_tokens()


def test_load_auth_tokens_reads_persisted_file(tmp_path):
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")
    client._write_json_file(
        client.tokens_path,
        {"access_token": "persisted-access", "refresh_token": "persisted-refresh"},
    )

    assert client._load_auth_tokens() == ("persisted-access", "persisted-refresh")


def test_load_auth_tokens_raises_when_only_one_env_value_is_present(tmp_path):
    client = KimiClient(str(tmp_path), access_token="access-only", refresh_token="")

    with pytest.raises(ValueError, match="devono essere entrambi valorizzati"):
        client._load_auth_tokens()


def test_resolve_auth_tokens_from_json_payload(tmp_path):
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")

    access_token, refresh_token = client._resolve_auth_tokens_from_login_content(
        '{"access_token":"kimi-access","refresh_token":"kimi-refresh"}'
    )

    assert access_token == "kimi-access"
    assert refresh_token == "kimi-refresh"


def test_resolve_auth_tokens_requires_json_mapping(tmp_path):
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")

    with pytest.raises(ValueError, match="JSON con access_token e refresh_token"):
        client._resolve_auth_tokens_from_login_content("not-json")


def test_validate_auth_tokens_requires_both_fields():
    with pytest.raises(ValueError, match="devono essere entrambi valorizzati"):
        KimiClient._validate_auth_tokens({"access_token": "abc"})


@pytest.mark.asyncio
async def test_set_auth_tokens_script_uses_expected_local_storage_keys(tmp_path):
    class _FakePage:
        def __init__(self):
            self.calls = []

        async def evaluate(self, script, payload):
            self.calls.append((script, payload))

    page = _FakePage()
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")

    await client._set_auth_tokens(page, "a", "b")

    script, payload = page.calls[0]
    assert "localStorage.setItem('access_token'" in script
    assert "localStorage.setItem('refresh_token'" in script
    assert payload == ["a", "b"]


def test_is_logged_in_from_user_name_text_returns_false_for_log_in():
    assert KimiClient._is_logged_in_from_user_name_text("Log In") is False


def test_is_logged_in_from_user_name_text_returns_true_for_logged_user():
    assert KimiClient._is_logged_in_from_user_name_text("Michele") is True


def test_is_logged_in_from_user_name_text_returns_false_for_empty_text():
    assert KimiClient._is_logged_in_from_user_name_text("") is False


def test_clean_message_html_strips_tags_and_minifies_whitespace():
    html = "<div><h1>Hello</h1>\n\n<p>World</p></div>"

    assert KimiClient._clean_message_html(html) == "Hello World"


def test_clean_message_html_returns_empty_for_empty_content():
    assert KimiClient._clean_message_html("") == ""


class _FakeResponse:
    def __init__(self, url, payload):
        self.url = url
        self._payload = payload

    async def json(self):
        return self._payload


class _FakeExpectResponseContext:
    def __init__(self, page, predicate, timeout):
        self.page = page
        self.predicate = predicate
        self.timeout = timeout
        self.value = self._resolve()

    async def _resolve(self):
        self.page.expect_timeouts.append(self.timeout)
        outcome = self.page.response_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert self.predicate(outcome) is True
        return outcome

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConversationPage:
    def __init__(self, response_outcomes):
        self.response_outcomes = list(response_outcomes)
        self.expect_timeouts = []
        self.waited_timeouts = []
        self.reload_calls = 0
        self.reload_kwargs = []
        self.load_state_calls = []

    def expect_response(self, predicate, timeout):
        return _FakeExpectResponseContext(self, predicate, timeout)

    async def reload(self, **kwargs):
        self.reload_calls += 1
        self.reload_kwargs.append(kwargs)

    async def wait_for_timeout(self, timeout):
        self.waited_timeouts.append(timeout)

    async def wait_for_load_state(self, state, timeout):
        self.load_state_calls.append((state, timeout))


@pytest.mark.asyncio
async def test_fetch_conversation_via_page_returns_message_content(tmp_path):
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")
    page = _FakeConversationPage([
        _FakeResponse(
            KimiClient.GET_CHAT_URL,
            {"chat": {"id": "chat-123", "messageContent": "Ciao!"}},
        )
    ])

    result = await client._fetch_conversation_via_page(page, "chat-123")

    assert result == "Ciao!"
    assert page.reload_calls == 0
    assert page.waited_timeouts == [KimiClient.GET_CHAT_WAIT_TIMEOUT_MS]
    assert page.expect_timeouts == [KimiClient.GET_CHAT_WAIT_TIMEOUT_MS]


@pytest.mark.asyncio
async def test_fetch_conversation_via_page_retries_after_timeout_and_refreshes(tmp_path):
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")
    page = _FakeConversationPage([
        TimeoutError("response timeout"),
        _FakeResponse(
            KimiClient.GET_CHAT_URL,
            {"chat": {"id": "chat-123", "messageContent": "Risposta completa"}},
        ),
    ])

    result = await client._fetch_conversation_via_page(page, "chat-123")

    assert result == "Risposta completa"
    assert page.reload_calls == 1
    assert page.waited_timeouts == [
        KimiClient.GET_CHAT_WAIT_TIMEOUT_MS,
        KimiClient.GET_CHAT_WAIT_TIMEOUT_MS,
    ]
    assert page.expect_timeouts == [
        KimiClient.GET_CHAT_WAIT_TIMEOUT_MS,
        KimiClient.GET_CHAT_WAIT_TIMEOUT_MS,
    ]


@pytest.mark.asyncio
async def test_fetch_conversation_via_page_ignores_payload_for_other_chat_id(tmp_path):
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")
    page = _FakeConversationPage([
        _FakeResponse(
            KimiClient.GET_CHAT_URL,
            {"chat": {"id": "chat-other", "messageContent": "Ignora"}},
        ),
        _FakeResponse(
            KimiClient.GET_CHAT_URL,
            {"chat": {"id": "chat-123", "messageContent": "Usa questo"}},
        ),
    ])

    result = await client._fetch_conversation_via_page(page, "chat-123")

    assert result == "Usa questo"
    assert page.reload_calls == 1


@pytest.mark.asyncio
async def test_fetch_conversation_via_page_raises_after_ninety_seconds(tmp_path):
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")
    page = _FakeConversationPage([TimeoutError("response timeout")] * 9)

    with pytest.raises(TimeoutError, match="dopo 90 secondi"):
        await client._fetch_conversation_via_page(page, "chat-123")

    assert page.reload_calls == 8
    assert page.waited_timeouts == [KimiClient.GET_CHAT_WAIT_TIMEOUT_MS] * 9


def test_is_matching_get_chat_response_ignores_query_params():
    assert KimiClient._is_matching_get_chat_response(
        "https://www.kimi.com/apiv2/kimi.gateway.chat.v1.ChatService/GetChat?foo=bar"
    ) is True


def test_extract_message_from_get_chat_payload_returns_matching_message(tmp_path):
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")

    result = client._extract_message_from_get_chat_payload(
        {"chat": {"id": "chat-123", "messageContent": "Hello"}},
        "chat-123",
    )

    assert result == "Hello"


@pytest.mark.asyncio
async def test_get_conversation_uses_backend_fetch_helper(tmp_path, monkeypatch):
    client = KimiClient(str(tmp_path), access_token="access", refresh_token="refresh")

    class _FakePage:
        async def close(self):
            return None

    class _FakeContext:
        async def new_page(self):
            return _FakePage()

        async def close(self):
            return None

    class _FakeBrowser:
        async def new_context(self, **_kwargs):
            return _FakeContext()

    class _FakeAsyncCamoufox:
        def __init__(self, **_kwargs):
            self._browser = _FakeBrowser()

        async def __aenter__(self):
            return self._browser

        async def __aexit__(self, exc_type, exc, tb):
            return False

    bootstrap_calls = []
    fetch_calls = []

    async def _fake_bootstrap(page, url, access_token, refresh_token, **_kwargs):
        bootstrap_calls.append((page, url, access_token, refresh_token))

    async def _fake_fetch(page, chat_id):
        fetch_calls.append((page, chat_id))
        return "Risposta backend"

    monkeypatch.setattr("polychat.client.kimi_client.AsyncCamoufox", _FakeAsyncCamoufox)
    monkeypatch.setattr(client, "_bootstrap_authenticated_page", _fake_bootstrap)
    monkeypatch.setattr(client, "_fetch_conversation_via_page", _fake_fetch)

    result = await client.get_conversation("chat-123")

    assert result.chat_id == "chat-123"
    assert result.message == "Risposta backend"
    assert bootstrap_calls[0][1] == "https://www.kimi.com/chat/chat-123"
    assert fetch_calls[0][1:] == ("chat-123",)


@pytest.mark.asyncio
async def test_ask_and_wait_uses_backend_fetch_helper(tmp_path, monkeypatch):
    client = KimiClient(str(tmp_path), access_token="access", refresh_token="refresh")
    page_waits = []

    class _FakePage:
        async def wait_for_timeout(self, timeout):
            page_waits.append(timeout)

        async def close(self):
            return None

    class _FakeContext:
        async def new_page(self):
            return _FakePage()

        async def close(self):
            return None

    class _FakeBrowser:
        async def new_context(self, **_kwargs):
            return _FakeContext()

    class _FakeAsyncCamoufox:
        def __init__(self, **_kwargs):
            self._browser = _FakeBrowser()

        async def __aenter__(self):
            return self._browser

        async def __aexit__(self, exc_type, exc, tb):
            return False

    submit_calls = []
    open_chat_calls = []
    fetch_calls = []

    async def _fake_submit(page, message, chat_id, type_input, access_token, refresh_token):
        submit_calls.append((page, message, chat_id, type_input, access_token, refresh_token))
        return "chat-123"

    async def _fake_open_chat(page, chat_id):
        open_chat_calls.append((page, chat_id))

    async def _fake_fetch(page, chat_id):
        fetch_calls.append((page, chat_id))
        return "Risposta finale"

    monkeypatch.setattr("polychat.client.kimi_client.AsyncCamoufox", _FakeAsyncCamoufox)
    monkeypatch.setattr(client, "_submit_prompt", _fake_submit)
    monkeypatch.setattr(client, "_open_chat_page", _fake_open_chat)
    monkeypatch.setattr(client, "_fetch_conversation_via_page", _fake_fetch)

    result = await client.ask_and_wait("ciao", chat_id="chat-0")

    assert result.chat_id == "chat-123"
    assert result.message == "Risposta finale"
    assert submit_calls[0][1:] == ("ciao", "chat-0", True, "access", "refresh")
    assert page_waits == [KimiClient.POST_SUBMIT_WAIT_MS]
    assert open_chat_calls[0][1:] == ("chat-123",)
    assert fetch_calls[0][1:] == ("chat-123",)


@pytest.mark.asyncio
async def test_dismiss_later_dialog_clicks_matching_button(tmp_path):
    class _FakeButton:
        def __init__(self, text):
            self.text = text
            self.clicked = False

        async def inner_text(self):
            return self.text

        async def click(self):
            self.clicked = True

    class _FakePage:
        def __init__(self, buttons):
            self.buttons = buttons
            self.waits = []

        async def query_selector_all(self, selector):
            assert selector == ".common-dialog-button"
            return self.buttons

        async def wait_for_timeout(self, timeout):
            self.waits.append(timeout)

    matching_button = _FakeButton("Maybe Later")
    other_button = _FakeButton("No thanks")
    page = _FakePage([other_button, matching_button])
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")

    await client._dismiss_later_dialog_if_present(page)

    assert other_button.clicked is False
    assert matching_button.clicked is True
    assert page.waits == [500]


@pytest.mark.asyncio
async def test_dismiss_later_dialog_does_nothing_when_absent(tmp_path):
    class _FakeButton:
        def __init__(self, text):
            self.text = text
            self.clicked = False

        async def inner_text(self):
            return self.text

        async def click(self):
            self.clicked = True

    class _FakePage:
        def __init__(self, buttons):
            self.buttons = buttons
            self.waits = []

        async def query_selector_all(self, selector):
            assert selector == ".common-dialog-button"
            return self.buttons

        async def wait_for_timeout(self, timeout):
            self.waits.append(timeout)

    buttons = [_FakeButton("Not now"), _FakeButton("Continue")]
    page = _FakePage(buttons)
    client = KimiClient(str(tmp_path), access_token="", refresh_token="")

    await client._dismiss_later_dialog_if_present(page)

    assert all(button.clicked is False for button in buttons)
    assert page.waits == []
