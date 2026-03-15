from io import BytesIO

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from injector import inject

from polychat.mapper.service.chat_to_api_mapper import ChatToApiMapper
from polychat.model.chat_request import ChatRequest
from polychat.model.api.login_request import LoginRequest
from polychat.model.api.chat_response import (
    ChannelStatusResponse,
    ChatCompleteResponse,
    ChatMessageResponse,
    ChatStartResponse,
)
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
            response_model=ChatStartResponse,
        )
        self.router.add_api_route(
            "/complete",
            self.create_chat_and_wait,
            methods=["POST"],
            summary="Invia un messaggio a ChatGPT e attende la risposta finale",
            response_model=ChatCompleteResponse,
        )
        self.router.add_api_route(
            "/login",
            self.login,
            methods=["POST"],
            summary="Login ChatGPT",
        )
        self.router.add_api_route(
            "/logout",
            self.logout,
            methods=["POST"],
            summary="Logout ChatGPT",
        )
        self.router.add_api_route(
            "/status",
            self.get_status,
            methods=["GET"],
            summary="Status ChatGPT",
            response_model=ChannelStatusResponse,
        )
        self.router.add_api_route(
            "/download-proxy",
            self.proxy_download,
            methods=["GET"],
            summary="Proxy download file ChatGPT",
        )
        self.router.add_api_route(
            "/{chat_id}",
            self.get_chat_response,
            methods=["GET"],
            summary="Recupera una conversazione ChatGPT",
            response_model=ChatMessageResponse,
        )

    async def create_chat(self, request: ChatRequest) -> ChatStartResponse:
        """Invia un messaggio a ChatGPT e restituisce il testo generato."""
        try:
            chat = await self.chatgpt_service.ask(
                request.message,
                request.chat_id,
                type_input=request.type,
            )
            return self.chat_to_api_mapper.create_start_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing ChatGPT request: {exc}",
            )

    async def get_chat_response(self, chat_id: str) -> ChatMessageResponse:
        """Recupera la risposta di ChatGPT a partire dall'ID conversazione."""
        try:
            chat = await self.chatgpt_service.get_conversation(chat_id)
            return self.chat_to_api_mapper.create_message_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching ChatGPT conversation: {exc}",
            )

    async def create_chat_and_wait(self, request: ChatRequest) -> ChatCompleteResponse:
        """Invia un messaggio e restituisce direttamente la risposta finale."""
        try:
            chat = await self.chatgpt_service.ask_and_wait(
                request.message,
                request.chat_id,
                type_input=request.type,
            )
            return self.chat_to_api_mapper.create_complete_from(chat)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing blocking ChatGPT request: {exc}",
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

    async def get_status(self) -> ChannelStatusResponse:
        try:
            return ChannelStatusResponse.model_validate(await self.chatgpt_service.status())
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching ChatGPT status: {exc}",
            )

    async def login(self, request: LoginRequest) -> dict:
        try:
            await self.chatgpt_service.login(request.content)
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing ChatGPT login: {exc}",
            )

    def proxy_download(self, download_url: str = Query(...)) -> StreamingResponse:
        """Proxy di download_url ChatGPT aggiungendo cookie di sessione in header Cookie."""
        try:
            content, status_code, content_type, content_disposition = self.chatgpt_service.proxy_download(download_url)
            headers = {}
            if content_disposition:
                headers["Content-Disposition"] = content_disposition
            return StreamingResponse(
                BytesIO(content),
                media_type=content_type,
                status_code=status_code,
                headers=headers,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error proxying ChatGPT download: {exc}",
            )
