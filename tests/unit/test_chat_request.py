import pytest
from pydantic import ValidationError

from polychat.model.chat_request import ChatRequest


def test_chat_request_accepts_chat_id():
    payload = ChatRequest(message="hello", chat_id="abc", type=True)
    assert payload.chat_id == "abc"


def test_chat_request_rejects_chat_slug():
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", chat_slug="legacy")
