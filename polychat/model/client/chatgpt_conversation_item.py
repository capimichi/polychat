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
