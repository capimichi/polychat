from typing import Optional

from injector import inject

from polychat.client.qwen_client import QwenClient
from polychat.mapper.client.qwen_chat_mapper import QwenChatMapper
from polychat.model.service.chat import Chat


class QwenService:

    @inject
    def __init__(self, qwen_client: QwenClient, qwen_chat_mapper: QwenChatMapper):
        self.qwen_client = qwen_client
        self.qwen_chat_mapper = qwen_chat_mapper

    def logout(self) -> None:
        self.qwen_client.logout()

    def status(self) -> dict:
        return self.qwen_client.status()

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> Chat:
        try:
            response = await self.qwen_client.ask(message, chat_id, type_input=type_input)
            return self.qwen_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error asking Qwen: {exc}")

    async def get_conversation(self, conversation_id: str) -> Chat:
        try:
            response = await self.qwen_client.get_conversation(conversation_id)
            return self.qwen_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error fetching Qwen conversation: {exc}")
