import pytest

from polychat.controller.perplexity_controller import PerplexityController
from polychat.mapper.service.chat_to_api_mapper import ChatToApiMapper
from polychat.model.chat_request import ChatRequest
from polychat.model.service.chat import Chat
from polychat.model.service.chat_metadata import ChatMetadata


class _FakePerplexityService:
    async def ask(self, message: str, chat_id: str | None = None, type_input: bool = True) -> Chat:
        return Chat(id="chat-123", message="", metadata=ChatMetadata(provider="perplexity"))

    async def get_conversation(self, chat_id: str) -> Chat:
        return Chat(id=chat_id, message="answer", metadata=ChatMetadata(provider="perplexity"))

    def logout(self) -> None:
        return None

    async def status(self) -> dict:
        return {
            "provider": "perplexity",
            "is_available": True,
            "is_logged_in": False,
            "detail": "TODO",
        }


@pytest.mark.asyncio
async def test_create_chat_returns_only_chat_id():
    controller = PerplexityController(_FakePerplexityService(), ChatToApiMapper())

    response = await controller.create_chat(ChatRequest(message="hello", chat_id="x"))

    assert response.chat_id == "chat-123"


@pytest.mark.asyncio
async def test_get_chat_response_returns_message_payload():
    controller = PerplexityController(_FakePerplexityService(), ChatToApiMapper())

    response = await controller.get_chat_response("chat-123")

    assert response.message == "answer"
    assert response.image_url is None
