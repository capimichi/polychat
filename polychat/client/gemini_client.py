import asyncio
import os
import re
from typing import Literal, Optional
from urllib.parse import urlparse

from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from injector import inject

from polychat.client.abstract_client import AbstractClient
from polychat.model.client.gemini_response import GeminiResponse


class GeminiClient(AbstractClient):
    """Client per interagire con Gemini tramite automazione browser."""

    BASE_URL = "https://gemini.google.com/app"
    BATCH_EXECUTE_PATH = "/_/BardChatUi/data/batchexecute"
    INPUT_SELECTOR = ".text-input-field"
    COMPLETE_WAIT_TIMEOUT_SECONDS = 60.0
    COMPLETE_WAIT_CHECK_INTERVAL_SECONDS = 2.0

    @inject
    def __init__(
        self,
        session_dir: str,
        headless: bool | Literal["virtual"] = False,
        cookie_1psid: str = "",
        cookie_1psidts: str = "",
    ):
        super().__init__()
        self.session_dir = os.path.join(session_dir, "gemini")
        self.storage_state_path = os.path.join(self.session_dir, "gemini_state.json")
        self.headless = headless
        self.cookie_1psid = cookie_1psid
        self.cookie_1psidts = cookie_1psidts
        os.makedirs(self.session_dir, exist_ok=True)

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> GeminiResponse:
        cookie_1psid, cookie_1psidts = self._load_session_cookies()

        async def _attempt() -> GeminiResponse:
            constraints = Screen(max_width=1920, max_height=1080)
            async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path

                context = await browser.new_context(**context_options)
                await context.add_cookies([
                    {
                        "name": "__Secure-1PSID",
                        "value": cookie_1psid,
                        "domain": ".google.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "None",
                    },
                    {
                        "name": "__Secure-1PSIDTS",
                        "value": cookie_1psidts,
                        "domain": ".google.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "None",
                    },
                ])

                page = await context.new_page()
                self._attach_page_request_logger(page)
                url = f"{self.BASE_URL}/{chat_id}" if chat_id else self.BASE_URL
                await self._goto(page, url, wait_until="domcontentloaded", timeout=20_000)

                await page.wait_for_selector(self.INPUT_SELECTOR, state="visible", timeout=20_000)
                await page.click(self.INPUT_SELECTOR)
                await page.wait_for_timeout(1_000)

                if type_input:
                    await page.keyboard.type(self._sanitize_message(message))
                else:
                    await page.keyboard.insert_text(self._sanitize_message(message))

                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2_000)

                try:
                    await page.wait_for_url("**/app/**", timeout=15_000)
                except Exception:
                    pass

                extracted_chat_id = self._extract_chat_id_from_url(page.url or "")
                if not extracted_chat_id:
                    raise ValueError("Chat ID Gemini non trovato nella URL dopo l'invio del messaggio")

                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception:
                    pass

                await page.close()
                await context.close()

                return GeminiResponse(chat_id=extracted_chat_id, message="")

        return await _attempt()

    async def get_conversation(self, chat_id: str) -> GeminiResponse:
        if not chat_id:
            raise ValueError("chat_id mancante")

        cookie_1psid, cookie_1psidts = self._load_session_cookies()
        constraints = Screen(max_width=1920, max_height=1080)

        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context_options = {}
            if os.path.exists(self.storage_state_path):
                context_options["storage_state"] = self.storage_state_path

            context = await browser.new_context(**context_options)
            await context.add_cookies([
                {
                    "name": "__Secure-1PSID",
                    "value": cookie_1psid,
                    "domain": ".google.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "None",
                },
                {
                    "name": "__Secure-1PSIDTS",
                    "value": cookie_1psidts,
                    "domain": ".google.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "None",
                },
            ])

            page = await context.new_page()
            self._attach_page_request_logger(page)
            response_container_id = ""
            response_received = asyncio.Event()

            async def handle_response(response):
                nonlocal response_container_id
                if self.BATCH_EXECUTE_PATH not in (response.url or ""):
                    return

                try:
                    content = await response.text()
                except Exception:
                    return

                extracted = self._extract_response_container_id(content, chat_id)
                if extracted:
                    response_container_id = extracted
                    response_received.set()

            page.on("response", handle_response)
            await self._goto(page, f"{self.BASE_URL}/{chat_id}", wait_until="domcontentloaded", timeout=20_000)

            try:
                await asyncio.wait_for(response_received.wait(), timeout=45)
            except asyncio.TimeoutError as exc:
                raise TimeoutError("Timeout waiting for Gemini batchexecute response") from exc

            selector = f"#model-response-message-content{response_container_id}"
            await page.wait_for_selector(selector, state="visible", timeout=45_000)
            content = await page.inner_text(selector)

            try:
                await context.storage_state(path=self.storage_state_path)
            except Exception:
                pass

            await page.close()
            await context.close()

        return GeminiResponse(chat_id=chat_id, message=(content or "").strip())

    async def _submit_prompt(
        self,
        page,
        message: str,
        chat_id: Optional[str],
        type_input: bool,
    ) -> str:
        url = f"{self.BASE_URL}/{chat_id}" if chat_id else self.BASE_URL
        await self._goto(page, url, wait_until="domcontentloaded", timeout=20_000)

        await page.wait_for_selector(self.INPUT_SELECTOR, state="visible", timeout=20_000)
        await page.click(self.INPUT_SELECTOR)
        await page.wait_for_timeout(1_000)

        if type_input:
            await page.keyboard.type(self._sanitize_message(message))
        else:
            await page.keyboard.insert_text(self._sanitize_message(message))

        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2_000)

        try:
            await page.wait_for_url("**/app/**", timeout=15_000)
        except Exception:
            pass

        extracted_chat_id = self._extract_chat_id_from_url(page.url or "")
        if not extracted_chat_id:
            raise ValueError("Chat ID Gemini non trovato nella URL dopo l'invio del messaggio")

        return extracted_chat_id

    async def _read_conversation_from_page(self, page, chat_id: str) -> str:  # noqa: ANN001
        response_container_id = ""
        response_received = asyncio.Event()

        async def handle_response(response):
            nonlocal response_container_id
            if self.BATCH_EXECUTE_PATH not in (response.url or ""):
                return

            try:
                content = await response.text()
            except Exception:
                return

            extracted = self._extract_response_container_id(content, chat_id)
            if extracted:
                response_container_id = extracted
                response_received.set()

        page.on("response", handle_response)
        await self._goto(page, f"{self.BASE_URL}/{chat_id}", wait_until="domcontentloaded", timeout=20_000)

        try:
            await asyncio.wait_for(response_received.wait(), timeout=45)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Timeout waiting for Gemini batchexecute response") from exc

        selector = f"#model-response-message-content{response_container_id}"
        await page.wait_for_selector(selector, state="visible", timeout=45_000)
        return await page.inner_text(selector)

    async def ask_and_wait(
        self,
        message: str,
        chat_id: Optional[str] = None,
        type_input: bool = True,
    ) -> GeminiResponse:
        cookie_1psid, cookie_1psidts = self._load_session_cookies()
        constraints = Screen(max_width=1920, max_height=1080)

        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context_options = {}
            if os.path.exists(self.storage_state_path):
                context_options["storage_state"] = self.storage_state_path

            context = await browser.new_context(**context_options)
            await context.add_cookies([
                {
                    "name": "__Secure-1PSID",
                    "value": cookie_1psid,
                    "domain": ".google.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "None",
                },
                {
                    "name": "__Secure-1PSIDTS",
                    "value": cookie_1psidts,
                    "domain": ".google.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "None",
                },
            ])

            page = await context.new_page()
            self._attach_page_request_logger(page)

            try:
                resolved_chat_id = await self._submit_prompt(page, message, chat_id, type_input)
                await self._wait_for_network_to_settle(
                    page,
                    timeout_seconds=self.COMPLETE_WAIT_TIMEOUT_SECONDS,
                    check_interval_seconds=self.COMPLETE_WAIT_CHECK_INTERVAL_SECONDS,
                )
                content = await self._read_conversation_from_page(page, resolved_chat_id)
            finally:
                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception:
                    pass
                await page.close()
                await context.close()

        return GeminiResponse(chat_id=resolved_chat_id, message=(content or "").strip())

    def logout(self) -> None:
        self._clear_session_dir(self.session_dir)

    async def status(self) -> dict:
        marker = "Account Google:"
        constraints = Screen(max_width=1920, max_height=1080)

        try:
            cookie_1psid, cookie_1psidts = self._load_session_cookies()
            async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path
                context = await browser.new_context(**context_options)
                await context.add_cookies([
                    {
                        "name": "__Secure-1PSID",
                        "value": cookie_1psid,
                        "domain": ".google.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "None",
                    },
                    {
                        "name": "__Secure-1PSIDTS",
                        "value": cookie_1psidts,
                        "domain": ".google.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "None",
                    },
                ])
                page = await context.new_page()
                self._attach_page_request_logger(page)
                await self._goto(page, self.BASE_URL, wait_until="domcontentloaded", timeout=20_000)
                await page.wait_for_timeout(1_500)
                content = await page.content()

                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception:
                    pass
                await page.close()
                await context.close()
        except Exception as exc:
            return {
                "provider": "gemini",
                "is_available": False,
                "is_logged_in": False,
                "detail": f"Status check failed: {exc}",
            }

        return {
            "provider": "gemini",
            "is_available": True,
            "is_logged_in": marker in content,
            "detail": None if marker in content else "Marker 'Account Google:' non trovato",
        }

    def _load_session_cookies(self) -> tuple[str, str]:
        cookie_1psid = (self.cookie_1psid or "").strip()
        cookie_1psidts = (self.cookie_1psidts or "").strip()
        if not cookie_1psid or not cookie_1psidts:
            raise ValueError("GEMINI_COOKIE_1PSID e GEMINI_COOKIE_1PSIDTS sono obbligatori")
        return cookie_1psid, cookie_1psidts

    @staticmethod
    def _extract_chat_id_from_url(url: str) -> str:
        if not url:
            return ""

        parsed = urlparse(url)
        parts = [part for part in (parsed.path or "").split("/") if part]
        if len(parts) >= 2 and parts[0] == "app":
            return parts[1]
        return ""

    @staticmethod
    def _extract_response_container_id(payload: str, chat_id: str) -> str:
        if not payload or not chat_id:
            return ""

        anchor = f'c_{chat_id}'
        idx = payload.find(anchor)
        if idx == -1:
            return ""

        snippet = payload[idx: idx + 500]
        match = re.search(r'"(r_[a-zA-Z0-9]+)"', snippet)
        if not match:
            return ""

        return match.group(1)
