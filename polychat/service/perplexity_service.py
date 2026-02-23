from typing import Optional
from injector import inject
from polychat.client.perplexity_client import PerplexityClient
from polychat.mapper.client.perplexity_chat_mapper import PerplexityChatMapper
from polychat.model.service.chat import Chat


class PerplexityService:

    @inject
    def __init__(self, perplexity_client: PerplexityClient, perplexity_chat_mapper: PerplexityChatMapper):
        self.perplexity_client = perplexity_client
        self.perplexity_chat_mapper = perplexity_chat_mapper

    async def login(self, session_cookie: str) -> None:
        """Salva il cookie di sessione Perplexity."""
        try:
            await self.perplexity_client.login(session_cookie)
        except Exception as e:
            raise Exception(f"Error during Perplexity login: {str(e)}")

    async def ask(self, message: str, chat_slug: Optional[str] = None, type_input: bool = True) -> Chat:
        """Ask a question to Perplexity AI and return a Chat."""
        try:
            response = await self.perplexity_client.ask(message, chat_slug, type_input=type_input)
            return self.perplexity_chat_mapper.create_from(response)
        except Exception as e:
            raise Exception(f"Error asking Perplexity: {str(e)}")

    async def get_conversation(self, conversation_id: str) -> Chat:
        """Recupera la conversazione Perplexity a partire dallo slug."""
        try:
            response = await self.perplexity_client.get_conversation(conversation_id)
            return self.perplexity_chat_mapper.create_from(response)
        except Exception as e:
            raise Exception(f"Error fetching Perplexity conversation: {str(e)}")
