from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConversationAuthor(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationContent(BaseModel):
    model_config = ConfigDict(extra="allow")

    content_type: str
    parts: List[Any] = Field(default_factory=list)


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    author: ConversationAuthor
    create_time: Optional[float] = None
    update_time: Optional[float] = None
    content: ConversationContent
    status: Optional[str] = None
    end_turn: Optional[bool] = None
    weight: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    recipient: Optional[str] = None
    channel: Optional[str] = None


class ConversationMappingNode(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    message: Optional[ConversationMessage] = None
    parent: Optional[str] = None
    children: List[str] = Field(default_factory=list)


class ConversationDetail(BaseModel):
    """Dettaglio conversazione ChatGPT (/backend-api/conversation/{id})."""

    model_config = ConfigDict(extra="allow")

    title: Optional[str] = None
    create_time: Optional[float] = None
    update_time: Optional[float] = None
    mapping: Dict[str, ConversationMappingNode] = Field(default_factory=dict)
    moderation_results: List[Any] = Field(default_factory=list)
    current_node: Optional[str] = None
    plugin_ids: Optional[Any] = None
    conversation_id: str
    conversation_template_id: Optional[str] = None
    gizmo_id: Optional[str] = None
    gizmo_type: Optional[str] = None
    is_archived: Optional[bool] = None
    is_starred: Optional[bool] = None
    safe_urls: List[Any] = Field(default_factory=list)
    blocked_urls: List[Any] = Field(default_factory=list)
    default_model_slug: Optional[str] = None
    memory_scope: Optional[str] = None
    context_scopes: Optional[Any] = None
    async_status: Optional[Any] = None
