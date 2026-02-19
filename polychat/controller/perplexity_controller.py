from fastapi import APIRouter, HTTPException, status
from injector import inject

from polychat.model.chat_request import ChatRequest
from polychat.mapper.service.chat_to_api_mapper import ChatToApiMapper
from polychat.model.api.chat_response import ChatResponse
from polychat.service.perplexity_service import PerplexityService


class PerplexityController:
    """Controller for Perplexity-specific chat endpoints."""

    @inject
    def __init__(self, perplexity_service: PerplexityService, chat_to_api_mapper: ChatToApiMapper):
        self.perplexity_service = perplexity_service
        self.chat_to_api_mapper = chat_to_api_mapper
        self.router = APIRouter(prefix="/perplexity/chats", tags=["Perplexity Chats"])
        self._register_routes()

    def _register_routes(self):
        """Register Perplexity routes."""
        self.router.add_api_route(
            "",
            self.create_chat,
            methods=["POST"],
            summary="Send a message to Perplexity",
            response_model=ChatResponse,
        )

    async def create_chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat message to Perplexity."""
        try:
            chat = await self.perplexity_service.ask(
                request.message,
                request.chat_slug,
                type_input=request.type,
            )
            return self.chat_to_api_mapper.create_from(chat)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing request: {str(e)}",
            )
