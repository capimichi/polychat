import asyncio
import os
from typing import Optional

from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from injector import inject

from polychat.model import ChatResponse


class KimiClient:
    """Client per interagire con Kimi tramite automazione browser."""

    BASE_URL = "https://www.kimi.com/"

    @inject
    def __init__(self, session_dir: str, headless: bool = False):
        self.session_dir = session_dir
        self.storage_state_path = os.path.join(session_dir, "kimi_state.json")
        self.headless = headless

    async def login(self) -> None:
        """Apre il browser per consentire il login manuale e salva lo stato della sessione."""
        constraints = Screen(max_width=1920, max_height=1080)
        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(self.BASE_URL)
            await asyncio.sleep(60)

            await context.storage_state(path=self.storage_state_path)

            await page.close()
            await context.close()

    async def ask(self, message: str) -> ChatResponse:
        """Invia un prompt a Kimi e restituisce la risposta come ChatResponse."""
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

            await page.goto(self.BASE_URL)
            await page.wait_for_selector(".chat-input")
            await page.click(".chat-input")

            safe_message = message.replace("\n", " ")
            chunk_size = 500
            chunks = [safe_message[i:i + chunk_size] for i in range(0, len(safe_message), chunk_size)]
            for chunk in chunks:
                await page.type(".chat-input", chunk)

            await page.keyboard.press("Enter")

            # Attesa iniziale prima di monitorare la risposta
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

                # Non è cresciuto: consideriamo la risposta completa
                break

            await page.close()
            await context.close()

        return ChatResponse(slug="", message=content_html)
