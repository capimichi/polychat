from typing import Optional
from injector import inject
from polychat.client.perplexity_client import PerplexityClient
from polychat.model import ChatResponse


class PerplexityService:

    @inject
    def __init__(self, perplexity_client: PerplexityClient):
        self.perplexity_client = perplexity_client

    async def login(self):
        """
        Perform login to Perplexity AI.
        Opens browser and waits 45 seconds for manual login.
        """
        try:
            await self.perplexity_client.login()
        except Exception as e:
            raise Exception(f"Error during Perplexity login: {str(e)}")

    async def ask(self, message: str, chat_slug: Optional[str] = None, type_input: bool = True) -> ChatResponse:
        """Ask a question to Perplexity AI and return a ChatResponse."""
        try:
            response = await self.perplexity_client.ask(message, chat_slug, type_input=type_input)
            return response
        except Exception as e:
            raise Exception(f"Error asking Perplexity: {str(e)}")
