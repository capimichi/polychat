from fastapi import APIRouter, HTTPException, status

from polychat.model.api.chat_response import ChannelStatusResponse
from polychat.model.chat_request import ChatRequest


class DeepseekController:
    """Controller for Deepseek chat endpoints (placeholder)."""

    def __init__(self):
        self.router = APIRouter(prefix="/deepseek/chats", tags=["Deepseek Chats"])
        self._register_routes()

    def _register_routes(self):
        """Register Deepseek routes."""
        self.router.add_api_route(
            "",
            self.create_chat,
            methods=["POST"],
            summary="Send a message to Deepseek (placeholder)",
            responses={501: {"description": "Not implemented"}},
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

    async def create_chat(self, request: ChatRequest):
        """Placeholder for sending a chat to Deepseek."""
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Sending chats to Deepseek is not implemented yet",
        )

    def logout(self) -> dict:
        return {"status": "ok", "detail": "TODO: implement Deepseek logout"}

    def get_status(self) -> ChannelStatusResponse:
        return ChannelStatusResponse(
            provider="deepseek",
            is_available=True,
            is_logged_in=None,
            detail="TODO: implement Deepseek status detection",
        )
