from pydantic import BaseModel, ConfigDict

from polychat.model.service.chat_metadata import ChatMetadata


class Chat(BaseModel):
    """Modello di dominio per una chat."""

    model_config = ConfigDict(validate_assignment=True)

    id: str
    message: str
    metadata: ChatMetadata
