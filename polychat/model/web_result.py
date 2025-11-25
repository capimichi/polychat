from pydantic import BaseModel
from typing import Optional, Any
from polychat.model.web_result_metadata import WebResultMetadata


class WebResult(BaseModel):
    name: str
    snippet: str
    timestamp: Optional[str] = None
    url: str
    meta_data: Optional[WebResultMetadata] = None
    file_metadata: Optional[Any] = None
    is_attachment: bool = False
    is_image: bool = False
    is_code_interpreter: bool = False
    is_knowledge_card: bool = False
    is_navigational: bool = False
    is_widget: bool = False
    sitelinks: Optional[Any] = None
    is_focused_web: bool = False
    is_client_context: bool = False
    inline_entity_id: Optional[str] = None
    is_memory: bool = False
    is_conversation_history: bool = False
    tab_id: Optional[str] = None
    is_scrubbed: Optional[bool] = None
