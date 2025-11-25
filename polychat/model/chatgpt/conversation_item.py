from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConversationItem(BaseModel):
    """Rappresenta un singolo elemento della lista conversazioni di ChatGPT."""

    model_config = ConfigDict(validate_assignment=True)

    id: str
    title: Optional[str] = None
    create_time: datetime
    update_time: datetime
    mapping: Optional[Dict[str, Any]] = None
    current_node: Optional[str] = None
    conversation_template_id: Optional[str] = None
    gizmo_id: Optional[str] = None
    is_archived: bool = False
    is_starred: Optional[bool] = None
    is_do_not_remember: bool = False
    memory_scope: Optional[str] = None
    context_scopes: Optional[List[str]] = None
    workspace_id: Optional[str] = None
    async_status: Optional[str] = None
    safe_urls: List[str] = Field(default_factory=list)
    blocked_urls: List[str] = Field(default_factory=list)
    conversation_origin: Optional[str] = None
    snippet: Optional[str] = None
    sugar_item_id: Optional[str] = None
    sugar_item_visible: bool = False

    def get_conversation_id(self) -> str:
        return self.id

    def set_conversation_id(self, conversation_id: str) -> None:
        self.id = conversation_id

    def get_title(self) -> Optional[str]:
        return self.title

    def set_title(self, title: Optional[str]) -> None:
        self.title = title

    def is_favorited(self) -> bool:
        return bool(self.is_starred)

    def set_favorited(self, starred: bool) -> None:
        self.is_starred = starred

    def is_archived_flag(self) -> bool:
        return self.is_archived

    def set_archived(self, archived: bool) -> None:
        self.is_archived = archived

    def get_snippet(self) -> Optional[str]:
        return self.snippet

    def set_snippet(self, snippet: Optional[str]) -> None:
        self.snippet = snippet

    def add_safe_url(self, url: str) -> None:
        """Aggiunge un URL all'elenco di safe_urls evitando duplicati."""
        if url not in self.safe_urls:
            self.safe_urls.append(url)

    def add_blocked_url(self, url: str) -> None:
        """Aggiunge un URL all'elenco di blocked_urls evitando duplicati."""
        if url not in self.blocked_urls:
            self.blocked_urls.append(url)
