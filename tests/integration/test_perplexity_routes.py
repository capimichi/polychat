from fastapi import FastAPI
from fastapi.testclient import TestClient

from polychat.controller.perplexity_chat_controller import PerplexityChatController
from polychat.service.chat_service import ChatService
from tests.fakes.fake_perplexity_client import FakePerplexityClient
from tests.fakes.perplexity_response_factory import make_perplexity_response


def create_test_app():
    fake_client = FakePerplexityClient(make_perplexity_response(answer="from fake"))
    service = ChatService(fake_client)
    controller = PerplexityChatController(service)

    app = FastAPI()
    app.include_router(controller.router)

    return app, fake_client


def test_post_perplexity_chat_returns_payload():
    app, fake_client = create_test_app()
    client = TestClient(app)

    response = client.post("/perplexity/chats", json={"message": "Hello!"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend_uuid"] == "backend-uuid"
    assert payload["answer"] == "from fake"
    assert fake_client.calls == [("Hello!", None)]


def test_get_perplexity_chats_returns_not_implemented():
    app, _ = create_test_app()
    client = TestClient(app)

    response = client.get("/perplexity/chats")

    assert response.status_code == 501
    assert "not implemented" in response.json().get("detail", "").lower()
