from pydantic import BaseModel, ConfigDict


class ChatGptAskResult(BaseModel):
    """Risultato minimale della richiesta ChatGPT via browser."""

    model_config = ConfigDict(validate_assignment=True)

    conversation_id: str
    message: str
