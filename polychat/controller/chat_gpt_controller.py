from fastapi import APIRouter, HTTPException, status
from injector import inject

from polychat.model import ChatResponse, ChatRequest
from polychat.service.chat_gpt_service import ChatGptService


class ChatGptController:
    """Controller per le chat con ChatGPT."""

    @inject
    def __init__(self, chatgpt_service: ChatGptService):
        self.chatgpt_service = chatgpt_service
        self.router = APIRouter(prefix="/chatgpt/chats", tags=["ChatGPT Chats"])
        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route(
            "",
            self.create_chat,
            methods=["POST"],
            summary="Invia un messaggio a ChatGPT",
            response_model=ChatResponse,
        )

    async def create_chat(self, request: ChatRequest) -> ChatResponse:
        """Invia un messaggio a ChatGPT e restituisce il testo generato."""
        try:
            return await self.chatgpt_service.ask(
                request.message,
                request.chat_slug,
                type_input=request.type,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing ChatGPT request: {exc}",
            )
