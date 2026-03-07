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

    async def status(self) -> dict:
        return await self.chatgpt_client.status()

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> Chat:
        """Invia una domanda a ChatGPT e restituisce l'output come Chat."""
        try:
            result = await self.chatgpt_client.ask(message, chat_id, type_input=type_input)
            return self.chatgpt_chat_mapper.create_from(result)
        except Exception as exc:
            raise Exception(f"Error asking ChatGPT: {exc}")

    async def get_conversation(self, chat_id: str) -> Chat:
        """Recupera i dettagli di una conversazione ChatGPT."""
        try:
            detail = await self.chatgpt_client.get_conversation(chat_id)
            return self.chatgpt_chat_mapper.create_from(detail)
        except Exception as exc:
            raise Exception(f"Error fetching ChatGPT conversation: {exc}")

    def proxy_download(self, download_url: str) -> tuple[bytes, int, str, str]:
        """Proxy download file ChatGPT usando cookie di sessione."""
        try:
            return self.chatgpt_client.proxy_download(download_url)
        except Exception as exc:
            raise Exception(f"Error proxying ChatGPT download: {exc}")
