from polychat.model.api.chat_response import ChatResponse
from polychat.model.service.chat import Chat


class ChatToApiMapper:
    """Mapper domain -> API."""

    def create_from(self, chat: Chat) -> ChatResponse:
        return ChatResponse(
            id=chat.id,
            message=chat.message,
        )
