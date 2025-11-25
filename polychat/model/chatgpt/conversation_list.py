from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from polychat.model.chatgpt.conversation_item import ConversationItem


class ConversationList(BaseModel):
    """Envelope della risposta di lista conversazioni ChatGPT."""

    model_config = ConfigDict(validate_assignment=True)

    items: List[ConversationItem]
    total: int
    limit: int
    offset: int

    def get_conversation_by_id(self, conversation_id: str) -> Optional[ConversationItem]:
        """Restituisce una conversazione tramite il suo id se presente."""
        return next((item for item in self.items if item.id == conversation_id), None)

    def add_conversation(self, conversation: ConversationItem) -> None:
        self.items.append(conversation)

    def has_more(self) -> bool:
        """Indica se esistono altre conversazioni oltre al blocco corrente."""
        return self.offset + self.limit < self.total
