from fastapi import APIRouter, HTTPException, status
from injector import inject

from polychat.mapper.service.chat_to_api_mapper import ChatToApiMapper
from polychat.model.api.chat_response import (
    ChannelStatusResponse,
    ChatCompleteResponse,
    ChatMessageResponse,
    ChatStartResponse,
)
from polychat.model.api.login_request import LoginRequest
from polychat.model.chat_request import ChatRequest
from polychat.service.deepseek_service import DeepseekService


class DeepseekController:
    """Controller per le chat con Deepseek."""

    @inject
    def __init__(self, deepseek_service: DeepseekService, chat_to_api_mapper: ChatToApiMapper):
        self.deepseek_service = deepseek_service
        self.chat_to_api_mapper = chat_to_api_mapper
        self.router = APIRouter(prefix="/deepseek/chats", tags=["Deepseek Chats"])
        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route(
            "",
            self.create_chat,
            methods=["POST"],
            summary="Invia un messaggio a Deepseek",
            response_model=ChatStartResponse,
        )
        self.router.add_api_route(
            "/complete",
            self.create_chat_and_wait,
            methods=["POST"],
            summary="Invia un messaggio a Deepseek e attende la risposta finale",
            response_model=ChatCompleteResponse,
        )
        self.router.add_api_route(
            "/login",
            self.login,
            methods=["POST"],
            summary="Login Deepseek",
        )
        self.router.add_api_route(
            "/logout",
            self.logout,
            methods=["POST"],
            summary="Logout Deepseek",
        )
        self.router.add_api_route(
            "/status",
            self.get_status,
            methods=["GET"],
            summary="Status Deepseek",
            response_model=ChannelStatusResponse,
        )
        self.router.add_api_route(
            "/{chat_id}",
            self.get_chat_response,
            methods=["GET"],
            summary="Recupera una conversazione Deepseek",
            response_model=ChatMessageResponse,
        )

    async def create_chat(self, request: ChatRequest) -> ChatStartResponse:
        try:
            chat = await self.deepseek_service.ask(
                request.message,
                request.chat_id,
                type_input=request.type,
            )
            return self.chat_to_api_mapper.create_start_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Deepseek request: {exc}",
            )

    async def get_chat_response(self, chat_id: str) -> ChatMessageResponse:
        try:
            chat = await self.deepseek_service.get_conversation(chat_id)
            return self.chat_to_api_mapper.create_message_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching Deepseek conversation: {exc}",
            )

    async def create_chat_and_wait(self, request: ChatRequest) -> ChatCompleteResponse:
        try:
            chat = await self.deepseek_service.ask_and_wait(
                request.message,
                request.chat_id,
                type_input=request.type,
            )
            return self.chat_to_api_mapper.create_complete_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing blocking Deepseek request: {exc}",
            )

    def logout(self) -> dict:
        try:
            self.deepseek_service.logout()
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Deepseek logout: {exc}",
            )

    async def get_status(self) -> ChannelStatusResponse:
        try:
            return ChannelStatusResponse.model_validate(await self.deepseek_service.status())
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching Deepseek status: {exc}",
            )

    async def login(self, request: LoginRequest) -> dict:
        try:
            await self.deepseek_service.login(request.content)
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Deepseek login: {exc}",
            )
