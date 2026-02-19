import asyncio
import os
from typing import Optional

import requests
from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from injector import inject

from polychat.client.abstract_client import AbstractClient
from polychat.model.client.chatgpt_ask_result import ChatGptAskResult
from polychat.model.client.chatgpt_conversation_detail import ConversationDetail
from polychat.model.client.chatgpt_conversation_list import ConversationList


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
        self.cookie_path = os.path.join(session_dir, "chatgpt_cookie.txt")
        self.headless = headless

    async def login(self, session_cookie: str) -> None:
        """Salva il cookie di sessione fornito manualmente."""
        cookie_value = (session_cookie or "").strip()
        if not cookie_value:
            raise ValueError("Cookie di sessione mancante")

        os.makedirs(self.session_dir, exist_ok=True)
        with open(self.cookie_path, "w", encoding="utf-8") as f:
            f.write(cookie_value)

    def logout(self) -> None:
        """Rimuove cookie e storage state salvati."""
        for path in (self.cookie_path, self.storage_state_path):
            if os.path.exists(path):
                os.remove(path)

    def get_conversations(self, offset: int = 0, limit: int = 28) -> ConversationList:
        """Recupera la lista delle conversazioni esistenti."""
        session_cookie = self._load_session_cookie()

        url = self.CHAT_LIST_URL.format(offset=offset, limit=limit)

        with requests.Session() as session:
            response = session.get(url, headers=self._auth_headers(session_cookie, ""), timeout=30)
            response.raise_for_status()
            return ConversationList.model_validate_json(response.text)

    async def get_conversation(self, conversation_id: str) -> ConversationDetail:
        """Recupera i dettagli di una conversazione tramite il browser."""
        if not conversation_id:
            raise ValueError("conversation_id mancante")

        session_cookie = self._load_session_cookie()
        payload = await self._fetch_conversation_via_browser(conversation_id, session_cookie)
        return ConversationDetail.model_validate(payload)

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> ChatGptAskResult:
        """
        Invia un messaggio compilando #prompt-textarea, attende il completamento dello stream
        su /backend-api/f/conversation, poi copia l'ultima risposta cliccando il bottone
        con aria-label="Copia" e restituisce il contenuto della clipboard come ChatGptAskResult.
        """
        session_cookie = self._load_session_cookie()

        async def _attempt() -> ChatGptAskResult:
            constraints = Screen(max_width=1920, max_height=1080)
            current_url = ""
            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constraints
            ) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path
                context = await browser.new_context(**context_options)
                await context.add_cookies([
                    {
                        "name": "__Secure-next-auth.session-token",
                        "value": session_cookie,
                        "domain": "chatgpt.com",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "None",
                    }
                ])
                page = await context.new_page()

                url = f"https://chatgpt.com/c/{chat_id}" if chat_id else "https://chatgpt.com/"
                await page.goto(url)

                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)

                popover = await page.query_selector(".popover")
                if popover:
                    popover_text = (await popover.inner_text()).lower()
                    if "area di lavoro" in popover_text or "workspace" in popover_text:
                        workspace_button = await popover.query_selector("button")
                        if workspace_button:
                            await workspace_button.click()
                            await page.wait_for_timeout(1000)
                            try:
                                await context.storage_state(path=self.storage_state_path)
                            except Exception as exc:
                                print(f"Errore salvataggio storage state: {exc}")

                if type_input:
                    await self._type_message(page, "#prompt-textarea", message)
                else:
                    await self._paste_message(page, "#prompt-textarea", message)

                await page.keyboard.press("Enter")

                try:
                    await page.wait_for_url("**/c/**", timeout=30_000)
                except Exception:
                    pass

                current_url = page.url

                try:
                    await page.close()
                    await context.close()
                except Exception as exc:
                    print(f"Errore durante la chiusura della pagina o del contesto: {exc}")

            slug = self._extract_slug_from_url(current_url if 'current_url' in locals() else url)
            return ChatGptAskResult(conversation_id=slug, message="")

        return await _attempt()

    def _load_session_cookie(self) -> str:
        """Carica il cookie di sessione salvato."""
        if not os.path.exists(self.cookie_path):
            raise FileNotFoundError("Cookie di sessione non trovato: esegui prima login()")

        with open(self.cookie_path, "r", encoding="utf-8") as f:
            cookie_value = f.read().strip()

        if not cookie_value:
            raise ValueError("Cookie di sessione vuoto")

        return cookie_value

    async def _fetch_conversation_via_browser(self, conversation_id: str, session_cookie: str) -> dict:
        conversation_url = f"https://chatgpt.com/backend-api/conversation/{conversation_id}"
        constraints = Screen(max_width=1920, max_height=1080)
        conversation_payload = {}
        response_received = asyncio.Event()

        async def handle_response(response):
            nonlocal conversation_payload
            if response.url != conversation_url:
                return
            try:
                conversation_payload = await response.json()
                response_received.set()
            except Exception as exc:
                print(f"Errore lettura conversazione: {exc}")

        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context_options = {}
            if os.path.exists(self.storage_state_path):
                context_options["storage_state"] = self.storage_state_path
            context = await browser.new_context(**context_options)
            await context.add_cookies([
                {
                    "name": "__Secure-next-auth.session-token",
                    "value": session_cookie,
                    "domain": "chatgpt.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "None",
                }
            ])
            page = await context.new_page()
            page.on("response", handle_response)

            url = f"https://chatgpt.com/c/{conversation_id}"
            await page.goto(url)
            await page.wait_for_load_state("networkidle")

            try:
                await asyncio.wait_for(response_received.wait(), timeout=30)
            except Exception:
                pass

            try:
                await context.storage_state(path=self.storage_state_path)
            except Exception as exc:
                print(f"Errore salvataggio storage state: {exc}")
            await page.close()
            await context.close()

        if not conversation_payload:
            raise Exception("Risposta conversazione non intercettata")
        return conversation_payload

    @staticmethod
    def _auth_headers(session_cookie: str, account_id: str = "") -> dict:
        headers = {
            "accept": "*/*",
            "authorization": f"Bearer {session_cookie}",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/144.0.0.0 Safari/537.36"
            ),
        }
        return headers

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
