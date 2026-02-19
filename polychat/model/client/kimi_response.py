from pydantic import BaseModel, ConfigDict


class KimiResponse(BaseModel):
    """Risposta di Kimi acquisita via browser."""

    model_config = ConfigDict(validate_assignment=True)

    message: str
