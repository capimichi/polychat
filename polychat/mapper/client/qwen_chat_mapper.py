from polychat.model.client.qwen_response import QwenResponse
from polychat.model.service.chat import Chat
from polychat.model.service.chat_metadata import ChatMetadata


class QwenChatMapper:
    """Mapper client -> domain per Qwen."""

    def create_from(self, source: QwenResponse) -> Chat:
        return Chat(
            id=source.chat_id,
            message=source.answer,
            metadata=ChatMetadata(
                provider="qwen",
                title=source.title,
                created_at=source.created_at,
                updated_at=source.updated_at,
                model=source.model_name,
                raw_id=source.request_id,
                extra={
                    "success": source.success,
                },
            ),
        )
