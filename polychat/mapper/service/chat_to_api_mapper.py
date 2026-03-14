from polychat.model.api.chat_response import ChatCompleteResponse, ChatMessageResponse, ChatStartResponse
from polychat.model.service.chat import Chat


class ChatToApiMapper:
    """Mapper domain -> API."""

    def create_start_from(self, chat: Chat) -> ChatStartResponse:
        return ChatStartResponse(
            chat_id=chat.id,
        )

    def create_message_from(self, chat: Chat) -> ChatMessageResponse:
        return ChatMessageResponse(
            message=chat.message,
            image_url=chat.image_url,
        )

    def create_complete_from(self, chat: Chat) -> ChatCompleteResponse:
        return ChatCompleteResponse(
            chat_id=chat.id,
            message=chat.message,
            image_url=chat.image_url,
        )
