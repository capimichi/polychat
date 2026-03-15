import pytest

from polychat.client.kimi_client import KimiClient


def test_load_auth_token_returns_value(tmp_path):
    client = KimiClient(str(tmp_path), auth_token=" kimi-token ")

    assert client._load_auth_token() == "kimi-token"


def test_load_auth_token_raises_when_missing(tmp_path):
    client = KimiClient(str(tmp_path), auth_token="")

    with pytest.raises(ValueError, match="KIMI_AUTH_TOKEN"):
        client._load_auth_token()


def test_build_auth_cookie_uses_expected_name_and_domain():
    cookie = KimiClient._build_auth_cookie("token-123")

    assert cookie["name"] == "kimi-auth"
    assert cookie["value"] == "token-123"
    assert cookie["domain"] == ".kimi.com"
