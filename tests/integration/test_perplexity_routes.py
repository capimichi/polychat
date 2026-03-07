from fastapi import FastAPI
from fastapi.testclient import TestClient

from polychat.controller.perplexity_controller import PerplexityController
from polychat.mapper.service.chat_to_api_mapper import ChatToApiMapper
from polychat.model.service.chat import Chat
from polychat.model.service.chat_metadata import ChatMetadata


class _FakePerplexityService:
    async def ask(self, message: str, chat_id: str | None = None, type_input: bool = True) -> Chat:
        return Chat(id="chat-abc", message="", metadata=ChatMetadata(provider="perplexity"))

    async def get_conversation(self, chat_id: str) -> Chat:
        return Chat(id=chat_id, message="from fake", metadata=ChatMetadata(provider="perplexity"))

    def logout(self) -> None:
        return None

    async def status(self) -> dict:
        return {
            "provider": "perplexity",
            "is_available": True,
            "is_logged_in": False,
            "detail": "TODO",
        }


def create_test_app():
    controller = PerplexityController(_FakePerplexityService(), ChatToApiMapper())
    app = FastAPI()
    app.include_router(controller.router)
    return app


def test_post_perplexity_chat_returns_start_payload():
    app = create_test_app()
    client = TestClient(app)

    response = client.post("/perplexity/chats", json={"message": "Hello!", "chat_id": None, "type": True})

    assert response.status_code == 200
    assert response.json() == {"chat_id": "chat-abc"}


def test_get_perplexity_chat_returns_message_payload():
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/perplexity/chats/chat-abc")

    assert response.status_code == 200
    assert response.json() == {"message": "from fake", "image_url": None}
