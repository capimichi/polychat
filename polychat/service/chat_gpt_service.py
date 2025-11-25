from typing import Optional

from injector import inject

from polychat.client.chat_gpt_client import ChatGptClient
from polychat.model import ChatResponse


class ChatGptService:

    @inject
    def __init__(self, chatgpt_client: ChatGptClient):
        self.chatgpt_client = chatgpt_client

    async def login(self) -> None:
        """Esegue il login a ChatGPT tramite il client."""
        await self.chatgpt_client.login()

    async def ask(self, message: str, chat_id: Optional[str] = None) -> ChatResponse:
        """Invia una domanda a ChatGPT e restituisce l'output come ChatResponse."""
        try:
            return await self.chatgpt_client.ask(message, chat_id)
        except Exception as exc:
            raise Exception(f"Error asking ChatGPT: {exc}")
