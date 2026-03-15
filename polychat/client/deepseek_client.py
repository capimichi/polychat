import asyncio
import json
import os
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from injector import inject

from polychat.client.abstract_client import AbstractClient
from polychat.model.client.deepseek_response import DeepseekResponse


class DeepseekClient(AbstractClient):
    """Client per interagire con Deepseek tramite browser + polling history API."""

    BASE_URL = "https://chat.deepseek.com/"
    CHAT_URL_TEMPLATE = "https://chat.deepseek.com/a/chat/s/{chat_id}"
    HISTORY_API_URL = "https://chat.deepseek.com/api/v0/chat/history_messages?chat_session_id={chat_id}"
    INPUT_SELECTOR = "textarea"
    POLL_INTERVAL_SECONDS = 2
    MAX_WAIT_SECONDS = 120
    COMPLETE_WAIT_TIMEOUT_SECONDS = 60.0
    COMPLETE_WAIT_CHECK_INTERVAL_SECONDS = 5.0

    @inject
    def __init__(
        self,
        session_dir: str,
        headless: bool | Literal["virtual"] = False,
        user_token_json: str = "",
    ):
        super().__init__()
        self.session_dir = os.path.join(session_dir, "deepseek")
        self.storage_state_path = os.path.join(self.session_dir, "deepseek_state.json")
        self.headless = headless
        self.user_token_json = user_token_json
        os.makedirs(self.session_dir, exist_ok=True)

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> DeepseekResponse:
        token_json = self._load_user_token_json()

        async def _attempt() -> DeepseekResponse:
            constraints = Screen(max_width=1920, max_height=1080)
            async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path

                context = await browser.new_context(**context_options)
                page = await context.new_page()
                self._attach_page_request_logger(page)

                url = self.CHAT_URL_TEMPLATE.format(chat_id=chat_id) if chat_id else self.BASE_URL
                await self._goto(page, url, wait_until="domcontentloaded", timeout=20_000)
                await self._set_user_token(page, token_json)
                await page.reload(wait_until="domcontentloaded", timeout=20_000)

                if self._is_sign_in_url(page.url or ""):
                    raise PermissionError("Deepseek login required: redirected to /sign_in")

                await page.wait_for_selector(self.INPUT_SELECTOR, state="visible", timeout=20_000)
                await page.click(self.INPUT_SELECTOR)

                if type_input:
                    await self._type_message(page, self.INPUT_SELECTOR, message)
                else:
                    await self._paste_message(page, self.INPUT_SELECTOR, message)

                await page.keyboard.press("Enter")

                try:
                    await page.wait_for_url("**/a/chat/s/**", timeout=20_000)
                except Exception:
                    pass

                await page.wait_for_timeout(1_500)
                extracted_chat_id = self._extract_chat_id_from_url(page.url or "")
                if not extracted_chat_id:
                    raise ValueError("Chat ID Deepseek non trovato nella URL dopo l'invio del messaggio")

                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception:
                    pass

                await page.close()
                await context.close()
                return DeepseekResponse(chat_id=extracted_chat_id, message="")

        return await _attempt()

    async def get_conversation(self, chat_id: str) -> DeepseekResponse:
        if not chat_id:
            raise ValueError("chat_id mancante")

        token_json = self._load_user_token_json()
        constraints = Screen(max_width=1920, max_height=1080)

        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context_options = {}
            if os.path.exists(self.storage_state_path):
                context_options["storage_state"] = self.storage_state_path

            context = await browser.new_context(**context_options)
            page = await context.new_page()
            self._attach_page_request_logger(page)

            await self._goto(page, self.CHAT_URL_TEMPLATE.format(chat_id=chat_id), wait_until="domcontentloaded", timeout=20_000)
            await self._set_user_token(page, token_json)
            await page.reload(wait_until="domcontentloaded", timeout=20_000)

            last_message = ""
            elapsed = 0

            while elapsed < self.MAX_WAIT_SECONDS:
                payload = await page.evaluate(
                    """async (url) => {
                        const response = await fetch(url, { credentials: 'include' });
                        return await response.json();
                    }""",
                    self.HISTORY_API_URL.format(chat_id=chat_id),
                )

                message, done = self._extract_assistant_message(payload)
                if message:
                    last_message = message
                if message and done:
                    break

                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
                elapsed += self.POLL_INTERVAL_SECONDS

            if not last_message:
                raise TimeoutError(f"Timeout waiting for Deepseek chat response (chat_id={chat_id})")

            try:
                await context.storage_state(path=self.storage_state_path)
            except Exception:
                pass

            await page.close()
            await context.close()

            return DeepseekResponse(chat_id=chat_id, message=last_message)

    async def _submit_prompt(
        self,
        page,
        token_json: str,
        message: str,
        chat_id: Optional[str],
        type_input: bool,
    ) -> str:
        url = self.CHAT_URL_TEMPLATE.format(chat_id=chat_id) if chat_id else self.BASE_URL
        await self._goto(page, url, wait_until="domcontentloaded", timeout=20_000)
        await self._set_user_token(page, token_json)
        await page.reload(wait_until="domcontentloaded", timeout=20_000)

        if self._is_sign_in_url(page.url or ""):
            raise PermissionError("Deepseek login required: redirected to /sign_in")

        await page.wait_for_selector(self.INPUT_SELECTOR, state="visible", timeout=20_000)
        await page.click(self.INPUT_SELECTOR)

        if type_input:
            await self._type_message(page, self.INPUT_SELECTOR, message)
        else:
            await self._paste_message(page, self.INPUT_SELECTOR, message)

        await page.keyboard.press("Enter")

        try:
            await page.wait_for_url("**/a/chat/s/**", timeout=20_000)
        except Exception:
            pass

        await page.wait_for_timeout(1_500)
        extracted_chat_id = self._extract_chat_id_from_url(page.url or "")
        if not extracted_chat_id:
            raise ValueError("Chat ID Deepseek non trovato nella URL dopo l'invio del messaggio")

        return extracted_chat_id

    async def _poll_conversation_from_page(self, page, chat_id: str) -> DeepseekResponse:  # noqa: ANN001
        last_message = ""
        elapsed = 0

        while elapsed < self.MAX_WAIT_SECONDS:
            payload = await page.evaluate(
                """async (url) => {
                    const response = await fetch(url, { credentials: 'include' });
                    return await response.json();
                }""",
                self.HISTORY_API_URL.format(chat_id=chat_id),
            )

            message, done = self._extract_assistant_message(payload)
            if message:
                last_message = message
            if message and done:
                return DeepseekResponse(chat_id=chat_id, message=message)

            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
            elapsed += self.POLL_INTERVAL_SECONDS

        if not last_message:
            raise TimeoutError(f"Timeout waiting for Deepseek chat response (chat_id={chat_id})")

        return DeepseekResponse(chat_id=chat_id, message=last_message)

    async def ask_and_wait(
        self,
        message: str,
        chat_id: Optional[str] = None,
        type_input: bool = True,
    ) -> DeepseekResponse:
        token_json = self._load_user_token_json()
        constraints = Screen(max_width=1920, max_height=1080)

        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context_options = {}
            if os.path.exists(self.storage_state_path):
                context_options["storage_state"] = self.storage_state_path

            context = await browser.new_context(**context_options)
            page = await context.new_page()
            self._attach_page_request_logger(page)

            try:
                resolved_chat_id = await self._submit_prompt(page, token_json, message, chat_id, type_input)
                await self._wait_for_network_to_settle(
                    page,
                    timeout_seconds=self.COMPLETE_WAIT_TIMEOUT_SECONDS,
                    check_interval_seconds=self.COMPLETE_WAIT_CHECK_INTERVAL_SECONDS,
                )
                response = await self._poll_conversation_from_page(page, resolved_chat_id)
            finally:
                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception:
                    pass
                await page.close()
                await context.close()

        return response

    def logout(self) -> None:
        self._clear_session_dir(self.session_dir)

    async def status(self) -> dict:
        try:
            token_json = self._load_user_token_json()
            constraints = Screen(max_width=1920, max_height=1080)
            async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path

                context = await browser.new_context(**context_options)
                page = await context.new_page()
                self._attach_page_request_logger(page)
                await self._goto(page, self.BASE_URL, wait_until="domcontentloaded", timeout=20_000)
                await self._set_user_token(page, token_json)
                await page.reload(wait_until="domcontentloaded", timeout=20_000)
                await page.wait_for_timeout(1_000)

                if self._is_sign_in_url(page.url or ""):
                    is_logged_in = False
                else:
                    is_logged_in = True

                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception:
                    pass

                await page.close()
                await context.close()
        except Exception as exc:
            return {
                "provider": "deepseek",
                "is_available": False,
                "is_logged_in": False,
                "detail": f"Status check failed: {exc}",
            }

        return {
            "provider": "deepseek",
            "is_available": True,
            "is_logged_in": is_logged_in,
            "detail": None if is_logged_in else "Redirected to /sign_in",
        }

    @staticmethod
    def _extract_chat_id_from_url(url: str) -> str:
        if not url:
            return ""

        parsed = urlparse(url)
        parts = [part for part in (parsed.path or "").split("/") if part]
        if len(parts) >= 4 and parts[0] == "a" and parts[1] == "chat" and parts[2] == "s":
            return parts[3]
        return ""

    @staticmethod
    def _is_sign_in_url(url: str) -> bool:
        return "/sign_in" in (url or "")

    @staticmethod
    def _extract_assistant_message(payload: dict[str, Any]) -> tuple[str, bool]:
        chat_messages = (
            (payload.get("data") or {})
            .get("biz_data", {})
            .get("chat_messages", [])
        )

        if not isinstance(chat_messages, list):
            return "", False

        fallback_message = ""
        for item in reversed(chat_messages):
            if not isinstance(item, dict):
                continue
            if str(item.get("role", "")).upper() != "ASSISTANT":
                continue

            fragments = item.get("fragments") or []
            response_fragment = None
            for fragment in fragments:
                if not isinstance(fragment, dict):
                    continue
                if str(fragment.get("type", "")).upper() == "RESPONSE":
                    response_fragment = fragment
                    break

            if not response_fragment:
                continue

            content = response_fragment.get("content")
            if isinstance(content, str) and content.strip():
                status = str(item.get("status", "")).upper()
                is_finished = status == "FINISHED"
                if is_finished:
                    return content.strip(), True
                fallback_message = content.strip()
                break

        if fallback_message:
            return fallback_message, False
        return "", False

    @staticmethod
    def _validate_user_token_json(token_json: str) -> str:
        try:
            parsed = json.loads(token_json)
        except json.JSONDecodeError as exc:
            raise ValueError("DEEPSEEK_USER_TOKEN_JSON non è un JSON valido") from exc
        return json.dumps(parsed, ensure_ascii=False)

    def _load_user_token_json(self) -> str:
        token_json = (self.user_token_json or "").strip()
        if not token_json:
            raise ValueError("DEEPSEEK_USER_TOKEN_JSON mancante o vuoto")
        return self._validate_user_token_json(token_json)

    async def _set_user_token(self, page, token_json: str) -> None:
        await page.evaluate(
            """(tokenValue) => {
                window.localStorage.setItem('userToken', tokenValue);
            }""",
            token_json,
        )
