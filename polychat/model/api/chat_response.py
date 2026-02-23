from typing import Optional

from pydantic import BaseModel, ConfigDict


class ChatResponse(BaseModel):
    """Risposta API minimale per il frontend."""

    model_config = ConfigDict(validate_assignment=True)

    id: str
    message: str
    image_url: Optional[str] = None
