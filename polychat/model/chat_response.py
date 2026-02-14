from pydantic import BaseModel, ConfigDict


class ChatResponse(BaseModel):
    """Risposta generica di una chat con identificativo e messaggio."""

    model_config = ConfigDict(validate_assignment=True)

    slug: str
    message: str = ""

    def get_slug(self) -> str:
        return self.slug

    def set_slug(self, value: str) -> None:
        self.slug = value

    def get_message(self) -> str:
        return self.message

    def set_message(self, value: str) -> None:
        self.message = value
