from fastapi import APIRouter, HTTPException, status
from injector import inject

from polychat.model.chat_request import ChatRequest
from polychat.mapper.service.chat_to_api_mapper import ChatToApiMapper
from polychat.model.api.chat_response import (
    ChannelStatusResponse,
    ChatCompleteResponse,
    ChatMessageResponse,
    ChatStartResponse,
)
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
            response_model=ChatStartResponse,
        )
        self.router.add_api_route(
            "/complete",
            self.create_chat_and_wait,
            methods=["POST"],
            summary="Send a message to Perplexity and wait for the completed response",
            response_model=ChatCompleteResponse,
        )
        self.router.add_api_route(
            "/logout",
            self.logout,
            methods=["POST"],
            summary="Logout Perplexity",
        )
        self.router.add_api_route(
            "/status",
            self.get_status,
            methods=["GET"],
            summary="Status Perplexity",
            response_model=ChannelStatusResponse,
        )
        self.router.add_api_route(
            "/{chat_id}",
            self.get_chat_response,
            methods=["GET"],
            summary="Get a Perplexity conversation by id",
            response_model=ChatMessageResponse,
        )

    async def create_chat(self, request: ChatRequest) -> ChatStartResponse:
        """Send a chat message to Perplexity."""
        try:
            chat = await self.perplexity_service.ask(
                request.message,
                request.chat_id,
                type_input=request.type,
            )
            return self.chat_to_api_mapper.create_start_from(chat)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing request: {str(e)}",
            )

    async def get_chat_response(self, chat_id: str) -> ChatMessageResponse:
        """Get Perplexity response by conversation id (slug)."""
        try:
            chat = await self.perplexity_service.get_conversation(chat_id)
            return self.chat_to_api_mapper.create_message_from(chat)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching conversation: {str(e)}",
            )

    async def create_chat_and_wait(self, request: ChatRequest) -> ChatCompleteResponse:
        """Send a chat message and wait until Perplexity exposes the final response."""
        try:
            chat = await self.perplexity_service.ask_and_wait(
                request.message,
                request.chat_id,
                type_input=request.type,
            )
            return self.chat_to_api_mapper.create_complete_from(chat)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing blocking request: {str(e)}",
            )

    def logout(self) -> dict:
        try:
            self.perplexity_service.logout()
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Perplexity logout: {exc}",
            )

    async def get_status(self) -> ChannelStatusResponse:
        try:
            return ChannelStatusResponse.model_validate(await self.perplexity_service.status())
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching Perplexity status: {exc}",
            )
