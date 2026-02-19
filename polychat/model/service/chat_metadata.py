from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatMetadata(BaseModel):
    """Metadati orizzontali comuni ai provider."""

    model_config = ConfigDict(validate_assignment=True)

    provider: str
    title: Optional[str] = None
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    model: Optional[str] = None
    raw_id: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)
