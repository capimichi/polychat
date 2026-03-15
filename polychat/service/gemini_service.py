from typing import Optional

from injector import inject

from polychat.client.gemini_client import GeminiClient
from polychat.mapper.client.gemini_chat_mapper import GeminiChatMapper
from polychat.model.service.chat import Chat


class GeminiService:

    @inject
    def __init__(self, gemini_client: GeminiClient, gemini_chat_mapper: GeminiChatMapper):
        self.gemini_client = gemini_client
        self.gemini_chat_mapper = gemini_chat_mapper

    def logout(self) -> None:
        self.gemini_client.logout()

    async def status(self) -> dict:
        return await self.gemini_client.status()

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> Chat:
        try:
            response = await self.gemini_client.ask(message, chat_id, type_input=type_input)
            return self.gemini_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error asking Gemini: {exc}")

    async def get_conversation(self, chat_id: str) -> Chat:
        try:
            response = await self.gemini_client.get_conversation(chat_id)
            return self.gemini_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error fetching Gemini conversation: {exc}")

    async def ask_and_wait(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> Chat:
        try:
            response = await self.gemini_client.ask_and_wait(message, chat_id, type_input=type_input)
            return self.gemini_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error asking Gemini and waiting for completion: {exc}")
