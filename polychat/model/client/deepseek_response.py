from pydantic import BaseModel, ConfigDict


class DeepseekResponse(BaseModel):
    """Risposta di Deepseek acquisita via browser/API history."""

    model_config = ConfigDict(validate_assignment=True)

    chat_id: str = ""
    message: str
