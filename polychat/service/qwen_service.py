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

    async def login(self, content: str) -> None:
        await self.qwen_client.login(content)

    async def status(self) -> dict:
        return await self.qwen_client.status()

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> Chat:
        try:
            response = await self.qwen_client.ask(message, chat_id, type_input=type_input)
            return self.qwen_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error asking Qwen: {exc}")

    async def get_conversation(self, chat_id: str) -> Chat:
        try:
            response = await self.qwen_client.get_conversation(chat_id)
            return self.qwen_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error fetching Qwen conversation: {exc}")

    async def ask_and_wait(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> Chat:
        try:
            response = await self.qwen_client.ask_and_wait(message, chat_id, type_input=type_input)
            return self.qwen_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error asking Qwen and waiting for completion: {exc}")
