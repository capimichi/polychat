from polychat.model.client.kimi_response import KimiResponse
from polychat.model.service.chat import Chat
from polychat.model.service.chat_metadata import ChatMetadata


class KimiChatMapper:
    """Mapper client -> domain per Kimi."""

    def create_from(self, source: KimiResponse) -> Chat:
        return Chat(
            id="",
            message=source.message,
            metadata=ChatMetadata(
                provider="kimi",
            ),
        )
