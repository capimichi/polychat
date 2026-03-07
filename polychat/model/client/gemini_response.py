from pydantic import BaseModel, ConfigDict


class GeminiResponse(BaseModel):
    """Risposta di Gemini acquisita via browser."""

    model_config = ConfigDict(validate_assignment=True)

    chat_id: str = ""
    message: str
