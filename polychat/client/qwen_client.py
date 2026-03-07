import asyncio
import os
from typing import Literal, Optional
from urllib.parse import urlparse

import requests
from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from injector import inject

from polychat.client.abstract_client import AbstractClient
from polychat.model.client.qwen_response import QwenResponse


class QwenClient(AbstractClient):
    """Client per interagire con Qwen via browser + polling API chat."""

    BASE_URL = "https://chat.qwen.ai/"
    CHAT_API_URL = "https://chat.qwen.ai/api/v2/chats/{chat_id}"
    WAIT_FOR_URL_TIMEOUT_MS = 20_000
    INPUT_SELECTOR = ".message-input-textarea"
    POLL_INTERVAL_SECONDS = 2
    MAX_WAIT_SECONDS = 120

    @inject
    def __init__(
        self,
        session_dir: str,
        headless: bool | Literal["virtual"] = False,
        session_cookie: str = "",
    ):
        super().__init__()
        self.session_dir = os.path.join(session_dir, "qwen")
        self.storage_state_path = os.path.join(self.session_dir, "qwen_state.json")
        self.headless = headless
        self.session_cookie = session_cookie
        os.makedirs(self.session_dir, exist_ok=True)

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> QwenResponse:
        session_cookie = self._load_session_cookie()

        async def _attempt() -> QwenResponse:
            constraints = Screen(max_width=1920, max_height=1080)
            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constraints,
            ) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path

                context = await browser.new_context(**context_options)
                await context.add_cookies(
                    [
                        {
                            "name": "token",
                            "value": session_cookie,
                            "domain": "chat.qwen.ai",
                            "path": "/",
                            "secure": True,
                            "sameSite": "Lax",
                        }
                    ]
                )

                page = await context.new_page()
                self._attach_page_request_logger(page)
                url = f"{self.BASE_URL}c/{chat_id}" if chat_id else self.BASE_URL
                await self._goto(page, url, wait_until="domcontentloaded", timeout=15_000)
                await page.wait_for_selector(self.INPUT_SELECTOR, state="visible", timeout=20_000)
                await page.wait_for_timeout(500)

                if type_input:
                    await self._type_into_focused_input(page, message)
                else:
                    await self._paste_into_focused_input(page, message)

                await page.keyboard.press("Enter")

                await page.wait_for_timeout(1_000)

                url = page.url or ""

                conversation_id = self._extract_chat_id_from_url(url)
                if not conversation_id:
                    raise ValueError("Chat ID Qwen non trovato nella URL dopo l'invio del messaggio")

                response = QwenResponse(
                    data={
                        "id": conversation_id,
                    }
                )

                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception:
                    pass

                await page.close()
                await context.close()

                return response

        # Non ritentare l'intero flow di ask: un retry qui rispedirebbe il messaggio.
        return await _attempt()

    def logout(self) -> None:
        self._clear_session_dir(self.session_dir)

    async def status(self) -> dict:
        constraints = Screen(max_width=1920, max_height=1080)
        session_cookie = self._load_session_cookie()
        try:
            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constraints,
            ) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path

                context = await browser.new_context(**context_options)
                await context.add_cookies(
                    [
                        {
                            "name": "token",
                            "value": session_cookie,
                            "domain": "chat.qwen.ai",
                            "path": "/",
                            "secure": True,
                            "sameSite": "Lax",
                        }
                    ]
                )

                page = await context.new_page()
                self._attach_page_request_logger(page)
                await self._goto(page, self.BASE_URL, wait_until="domcontentloaded", timeout=20_000)
                await page.wait_for_timeout(1_500)
                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception:
                    pass
                await page.close()
                await context.close()
        except Exception as exc:
            return {
                "provider": "qwen",
                "is_available": False,
                "is_logged_in": None,
                "detail": f"TODO: implement Qwen login detection (status check failed: {exc})",
            }

        return {
            "provider": "qwen",
            "is_available": True,
            "is_logged_in": None,
            "detail": "TODO: implement Qwen login detection",
        }

    async def get_conversation(self, conversation_id: str) -> QwenResponse:
        if not conversation_id:
            raise ValueError("conversation_id mancante")

        session_cookie = self._load_session_cookie()

        async def _attempt() -> QwenResponse:
            return await self._poll_chat_response(conversation_id, session_cookie)

        return await self._retry_async(_attempt, attempts=3)

    async def _poll_chat_response(self, chat_id: str, session_cookie: str) -> QwenResponse:
        elapsed = 0
        last_response: Optional[QwenResponse] = None
        last_error: Optional[Exception] = None

        while elapsed < self.MAX_WAIT_SECONDS:
            try:
                payload = await asyncio.to_thread(self._fetch_chat_payload, chat_id, session_cookie)
                response = QwenResponse.model_validate(payload)
                last_response = response

                if response.done and response.answer.strip():
                    return response
            except Exception as exc:
                last_error = exc

            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
            elapsed += self.POLL_INTERVAL_SECONDS

        if last_response and last_response.answer.strip():
            return last_response

        if last_error:
            raise TimeoutError(
                f"Timeout waiting for Qwen chat response (chat_id={chat_id}). Last error: {last_error}"
            )
        raise TimeoutError(f"Timeout waiting for Qwen chat response (chat_id={chat_id})")

    def _fetch_chat_payload(self, chat_id: str, session_cookie: str) -> dict:
        url = self.CHAT_API_URL.format(chat_id=chat_id)
        headers = {
            "Accept": "application/json",
            "Cookie": f"token={session_cookie}",
            "Referer": f"{self.BASE_URL}c/{chat_id}",
        }
        self._log_http_request("GET", url)
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError as exc:
            content_type = response.headers.get("Content-Type", "")
            body_preview = (response.text or "")[:200].replace("\n", " ")
            raise ValueError(
                f"Qwen chat API returned non-JSON response. "
                f"status={response.status_code} content_type={content_type} body={body_preview}"
            ) from exc

    def _load_session_cookie(self) -> str:
        cookie_value = (self.session_cookie or "").strip()
        if not cookie_value:
            raise ValueError("QWEN_SESSION_COOKIE mancante o vuoto")
        return cookie_value

    async def _type_into_focused_input(self, page, content: str) -> None:
        safe_content = self._sanitize_message(content)
        await page.keyboard.type(safe_content)

    async def _paste_into_focused_input(self, page, content: str) -> None:
        safe_content = self._sanitize_message(content)
        await page.keyboard.insert_text(safe_content)

    @staticmethod
    def _extract_chat_id_from_url(url: str) -> str:
        if not url:
            return ""

        parsed = urlparse(url)
        path = (parsed.path or "").strip("/")
        if not path:
            return ""

        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "c":
            return parts[1]
        return ""
