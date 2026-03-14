import pytest

from polychat.mapper.client.perplexity_chat_mapper import PerplexityChatMapper
from polychat.service.perplexity_service import PerplexityService
from polychat.service.chat_waiter import ChatWaitTimeoutError, ChatWaiter
from polychat.model.service.chat import Chat
from polychat.model.service.chat_metadata import ChatMetadata
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


@pytest.mark.asyncio
async def test_perplexity_service_ask_and_wait_polls_until_message_available():
    fake_client = FakePerplexityClient(
        response=make_perplexity_response(answer=""),
        conversation_response=make_perplexity_response(answer="done"),
    )
    service = PerplexityService(fake_client, PerplexityChatMapper())

    response = await service.ask_and_wait("hello", chat_id="chat-123")

    assert fake_client.calls == [("hello", "chat-123", True)]
    assert fake_client.conversation_calls == ["backend-uuid"]
    assert response.id == "backend-uuid"
    assert response.message == "done"


@pytest.mark.asyncio
async def test_chat_waiter_raises_timeout_when_chat_never_completes():
    pending_chat = Chat(
        id="chat-123",
        message="",
        metadata=ChatMetadata(provider="perplexity"),
    )

    async def _fetch(_: str) -> Chat:
        return pending_chat

    with pytest.raises(ChatWaitTimeoutError):
        await ChatWaiter.wait_for_completion(
            pending_chat,
            _fetch,
            timeout_seconds=0.01,
            poll_interval_seconds=0.01,
        )
