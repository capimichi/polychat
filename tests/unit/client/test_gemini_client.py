from pathlib import Path

from polychat.client.gemini_client import GeminiClient


def test_extract_chat_id_from_url():
    chat_id = GeminiClient._extract_chat_id_from_url("https://gemini.google.com/app/e0ccb7f20d4d6c53")
    assert chat_id == "e0ccb7f20d4d6c53"


def test_extract_response_container_id():
    payload = '[["wrb.fr","hNvQHb","[[[[\"c_e0ccb7f20d4d6c53\",\"r_a1a70693a88a0106\"]'  # noqa: E501
    extracted = GeminiClient._extract_response_container_id(payload, "e0ccb7f20d4d6c53")
    assert extracted == "r_a1a70693a88a0106"


def test_load_session_cookies_reads_persisted_file(tmp_path):
    client = GeminiClient(str(tmp_path), cookie_1psid="", cookie_1psidts="")
    Path(client.cookies_path).write_text(
        '{"__Secure-1PSID":"psid","__Secure-1PSIDTS":"psidts"}',
        encoding="utf-8",
    )

    assert client._load_session_cookies() == ("psid", "psidts")


def test_resolve_session_cookies_from_cookie_export(tmp_path):
    client = GeminiClient(str(tmp_path), cookie_1psid="", cookie_1psidts="")

    cookies = client._resolve_session_cookies_from_login_content(
        '[{"name":"__Secure-1PSID","value":"psid"},{"name":"__Secure-1PSIDTS","value":"psidts"}]'
    )

    assert cookies == ("psid", "psidts")
