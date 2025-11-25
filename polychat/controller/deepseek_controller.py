from fastapi import APIRouter, HTTPException, status

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

    async def create_chat(self, request: ChatRequest):
        """Placeholder for sending a chat to Deepseek."""
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Sending chats to Deepseek is not implemented yet",
        )
