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
