from fastapi import APIRouter, HTTPException, status
from injector import inject

from polychat.mapper.service.chat_to_api_mapper import ChatToApiMapper
from polychat.model.chat_request import ChatRequest
from polychat.model.api.chat_response import ChatResponse
from polychat.service.chat_gpt_service import ChatGptService


class ChatGptController:
    """Controller per le chat con ChatGPT."""

    @inject
    def __init__(self, chatgpt_service: ChatGptService, chat_to_api_mapper: ChatToApiMapper):
        self.chatgpt_service = chatgpt_service
        self.chat_to_api_mapper = chat_to_api_mapper
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
        self.router.add_api_route(
            "/{conversation_id}",
            self.get_chat_response,
            methods=["GET"],
            summary="Recupera una conversazione ChatGPT",
            response_model=ChatResponse,
        )
        self.router.add_api_route(
            "/logout",
            self.logout,
            methods=["POST"],
            summary="Logout ChatGPT",
        )

    async def create_chat(self, request: ChatRequest) -> ChatResponse:
        """Invia un messaggio a ChatGPT e restituisce il testo generato."""
        try:
            chat = await self.chatgpt_service.ask(
                request.message,
                request.chat_slug,
                type_input=request.type,
            )
            return self.chat_to_api_mapper.create_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing ChatGPT request: {exc}",
            )

    async def get_chat_response(self, conversation_id: str) -> ChatResponse:
        """Recupera la risposta di ChatGPT a partire dall'ID conversazione."""
        try:
            chat = await self.chatgpt_service.get_conversation(conversation_id)
            return self.chat_to_api_mapper.create_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching ChatGPT conversation: {exc}",
            )

    def logout(self) -> dict:
        """Logout ChatGPT (rimuove cookie e storage state)."""
        try:
            self.chatgpt_service.logout()
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing ChatGPT logout: {exc}",
            )
