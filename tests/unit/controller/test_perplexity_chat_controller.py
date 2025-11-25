import pytest
from fastapi import HTTPException

from polychat.controller.perplexity_chat_controller import PerplexityChatController
from polychat.model.chat_request import ChatRequest


@pytest.mark.asyncio
async def test_create_chat_returns_perplexity_response(chat_service, fake_perplexity_client):
    controller = PerplexityChatController(chat_service)
    request = ChatRequest(message="Hi there", chat_slug="slug-1")

    response = await controller.create_chat(request)

    assert response.backend_uuid == "backend-uuid"
    assert response.answer == "hello world"
    assert fake_perplexity_client.calls == [("Hi there", "slug-1")]


@pytest.mark.asyncio
async def test_list_chats_not_implemented(chat_service):
    controller = PerplexityChatController(chat_service)

    with pytest.raises(HTTPException) as exc:
        await controller.list_chats()

    assert exc.value.status_code == 501
