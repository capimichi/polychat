import asyncio
from datetime import datetime
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
    def __init__(
        self,
        session_dir: str,
        headless: bool = False,
        session_cookie: str = "",
        workspace_name: str = "",
    ):
        self.session_dir = session_dir
        self.storage_state_path = os.path.join(session_dir, "chatgpt_state.json")
        self.headless = headless
        self.session_cookie = session_cookie
        self.workspace_name = (workspace_name or "").strip()

    def logout(self) -> None:
        """Rimuove solo lo storage state salvato."""
        if os.path.exists(self.storage_state_path):
            os.remove(self.storage_state_path)

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

                if self.workspace_name:
                    await self._select_workspace_by_name(page, self.workspace_name)
                    await page.wait_for_timeout(1000)
                    try:
                        await context.storage_state(path=self.storage_state_path)
                    except Exception as exc:
                        print(f"Errore salvataggio storage state: {exc}")

                try:
                    await page.wait_for_selector("#prompt-textarea", timeout=5_000)
                except Exception as exc:
                    await self._raise_input_timeout(page, exc)

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
        """Carica il cookie di sessione da variabile ambiente."""
        cookie_value = (self.session_cookie or "").strip()
        if not cookie_value:
            raise ValueError("CHATGPT_SESSION_COOKIE mancante o vuoto")

        return cookie_value

    async def _select_workspace_by_name(self, page, workspace_name: str) -> None:
        target_name = " ".join(workspace_name.strip().lower().split())
        if not target_name:
            return

        popover = await page.query_selector(".popover")
        if not popover:
            raise Exception(
                f"Workspace picker non trovato: impossibile selezionare workspace '{workspace_name}'."
            )

        popover_text = " ".join(((await popover.inner_text()) or "").lower().split())
        if "area di lavoro" not in popover_text and "workspace" not in popover_text:
            raise Exception(
                f"Workspace picker non disponibile: impossibile selezionare workspace '{workspace_name}'."
            )

        workspace_button = await popover.query_selector("button")
        if not workspace_button:
            raise Exception(
                f"Pulsante workspace non trovato: impossibile selezionare workspace '{workspace_name}'."
            )

        await workspace_button.click()
        await page.wait_for_timeout(500)

        candidates = await page.query_selector_all("button, [role='option'], [role='menuitem']")
        for candidate in candidates:
            text = " ".join(((await candidate.inner_text()) or "").lower().split())
            if text == target_name:
                await candidate.click()
                return

        raise Exception(f"Workspace '{workspace_name}' non trovato.")

    async def _raise_input_timeout(self, page, original_exception: Exception) -> None:
        screenshots_dir = os.path.join(os.path.dirname(self.session_dir), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        screenshot_path = os.path.join(screenshots_dir, f"chatgpt-input-timeout-{timestamp}.png")

        try:
            await page.screenshot(path=screenshot_path, full_page=True)
        except Exception:
            screenshot_path = f"{screenshot_path} (screenshot non riuscito)"

        raise TimeoutError(
            "Input '#prompt-textarea' non trovato entro 5 secondi. "
            f"Screenshot creato: {screenshot_path}. "
            "Verifica se è necessario fornire CHATGPT_WORKSPACE_NAME per selezionare il workspace corretto."
        ) from original_exception

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
