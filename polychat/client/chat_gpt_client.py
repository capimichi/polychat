import asyncio
import json
import os
from http.cookiejar import CookieJar
from typing import Optional

import requests
from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from injector import inject

from polychat.client.abstract_client import AbstractClient
from polychat.model import ChatResponse
from polychat.model.chatgpt import ConversationList


class ChatGptClient(AbstractClient):
    CHAT_LIST_URL = (
        "https://chatgpt.com/backend-api/conversations?"
        "offset={offset}&limit={limit}&order=updated&is_archived=false&"
        "is_starred=false&request_p_scope=false"
    )

    @inject
    def __init__(self, session_dir: str, headless: bool = False):
        self.session_dir = session_dir
        self.storage_state_path = os.path.join(session_dir, "chatgpt_state.json")
        self.headless = headless

    async def login(self) -> None:
        """Apre il browser per consentire il login manuale e salva lo stato della sessione."""
        constraints = Screen(max_width=768, max_height=992)
        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto("https://chatgpt.com/")
            await asyncio.sleep(60)

            await context.storage_state(path=self.storage_state_path)

            await page.close()
            await context.close()

    def get_conversations(self, offset: int = 0, limit: int = 28) -> ConversationList:
        """Recupera la lista delle conversazioni esistenti."""
        if not os.path.exists(self.storage_state_path):
            raise FileNotFoundError("Storage state non trovato: esegui prima login()")

        cookies = self._load_cookies()
        url = self.CHAT_LIST_URL.format(offset=offset, limit=limit)

        with requests.Session() as session:
            session.cookies = cookies
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return ConversationList.model_validate_json(response.text)

    async def ask(self, message: str, chat_id: Optional[str] = None) -> ChatResponse:
        """
        Invia un messaggio compilando #prompt-textarea, attende il completamento dello stream
        su /backend-api/f/conversation, poi copia l'ultima risposta cliccando il bottone
        con aria-label="Copia" e restituisce il contenuto della clipboard come ChatResponse.
        """
        if not os.path.exists(self.storage_state_path):
            raise FileNotFoundError("Storage state non trovato: esegui prima login()")

        constraints = Screen(max_width=1920, max_height=1080)
        stream_payload = ""
        stream_received = asyncio.Event()

        async def handle_response(response):
            nonlocal stream_payload
            if "/backend-api/f/conversation" in response.url:
                try:
                    body = await response.body()
                    raw_content = body.decode("utf-8")
                    stream_payload = raw_content
                    if "data: [DONE]" in raw_content:
                        stream_received.set()
                except Exception as exc:
                    print(f"Errore lettura stream ChatGPT: {exc}")

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
            page.on("response", handle_response)

            url = f"https://chatgpt.com/c/{chat_id}" if chat_id else "https://chatgpt.com/"
            await page.goto(url)

            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)

            # if there is a .popover with data-state="open", then check if there is a div with text "ChatGpt pro" and click on the workspace
            popover = await page.query_selector('div.popover[data-state="open"]')
            if popover:
                workspace_button = await popover.query_selector('button:has-text("ChatGpt pro")')
                if workspace_button:
                    await workspace_button.click()
                    await page.wait_for_timeout(1000)

            await page.wait_for_selector("#prompt-textarea")
            await self._paste_message(page, "#prompt-textarea", message)

            await page.keyboard.press("Enter")

            try:
                await asyncio.wait_for(stream_received.wait(), timeout=120)
            except asyncio.TimeoutError:
                raise Exception("Timeout in attesa della risposta ChatGPT")

            await page.wait_for_timeout(3000)

            # get last ".text-message.relative .markdown" stripping html
            clipboard_text = ""
            messages = await page.query_selector_all(".text-message.relative .markdown")
            if messages:
                last_message = messages[-1]
                clipboard_text = await last_message.inner_text()

            current_url = page.url

            await page.close()
            await context.close()

        slug = self._extract_slug_from_url(current_url if 'current_url' in locals() else url)
        return ChatResponse(slug=slug, message=clipboard_text)


    def _load_cookies(self) -> CookieJar:
        """Carica i cookie Playwright salvati in una CookieJar per requests."""
        with open(self.storage_state_path, "r") as f:
            storage = json.load(f)

        jar = requests.cookies.RequestsCookieJar()
        for cookie in storage.get("cookies", []):
            jar.set(
                name=cookie.get("name"),
                value=cookie.get("value"),
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
                secure=cookie.get("secure", False),
            )
        return jar

    @staticmethod
    def _extract_slug_from_url(current_url: str) -> str:
        """Restituisce lo slug della conversazione a partire dalla URL corrente."""
        if not current_url:
            return ""

        prefix = "https://chatgpt.com/c/"
        if not current_url.startswith(prefix):
            return ""

        slug = current_url[len(prefix):]
        # Remove query or fragment if present
        slug = slug.split("?", 1)[0].split("#", 1)[0]
        return slug.rstrip("/")
