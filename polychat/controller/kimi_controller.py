from fastapi import APIRouter, HTTPException, status
from injector import inject

from polychat.model import ChatRequest, ChatResponse
from polychat.service.kimi_service import KimiService


class KimiController:
    """Controller per le chat con Kimi."""

    @inject
    def __init__(self, kimi_service: KimiService):
        self.kimi_service = kimi_service
        self.router = APIRouter(prefix="/kimi/chats", tags=["Kimi Chats"])
        self._register_routes()

    def _register_routes(self):
        """Register Kimi routes."""
        self.router.add_api_route(
            "",
            self.create_chat,
            methods=["POST"],
            summary="Invia un messaggio a Kimi",
            response_model=ChatResponse,
        )

    async def create_chat(self, request: ChatRequest) -> ChatResponse:
        """Invia un messaggio a Kimi e restituisce la risposta."""
        try:
            return await self.kimi_service.ask(request.message, type_input=request.type)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Kimi request: {exc}",
            )
