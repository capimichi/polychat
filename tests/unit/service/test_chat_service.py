import pytest

from polychat.mapper.client.perplexity_chat_mapper import PerplexityChatMapper
from polychat.service.perplexity_service import PerplexityService
from tests.fakes.fake_perplexity_client import FakePerplexityClient
from tests.fakes.perplexity_response_factory import make_perplexity_response


@pytest.mark.asyncio
async def test_perplexity_service_delegates_to_client():
    fake_client = FakePerplexityClient(make_perplexity_response(answer="ok"))
    service = PerplexityService(fake_client, PerplexityChatMapper())

    response = await service.ask("hello", chat_id="chat-123")

    assert fake_client.calls == [("hello", "chat-123", True)]
    assert response.id == "backend-uuid"


@pytest.mark.asyncio
async def test_perplexity_service_login_sets_flag():
    fake_client = FakePerplexityClient()
    service = PerplexityService(fake_client, PerplexityChatMapper())

    await service.login("cookie")

    assert fake_client.logged_in is True
