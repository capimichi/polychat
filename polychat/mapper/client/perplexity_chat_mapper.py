from polychat.model.client.perplexity_response import PerplexityResponse
from polychat.model.service.chat import Chat
from polychat.model.service.chat_metadata import ChatMetadata


class PerplexityChatMapper:
    """Mapper client -> domain per Perplexity."""

    def create_from(self, source: PerplexityResponse) -> Chat:
        conversation_id = source.thread_url_slug or source.backend_uuid or ""
        return Chat(
            id=conversation_id,
            message=source.answer or "",
            metadata=ChatMetadata(
                provider="perplexity",
                title=source.thread_title,
                model=source.display_model or source.user_selected_model,
                raw_id=source.uuid,
                extra={
                    "context_uuid": source.context_uuid,
                    "backend_uuid": source.backend_uuid,
                    "thread_url_slug": source.thread_url_slug,
                },
            ),
        )
