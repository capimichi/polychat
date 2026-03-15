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
from polychat.service.qwen_service import QwenService


class QwenController:
    """Controller per le chat con Qwen."""

    @inject
    def __init__(self, qwen_service: QwenService, chat_to_api_mapper: ChatToApiMapper):
        self.qwen_service = qwen_service
        self.chat_to_api_mapper = chat_to_api_mapper
        self.router = APIRouter(prefix="/qwen/chats", tags=["Qwen Chats"])
        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route(
            "",
            self.create_chat,
            methods=["POST"],
            summary="Invia un messaggio a Qwen",
            response_model=ChatStartResponse,
        )
        self.router.add_api_route(
            "/complete",
            self.create_chat_and_wait,
            methods=["POST"],
            summary="Invia un messaggio a Qwen e attende la risposta finale",
            response_model=ChatCompleteResponse,
        )
        self.router.add_api_route(
            "/login",
            self.login,
            methods=["POST"],
            summary="Login Qwen",
        )
        self.router.add_api_route(
            "/logout",
            self.logout,
            methods=["POST"],
            summary="Logout Qwen",
        )
        self.router.add_api_route(
            "/status",
            self.get_status,
            methods=["GET"],
            summary="Status Qwen",
            response_model=ChannelStatusResponse,
        )
        self.router.add_api_route(
            "/{chat_id}",
            self.get_chat_response,
            methods=["GET"],
            summary="Recupera una conversazione Qwen",
            response_model=ChatMessageResponse,
        )

    async def create_chat(self, request: ChatRequest) -> ChatStartResponse:
        try:
            chat = await self.qwen_service.ask(
                request.message,
                request.chat_id,
                type_input=request.type,
            )
            return self.chat_to_api_mapper.create_start_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Qwen request: {exc}",
            )

    async def get_chat_response(self, chat_id: str) -> ChatMessageResponse:
        try:
            chat = await self.qwen_service.get_conversation(chat_id)
            return self.chat_to_api_mapper.create_message_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching Qwen conversation: {exc}",
            )

    async def create_chat_and_wait(self, request: ChatRequest) -> ChatCompleteResponse:
        try:
            chat = await self.qwen_service.ask_and_wait(
                request.message,
                request.chat_id,
                type_input=request.type,
            )
            return self.chat_to_api_mapper.create_complete_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing blocking Qwen request: {exc}",
            )

    def logout(self) -> dict:
        try:
            self.qwen_service.logout()
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Qwen logout: {exc}",
            )

    async def get_status(self) -> ChannelStatusResponse:
        try:
            return ChannelStatusResponse.model_validate(await self.qwen_service.status())
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching Qwen status: {exc}",
            )

    async def login(self, request: LoginRequest) -> dict:
        try:
            await self.qwen_service.login(request.content)
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Qwen login: {exc}",
            )
