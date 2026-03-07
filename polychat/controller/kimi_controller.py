from fastapi import APIRouter, HTTPException, status
from injector import inject

from polychat.mapper.service.chat_to_api_mapper import ChatToApiMapper
from polychat.model.chat_request import ChatRequest
from polychat.model.api.chat_response import ChannelStatusResponse, ChatMessageResponse, ChatStartResponse
from polychat.service.kimi_service import KimiService


class KimiController:
    """Controller per le chat con Kimi."""

    @inject
    def __init__(self, kimi_service: KimiService, chat_to_api_mapper: ChatToApiMapper):
        self.kimi_service = kimi_service
        self.chat_to_api_mapper = chat_to_api_mapper
        self.router = APIRouter(prefix="/kimi/chats", tags=["Kimi Chats"])
        self._register_routes()

    def _register_routes(self):
        """Register Kimi routes."""
        self.router.add_api_route(
            "",
            self.create_chat,
            methods=["POST"],
            summary="Invia un messaggio a Kimi",
            response_model=ChatStartResponse,
        )
        self.router.add_api_route(
            "/logout",
            self.logout,
            methods=["POST"],
            summary="Logout Kimi",
        )
        self.router.add_api_route(
            "/status",
            self.get_status,
            methods=["GET"],
            summary="Status Kimi",
            response_model=ChannelStatusResponse,
        )
        self.router.add_api_route(
            "/{chat_id}",
            self.get_chat_response,
            methods=["GET"],
            summary="Recupera una conversazione Kimi",
            response_model=ChatMessageResponse,
        )

    async def create_chat(self, request: ChatRequest) -> ChatStartResponse:
        """Invia un messaggio a Kimi e restituisce la risposta."""
        try:
            chat = await self.kimi_service.ask(request.message, request.chat_id, type_input=request.type)
            return self.chat_to_api_mapper.create_start_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Kimi request: {exc}",
            )

    async def get_chat_response(self, chat_id: str) -> ChatMessageResponse:
        try:
            chat = await self.kimi_service.get_conversation(chat_id)
            return self.chat_to_api_mapper.create_message_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching Kimi conversation: {exc}",
            )

    def logout(self) -> dict:
        try:
            self.kimi_service.logout()
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Kimi logout: {exc}",
            )

    async def get_status(self) -> ChannelStatusResponse:
        try:
            return ChannelStatusResponse.model_validate(await self.kimi_service.status())
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching Kimi status: {exc}",
            )
