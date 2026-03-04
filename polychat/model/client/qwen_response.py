from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


class QwenResponse(BaseModel):
    """Risposta completa della GET /api/v2/chats/{chat_id} di Qwen."""

    model_config = ConfigDict(validate_assignment=True)

    success: Optional[bool] = None
    request_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)

    @computed_field
    @property
    def chat_id(self) -> str:
        value = self.data.get("id")
        return value if isinstance(value, str) else ""

    @computed_field
    @property
    def title(self) -> Optional[str]:
        value = self.data.get("title")
        return value if isinstance(value, str) else None

    @computed_field
    @property
    def created_at(self) -> Optional[float]:
        value = self.data.get("created_at")
        return float(value) if isinstance(value, (int, float)) else None

    @computed_field
    @property
    def updated_at(self) -> Optional[float]:
        value = self.data.get("updated_at")
        return float(value) if isinstance(value, (int, float)) else None

    @computed_field
    @property
    def model_name(self) -> Optional[str]:
        assistant = self._current_assistant_message()
        model_name = assistant.get("modelName")
        if isinstance(model_name, str) and model_name.strip():
            return model_name

        model_id = assistant.get("model")
        if isinstance(model_id, str) and model_id.strip():
            return model_id

        chat_models = (self.data.get("chat") or {}).get("models")
        if isinstance(chat_models, list) and chat_models:
            first = chat_models[0]
            if isinstance(first, str):
                return first
        return None

    @computed_field
    @property
    def answer(self) -> str:
        assistant = self._current_assistant_message()
        content_list = assistant.get("content_list")
        if isinstance(content_list, list):
            for item in reversed(content_list):
                if not isinstance(item, dict):
                    continue
                phase = item.get("phase")
                status = item.get("status")
                content = item.get("content")
                if phase == "answer" and status == "finished" and isinstance(content, str) and content.strip():
                    return content

            for item in reversed(content_list):
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    return content

        content = assistant.get("content")
        if isinstance(content, str):
            return content
        return ""

    @computed_field
    @property
    def done(self) -> bool:
        assistant = self._current_assistant_message()
        if isinstance(assistant.get("done"), bool):
            return bool(assistant.get("done"))

        content_list = assistant.get("content_list")
        if not isinstance(content_list, list):
            return False

        for item in content_list:
            if not isinstance(item, dict):
                continue
            if item.get("phase") == "answer" and item.get("status") == "finished":
                return True
        return False

    def _history_messages(self) -> Dict[str, Any]:
        history = ((self.data.get("chat") or {}).get("history") or {})
        messages = history.get("messages")
        return messages if isinstance(messages, dict) else {}

    def _current_assistant_message(self) -> Dict[str, Any]:
        messages = self._history_messages()
        if not messages:
            return {}

        history = ((self.data.get("chat") or {}).get("history") or {})
        current_id = history.get("currentId") or self.data.get("currentId")
        if isinstance(current_id, str):
            current = messages.get(current_id)
            if isinstance(current, dict):
                if current.get("role") == "assistant":
                    return current
                for child_id in current.get("childrenIds") or []:
                    child = messages.get(child_id)
                    if isinstance(child, dict) and child.get("role") == "assistant":
                        return child

        latest_assistant: Dict[str, Any] = {}
        latest_timestamp = -1.0
        for msg in messages.values():
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            ts = msg.get("timestamp")
            ts_value = float(ts) if isinstance(ts, (int, float)) else 0.0
            if ts_value >= latest_timestamp:
                latest_timestamp = ts_value
                latest_assistant = msg

        return latest_assistant
