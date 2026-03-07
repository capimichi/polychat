from polychat.model.client.gemini_response import GeminiResponse
from polychat.model.service.chat import Chat
from polychat.model.service.chat_metadata import ChatMetadata


class GeminiChatMapper:
    """Mapper client -> domain per Gemini."""

    def create_from(self, source: GeminiResponse) -> Chat:
        return Chat(
            id=source.chat_id,
            message=source.message,
            metadata=ChatMetadata(
                provider="gemini",
            ),
        )
