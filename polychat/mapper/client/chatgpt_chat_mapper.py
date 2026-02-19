from typing import Iterable, Optional

from polychat.model.client.chatgpt_ask_result import ChatGptAskResult
from polychat.model.client.chatgpt_conversation_detail import ConversationDetail, ConversationMappingNode
from polychat.model.service.chat import Chat
from polychat.model.service.chat_metadata import ChatMetadata


class ChatGptChatMapper:
    """Mapper client -> domain per ChatGPT."""

    def create_from(self, source: ConversationDetail | ChatGptAskResult) -> Chat:
        if isinstance(source, ChatGptAskResult):
            return Chat(
                id=source.conversation_id,
                message=source.message,
                metadata=ChatMetadata(
                    provider="chatgpt",
                    raw_id=source.conversation_id,
                ),
            )

        message = self._extract_last_assistant_message(source)
        return Chat(
            id=source.conversation_id,
            message=message,
            metadata=ChatMetadata(
                provider="chatgpt",
                title=source.title,
                created_at=source.create_time,
                updated_at=source.update_time,
                model=source.default_model_slug,
                raw_id=source.conversation_id,
            ),
        )

    def _extract_last_assistant_message(self, detail: ConversationDetail) -> str:
        if not detail.mapping:
            return ""

        current_id = detail.current_node
        if current_id:
            message = self._walk_up_for_assistant(detail.mapping, current_id)
            if message is not None:
                return message

        return self._find_last_assistant_by_time(detail.mapping.values())

    def _walk_up_for_assistant(
        self,
        mapping: dict[str, ConversationMappingNode],
        node_id: str,
    ) -> Optional[str]:
        while node_id:
            node = mapping.get(node_id)
            if not node:
                break
            if node.message and node.message.author.role == "assistant":
                return self._parts_to_text(node.message.content.parts)
            node_id = node.parent or ""
        return None

    def _find_last_assistant_by_time(self, nodes: Iterable[ConversationMappingNode]) -> str:
        best = None
        best_time = None
        fallback = None

        for node in nodes:
            if not node.message or node.message.author.role != "assistant":
                continue
            text = self._parts_to_text(node.message.content.parts)
            if fallback is None:
                fallback = text
            if node.message.create_time is not None:
                if best_time is None or node.message.create_time > best_time:
                    best_time = node.message.create_time
                    best = text

        return best if best is not None else (fallback or "")

    @staticmethod
    def _parts_to_text(parts: list) -> str:
        if not parts:
            return ""
        return "".join(part if isinstance(part, str) else str(part) for part in parts)
