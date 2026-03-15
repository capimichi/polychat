import pytest

from polychat.controller.perplexity_controller import PerplexityController
from polychat.mapper.service.chat_to_api_mapper import ChatToApiMapper
from polychat.model.chat_request import ChatRequest
from polychat.model.service.chat import Chat
from polychat.model.service.chat_metadata import ChatMetadata


class _FakePerplexityService:
    def __init__(self):
        self.login_content = None

    async def ask(self, message: str, chat_id: str | None = None, type_input: bool = True) -> Chat:
        return Chat(id="chat-123", message="", metadata=ChatMetadata(provider="perplexity"))

    async def ask_and_wait(self, message: str, chat_id: str | None = None, type_input: bool = True) -> Chat:
        return Chat(id="chat-123", message="answer", image_url="https://img.test/x.png", metadata=ChatMetadata(provider="perplexity"))

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

    async def login(self, content: str) -> None:
        self.login_content = content


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


@pytest.mark.asyncio
async def test_create_chat_and_wait_returns_complete_payload():
    controller = PerplexityController(_FakePerplexityService(), ChatToApiMapper())

    response = await controller.create_chat_and_wait(ChatRequest(message="hello", chat_id="x"))

    assert response.chat_id == "chat-123"
    assert response.message == "answer"
    assert response.image_url == "https://img.test/x.png"


@pytest.mark.asyncio
async def test_login_delegates_to_service():
    service = _FakePerplexityService()
    controller = PerplexityController(service, ChatToApiMapper())

    response = await controller.login(type("Req", (), {"content": "cookie-123"})())

    assert response == {"status": "ok"}
    assert service.login_content == "cookie-123"
