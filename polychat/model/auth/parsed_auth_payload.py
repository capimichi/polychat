from typing import Any

from pydantic import BaseModel, Field


class ParsedAuthPayload(BaseModel):
    cookies: list[dict[str, Any]] = Field(default_factory=list)
    raw_json_value: Any | None = None
    raw_text: str = ""
