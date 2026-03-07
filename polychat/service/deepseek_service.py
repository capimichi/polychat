from typing import Optional

from injector import inject

from polychat.client.deepseek_client import DeepseekClient
from polychat.mapper.client.deepseek_chat_mapper import DeepseekChatMapper
from polychat.model.service.chat import Chat


class DeepseekService:

    @inject
    def __init__(self, deepseek_client: DeepseekClient, deepseek_chat_mapper: DeepseekChatMapper):
        self.deepseek_client = deepseek_client
        self.deepseek_chat_mapper = deepseek_chat_mapper

    def logout(self) -> None:
        self.deepseek_client.logout()

    async def status(self) -> dict:
        return await self.deepseek_client.status()

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> Chat:
        try:
            response = await self.deepseek_client.ask(message, chat_id, type_input=type_input)
            return self.deepseek_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error asking Deepseek: {exc}")

    async def get_conversation(self, chat_id: str) -> Chat:
        try:
            response = await self.deepseek_client.get_conversation(chat_id)
            return self.deepseek_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error fetching Deepseek conversation: {exc}")
