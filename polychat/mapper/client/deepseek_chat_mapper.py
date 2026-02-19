from polychat.model.service.chat import Chat
from polychat.model.service.chat_metadata import ChatMetadata


class DeepseekChatMapper:
    """Placeholder mapper client -> domain per Deepseek."""

    def create_from(self, source: object) -> Chat:
        return Chat(
            id="",
            message="",
            metadata=ChatMetadata(
                provider="deepseek",
            ),
        )
