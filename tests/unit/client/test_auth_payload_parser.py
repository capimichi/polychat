import pytest

from polychat.client.auth_payload_parser import AuthPayloadParser


def test_parse_json_cookie_export():
    payload = """
    [
      {
        "domain": ".chatgpt.com",
        "expirationDate": 1778518853.821406,
        "httpOnly": true,
        "name": "__Secure-next-auth.session-token",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": true,
        "value": "token-123"
      }
    ]
    """

    parsed = AuthPayloadParser.parse(payload)

    assert parsed.cookies == [
        {
            "name": "__Secure-next-auth.session-token",
            "value": "token-123",
            "domain": ".chatgpt.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
            "expires": 1778518853,
        }
    ]


def test_parse_netscape_cookie_export():
    payload = """
    # Netscape HTTP Cookie File
    .chat.qwen.ai\tTRUE\t/\tTRUE\t1779826753\ttoken\tqwen-123
    """

    parsed = AuthPayloadParser.parse(payload)

    assert parsed.cookies == [
        {
            "name": "token",
            "value": "qwen-123",
            "domain": ".chat.qwen.ai",
            "path": "/",
            "secure": True,
            "expires": 1779826753,
        }
    ]


def test_parse_raw_text_fallback():
    parsed = AuthPayloadParser.parse("plain-token")

    assert parsed.cookies == []
    assert parsed.raw_text == "plain-token"


def test_parse_invalid_json_raises():
    with pytest.raises(ValueError, match="JSON non valido"):
        AuthPayloadParser.parse('{"broken"')
