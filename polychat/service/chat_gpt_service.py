from typing import Optional

from injector import inject

from polychat.client.chat_gpt_client import ChatGptClient
from polychat.model import ChatResponse
from polychat.model.chatgpt import ConversationDetail


class ChatGptService:

    @inject
    def __init__(self, chatgpt_client: ChatGptClient):
        self.chatgpt_client = chatgpt_client

    async def login(self, session_cookie: str) -> None:
        """Salva il cookie di sessione per ChatGPT tramite il client."""
        await self.chatgpt_client.login(session_cookie)

    def logout(self) -> None:
        """Rimuove la sessione ChatGPT salvata."""
        self.chatgpt_client.logout()

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> ChatResponse:
        """Invia una domanda a ChatGPT e restituisce l'output come ChatResponse."""
        try:
            return await self.chatgpt_client.ask(message, chat_id, type_input=type_input)
        except Exception as exc:
            raise Exception(f"Error asking ChatGPT: {exc}")

    async def get_conversation(self, conversation_id: str) -> ConversationDetail:
        """Recupera i dettagli di una conversazione ChatGPT."""
        try:
            return await self.chatgpt_client.get_conversation(conversation_id)
        except Exception as exc:
            raise Exception(f"Error fetching ChatGPT conversation: {exc}")
