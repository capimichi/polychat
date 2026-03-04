from typing import Optional

from pydantic import BaseModel, ConfigDict


class ChatStartResponse(BaseModel):
    """Risposta API per la creazione chat."""

    model_config = ConfigDict(validate_assignment=True)

    chat_id: str


class ChatMessageResponse(BaseModel):
    """Risposta API per il recupero ultimo messaggio chat."""

    model_config = ConfigDict(validate_assignment=True)

    message: str
    image_url: Optional[str] = None


class ChannelStatusResponse(BaseModel):
    """Stato operativo/autenticazione di un canale."""

    model_config = ConfigDict(validate_assignment=True)

    provider: str
    is_available: bool
    is_logged_in: Optional[bool] = None
    detail: Optional[str] = None
