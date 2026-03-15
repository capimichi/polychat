import pytest

from polychat.mapper.client.chatgpt_chat_mapper import ChatGptChatMapper
from polychat.mapper.client.deepseek_chat_mapper import DeepseekChatMapper
from polychat.mapper.client.gemini_chat_mapper import GeminiChatMapper
from polychat.mapper.client.kimi_chat_mapper import KimiChatMapper
from polychat.mapper.client.qwen_chat_mapper import QwenChatMapper
from polychat.model.client.chatgpt_conversation_detail import (
    ConversationAuthor,
    ConversationContent,
    ConversationDetail,
    ConversationMappingNode,
    ConversationMessage,
)
from polychat.model.client.deepseek_response import DeepseekResponse
from polychat.model.client.gemini_response import GeminiResponse
from polychat.model.client.kimi_response import KimiResponse
from polychat.model.client.qwen_response import QwenResponse
from polychat.service.chat_gpt_service import ChatGptService
from polychat.service.deepseek_service import DeepseekService
from polychat.service.gemini_service import GeminiService
from polychat.service.kimi_service import KimiService
from polychat.service.qwen_service import QwenService


class _FakeDeepseekClient:
    def __init__(self):
        self.calls = []
        self.conversation_calls = []

    async def ask_and_wait(self, message: str, chat_id: str | None = None, type_input: bool = True) -> DeepseekResponse:
        self.calls.append((message, chat_id, type_input))
        return DeepseekResponse(chat_id="deepseek-chat", message="done")

    async def get_conversation(self, chat_id: str) -> DeepseekResponse:
        self.conversation_calls.append(chat_id)
        return DeepseekResponse(chat_id=chat_id, message="done")


class _FakeGeminiClient:
    def __init__(self):
        self.calls = []
        self.conversation_calls = []

    async def ask_and_wait(self, message: str, chat_id: str | None = None, type_input: bool = True) -> GeminiResponse:
        self.calls.append((message, chat_id, type_input))
        return GeminiResponse(chat_id="gemini-chat", message="done")

    async def get_conversation(self, chat_id: str) -> GeminiResponse:
        self.conversation_calls.append(chat_id)
        return GeminiResponse(chat_id=chat_id, message="done")


class _FakeKimiClient:
    def __init__(self):
        self.calls = []
        self.conversation_calls = []

    async def ask_and_wait(self, message: str, chat_id: str | None = None, type_input: bool = True) -> KimiResponse:
        self.calls.append((message, chat_id, type_input))
        return KimiResponse(chat_id="kimi-chat", message="<p>done</p>")

    async def get_conversation(self, chat_id: str) -> KimiResponse:
        self.conversation_calls.append(chat_id)
        return KimiResponse(chat_id=chat_id, message="<p>done</p>")


class _FakeQwenClient:
    def __init__(self):
        self.calls = []
        self.conversation_calls = []

    async def ask_and_wait(self, message: str, chat_id: str | None = None, type_input: bool = True) -> QwenResponse:
        self.calls.append((message, chat_id, type_input))
        return QwenResponse(
            success=True,
            request_id="req-1",
            data={
                "id": "qwen-chat",
                "title": "Qwen",
                "chat": {
                    "history": {
                        "currentId": "assistant-1",
                        "messages": {
                            "assistant-1": {
                                "role": "assistant",
                                "done": True,
                                "content": "done",
                            }
                        },
                    },
                },
            },
        )

    async def get_conversation(self, chat_id: str) -> QwenResponse:
        self.conversation_calls.append(chat_id)
        return await self.ask_and_wait("ignored", chat_id)


class _FakeChatGptClient:
    def __init__(self):
        self.calls = []
        self.conversation_calls = []

    async def ask_and_wait(self, message: str, chat_id: str | None = None, type_input: bool = True) -> ConversationDetail:
        self.calls.append((message, chat_id, type_input))
        assistant_message = ConversationMessage(
            id="assistant-message",
            author=ConversationAuthor(role="assistant"),
            content=ConversationContent(content_type="text", parts=["done"]),
            create_time=1.0,
        )
        return ConversationDetail(
            conversation_id="chatgpt-chat",
            current_node="assistant-node",
            mapping={
                "assistant-node": ConversationMappingNode(
                    id="assistant-node",
                    message=assistant_message,
                    parent="user-node",
                    children=[],
                )
            },
            default_model_slug="gpt-test",
        )

    async def get_conversation(self, chat_id: str) -> ConversationDetail:
        self.conversation_calls.append(chat_id)
        return await self.ask_and_wait("ignored", chat_id)


@pytest.mark.asyncio
async def test_deepseek_service_ask_and_wait_uses_single_client_flow():
    client = _FakeDeepseekClient()
    service = DeepseekService(client, DeepseekChatMapper())

    response = await service.ask_and_wait("hello", chat_id="chat-1")

    assert client.calls == [("hello", "chat-1", True)]
    assert client.conversation_calls == []
    assert response.id == "deepseek-chat"
    assert response.message == "done"


@pytest.mark.asyncio
async def test_gemini_service_ask_and_wait_uses_single_client_flow():
    client = _FakeGeminiClient()
    service = GeminiService(client, GeminiChatMapper())

    response = await service.ask_and_wait("hello", chat_id="chat-1")

    assert client.calls == [("hello", "chat-1", True)]
    assert client.conversation_calls == []
    assert response.id == "gemini-chat"
    assert response.message == "done"


@pytest.mark.asyncio
async def test_kimi_service_ask_and_wait_uses_single_client_flow():
    client = _FakeKimiClient()
    service = KimiService(client, KimiChatMapper())

    response = await service.ask_and_wait("hello", chat_id="chat-1")

    assert client.calls == [("hello", "chat-1", True)]
    assert client.conversation_calls == []
    assert response.id == "kimi-chat"
    assert response.message == "<p>done</p>"


@pytest.mark.asyncio
async def test_qwen_service_ask_and_wait_uses_single_client_flow():
    client = _FakeQwenClient()
    service = QwenService(client, QwenChatMapper())

    response = await service.ask_and_wait("hello", chat_id="chat-1")

    assert client.calls == [("hello", "chat-1", True)]
    assert client.conversation_calls == []
    assert response.id == "qwen-chat"
    assert response.message == "done"


@pytest.mark.asyncio
async def test_chatgpt_service_ask_and_wait_uses_single_client_flow():
    client = _FakeChatGptClient()
    service = ChatGptService(client, ChatGptChatMapper())

    response = await service.ask_and_wait("hello", chat_id="chat-1")

    assert client.calls == [("hello", "chat-1", True)]
    assert client.conversation_calls == []
    assert response.id == "chatgpt-chat"
    assert response.message == "done"
