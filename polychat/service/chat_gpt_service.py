from typing import Optional

from injector import inject

from polychat.client.chat_gpt_client import ChatGptClient
from polychat.mapper.client.chatgpt_chat_mapper import ChatGptChatMapper
from polychat.model.service.chat import Chat


class ChatGptService:

    @inject
    def __init__(self, chatgpt_client: ChatGptClient, chatgpt_chat_mapper: ChatGptChatMapper):
        self.chatgpt_client = chatgpt_client
        self.chatgpt_chat_mapper = chatgpt_chat_mapper

    def logout(self) -> None:
        """Rimuove la sessione ChatGPT salvata."""
        self.chatgpt_client.logout()

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> Chat:
        """Invia una domanda a ChatGPT e restituisce l'output come Chat."""
        try:
            result = await self.chatgpt_client.ask(message, chat_id, type_input=type_input)
            return self.chatgpt_chat_mapper.create_from(result)
        except Exception as exc:
            raise Exception(f"Error asking ChatGPT: {exc}")

    async def get_conversation(self, conversation_id: str) -> Chat:
        """Recupera i dettagli di una conversazione ChatGPT."""
        try:
            detail = await self.chatgpt_client.get_conversation(conversation_id)
            return self.chatgpt_chat_mapper.create_from(detail)
        except Exception as exc:
            raise Exception(f"Error fetching ChatGPT conversation: {exc}")
