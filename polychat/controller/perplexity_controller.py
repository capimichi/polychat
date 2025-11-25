from fastapi import APIRouter, HTTPException, status
from injector import inject

from polychat.model.chat_request import ChatRequest
from polychat.model.perplexity_response import PerplexityResponse
from polychat.service.perplexity_service import PerplexityService


class PerplexityController:
    """Controller for Perplexity-specific chat endpoints."""

    @inject
    def __init__(self, perplexity_service: PerplexityService):
        self.perplexity_service = perplexity_service
        self.router = APIRouter(prefix="/perplexity/chats", tags=["Perplexity Chats"])
        self._register_routes()

    def _register_routes(self):
        """Register Perplexity routes."""
        self.router.add_api_route(
            "",
            self.create_chat,
            methods=["POST"],
            summary="Send a message to Perplexity",
        )

    async def create_chat(self, request: ChatRequest) -> PerplexityResponse:
        """Send a chat message to Perplexity."""
        try:
            return await self.perplexity_service.ask(request.message, request.chat_slug)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing request: {str(e)}",
            )
