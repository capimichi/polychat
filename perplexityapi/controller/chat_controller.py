from fastapi import APIRouter, HTTPException, status
from injector import inject
from perplexityapi.service.chat_service import ChatService
from perplexityapi.model.chat_request import ChatRequest
from perplexityapi.model.perplexity_response import PerplexityResponse


class ChatController:

    @inject
    def __init__(self, chat_service: ChatService):
        self.chat_service = chat_service
        self.router = APIRouter(prefix="/chats", tags=["Chats"])
        self._register_routes()

    def _register_routes(self):
        """Register routes for the controller"""
        self.router.add_api_route("", self.ask_perplexity, methods=["POST"])

    async def ask_perplexity(self, request: ChatRequest) -> PerplexityResponse:
        """
        Ask a question to Perplexity AI.

        Args:
            request: ChatRequest with message and optional chat_slug

        Returns:
            PerplexityResponse with complete Perplexity data
        """
        try:
            perplexity_response = await self.chat_service.ask(request.message, request.chat_slug)
            return perplexity_response
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing request: {str(e)}"
            )