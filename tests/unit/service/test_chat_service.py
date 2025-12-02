import pytest

from polychat.service.chat_service import ChatService
from tests.fakes.fake_perplexity_client import FakePerplexityClient
from tests.fakes.perplexity_response_factory import make_perplexity_response


@pytest.mark.asyncio
async def test_chat_service_delegates_to_client():
    fake_client = FakePerplexityClient(make_perplexity_response(answer="ok"))
    service = ChatService(fake_client)

    response = await service.ask("hello", chat_slug="chat-123")

    assert fake_client.calls == [("hello", "chat-123", True)]
    assert response.answer == "ok"


@pytest.mark.asyncio
async def test_chat_service_login_sets_flag():
    fake_client = FakePerplexityClient()
    service = ChatService(fake_client)

    await service.login()

    assert fake_client.logged_in is True
