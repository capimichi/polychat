import asyncio
from time import monotonic
from typing import Awaitable, Callable

from polychat.model.service.chat import Chat


class ChatWaitTimeoutError(TimeoutError):
    """Raised when a chat response is not ready before the timeout expires."""


class ChatWaiter:
    DEFAULT_TIMEOUT_SECONDS = 120.0
    DEFAULT_POLL_INTERVAL_SECONDS = 2.0

    @classmethod
    async def wait_for_completion(
        cls,
        initial_chat: Chat,
        fetch_chat: Callable[[str], Awaitable[Chat]],
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> Chat:
        """Poll a chat until it exposes a message or image, or timeout."""
        if cls._is_complete(initial_chat):
            return initial_chat

        if not initial_chat.id:
            raise ValueError("chat id mancante")

        deadline = monotonic() + timeout_seconds
        latest_chat = initial_chat

        while True:
            remaining_seconds = deadline - monotonic()
            if remaining_seconds <= 0:
                raise ChatWaitTimeoutError(
                    f"Timeout waiting for completed chat response for chat_id '{initial_chat.id}'"
                )

            await asyncio.sleep(min(poll_interval_seconds, remaining_seconds))
            latest_chat = await fetch_chat(initial_chat.id)
            if cls._is_complete(latest_chat):
                return latest_chat

    @staticmethod
    def _is_complete(chat: Chat) -> bool:
        return bool((chat.message or "").strip()) or bool((chat.image_url or "").strip())
