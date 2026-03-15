from pydantic import BaseModel


class LoginRequest(BaseModel):
    content: str
