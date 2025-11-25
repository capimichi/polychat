from typing import Optional
from injector import inject
from polychat.client.perplexity_client import PerplexityClient
from polychat.model.perplexity_response import PerplexityResponse


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

    async def ask(self, message: str, chat_slug: Optional[str] = None) -> PerplexityResponse:
        """
        Ask a question to Perplexity AI.

        Args:
            message: The question/message to ask
            chat_slug: Optional chat slug to continue an existing conversation

        Returns:
            PerplexityResponse with complete Perplexity data
        """
        try:
            response = await self.perplexity_client.ask(message, chat_slug)
            return response
        except Exception as e:
            raise Exception(f"Error asking Perplexity: {str(e)}")
