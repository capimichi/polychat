import asyncio
import os
from typing import Literal, Optional
from urllib.parse import urlparse

from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from injector import inject

from polychat.client.abstract_client import AbstractClient
from polychat.model.client.kimi_response import KimiResponse


class KimiClient(AbstractClient):
    """Client per interagire con Kimi tramite automazione browser."""

    BASE_URL = "https://www.kimi.com/"

    @inject
    def __init__(self, session_dir: str, headless: bool | Literal["virtual"] = False):
        super().__init__()
        self.session_dir = os.path.join(session_dir, "kimi")
        self.storage_state_path = os.path.join(self.session_dir, "kimi_state.json")
        self.headless = headless
        os.makedirs(self.session_dir, exist_ok=True)

    async def login(self) -> None:
        """Apre il browser per consentire il login manuale e salva lo stato della sessione."""
        os.makedirs(self.session_dir, exist_ok=True)
        constraints = Screen(max_width=1920, max_height=1080)
        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context = await browser.new_context()
            page = await context.new_page()
            self._attach_page_request_logger(page)

            await self._goto(page, self.BASE_URL)
            await asyncio.sleep(60)

            await context.storage_state(path=self.storage_state_path)

            await page.close()
            await context.close()

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> KimiResponse:
        """Invia un prompt a Kimi e restituisce il solo chat_id."""

        async def _attempt() -> KimiResponse:
            constraints = Screen(max_width=1920, max_height=1080)

            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constraints
            ) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path

                context = await browser.new_context(**context_options)
                page = await context.new_page()
                self._attach_page_request_logger(page)

                url = f"{self.BASE_URL}chat/{chat_id}" if chat_id else self.BASE_URL
                await self._goto(page, url)
                if type_input:
                    await self._type_message(page, ".chat-input", message)
                else:
                    await self._paste_message(page, ".chat-input", message)

                await page.keyboard.press("Enter")

                try:
                    await page.wait_for_url("**/chat/**", timeout=12_000)
                except Exception:
                    pass
                await page.wait_for_timeout(1_000)
                chat_id = self._extract_chat_id_from_url(page.url or "")
                if not chat_id:
                    raise ValueError("Chat ID Kimi non trovato nella URL dopo l'invio del messaggio")

                await page.close()
                await context.close()

            return KimiResponse(chat_id=chat_id, message="")

        return await self._retry_async(_attempt, attempts=3)

    async def get_conversation(self, chat_id: str) -> KimiResponse:
        if not chat_id:
            raise ValueError("chat_id mancante")

        async def _attempt() -> KimiResponse:
            constraints = Screen(max_width=1920, max_height=1080)
            content_html = ""

            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constraints
            ) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path

                context = await browser.new_context(**context_options)
                page = await context.new_page()
                self._attach_page_request_logger(page)
                await self._goto(page, f"{self.BASE_URL}chat/{chat_id}")

                await asyncio.sleep(5)

                last_len = 0
                max_wait_seconds = 120
                elapsed = 0

                while elapsed < max_wait_seconds:
                    await asyncio.sleep(2)
                    elapsed += 2

                    messages = await page.query_selector_all(".chat-content-item-assistant .markdown")
                    if not messages:
                        continue

                    last_message = messages[-1]
                    html = await last_message.inner_html()
                    if html is None:
                        continue

                    current_len = len(html)
                    if current_len > last_len:
                        last_len = current_len
                        content_html = html
                        continue

                    break

                await page.close()
                await context.close()

            return KimiResponse(chat_id=chat_id, message=content_html)

        return await self._retry_async(_attempt, attempts=3)

    def logout(self) -> None:
        self._clear_session_dir(self.session_dir)

    async def status(self) -> dict:
        constraints = Screen(max_width=1920, max_height=1080)
        try:
            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constraints
            ) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path
                context = await browser.new_context(**context_options)
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
                "provider": "kimi",
                "is_available": False,
                "is_logged_in": False,
                "detail": f"TODO: implement Kimi login detection (status check failed: {exc})",
            }

        return {
            "provider": "kimi",
            "is_available": True,
            "is_logged_in": False,
            "detail": "TODO: implement Kimi login detection",
        }

    @staticmethod
    def _extract_chat_id_from_url(url: str) -> str:
        if not url:
            return ""

        parsed = urlparse(url)
        path = (parsed.path or "").strip("/")
        if not path:
            return ""

        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "chat":
            return parts[1]
        return ""
