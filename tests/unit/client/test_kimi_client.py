from pathlib import Path

import pytest

from polychat.client.kimi_client import KimiClient


def test_load_auth_token_returns_value(tmp_path):
    client = KimiClient(str(tmp_path), auth_token=" kimi-token ")

    assert client._load_auth_token() == "kimi-token"


def test_load_auth_token_raises_when_missing(tmp_path):
    client = KimiClient(str(tmp_path), auth_token="")

    with pytest.raises(ValueError, match="KIMI_AUTH_TOKEN"):
        client._load_auth_token()


def test_load_auth_token_reads_persisted_file(tmp_path):
    client = KimiClient(str(tmp_path), auth_token="")
    Path(client.auth_token_path).write_text("persisted-kimi", encoding="utf-8")

    assert client._load_auth_token() == "persisted-kimi"


def test_resolve_auth_token_from_cookie_export(tmp_path):
    client = KimiClient(str(tmp_path), auth_token="")

    auth_token = client._resolve_auth_token_from_login_content(
        '[{"name":"kimi-auth","value":"kimi-123","domain":".kimi.com"}]'
    )

    assert auth_token == "kimi-123"


def test_build_auth_cookie_uses_expected_name_and_domain():
    cookie = KimiClient._build_auth_cookie("token-123")

    assert cookie["name"] == "kimi-auth"
    assert cookie["value"] == "token-123"
    assert cookie["domain"] == ".kimi.com"
