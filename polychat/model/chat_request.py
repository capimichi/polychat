from pydantic import BaseModel, ConfigDict
from typing import Optional


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    message: str
    chat_id: Optional[str] = None
    type: bool = True
