import asyncio
from datetime import datetime
import logging
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

logger = logging.getLogger(__name__)


class ChatGptClient(AbstractClient):
    CHAT_LIST_URL = (
        "https://chatgpt.com/backend-api/conversations?"
        "offset={offset}&limit={limit}&order=updated&is_archived=false&"
        "is_starred=false&request_p_scope=false"
    )
    PROMPT_SELECTOR = "#prompt-textarea"
    PROMPT_WAIT_TIMEOUT_MS = 3_500
    PROMPT_MAX_ATTEMPTS = 3
    POST_NAVIGATION_WAIT_MS = 400
    POST_RECOVERY_WAIT_MS = 250
    WAIT_FOR_URL_TIMEOUT_MS = 8_000

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
            logger.info("ChatGPT ask started (chat_id=%s, workspace=%s)", chat_id, self.workspace_name or "<none>")
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
                logger.info("Opening ChatGPT page: %s", url)
                await page.goto(url, wait_until="domcontentloaded", timeout=12_000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=4_000)
                except Exception:
                    logger.info("Network idle not reached quickly; continuing anyway")
                await page.wait_for_timeout(self.POST_NAVIGATION_WAIT_MS)

                if self.workspace_name:
                    logger.info("Workspace configured; selecting workspace by name: %s", self.workspace_name)
                    await self._select_workspace_by_name(page, self.workspace_name)
                    await page.wait_for_timeout(self.POST_RECOVERY_WAIT_MS)
                    try:
                        await context.storage_state(path=self.storage_state_path)
                    except Exception as exc:
                        logger.warning("Unable to persist ChatGPT storage state: %s", exc)

                for attempt in range(1, self.PROMPT_MAX_ATTEMPTS + 1):
                    try:
                        logger.info(
                            "Waiting for prompt textarea (attempt=%s/%s, timeout_ms=%s)",
                            attempt,
                            self.PROMPT_MAX_ATTEMPTS,
                            self.PROMPT_WAIT_TIMEOUT_MS,
                        )
                        await page.wait_for_selector(self.PROMPT_SELECTOR, timeout=self.PROMPT_WAIT_TIMEOUT_MS)
                        logger.info("Prompt textarea found")
                        break
                    except Exception as exc:
                        logger.info("Prompt textarea not found on attempt %s; trying recovery actions", attempt)
                        recovered = await self._try_select_other_work_category(page)
                        if not recovered:
                            recovered = await self._try_skip_apps_at_work_selection(page)
                        if not recovered:
                            logger.error("No recovery action matched; raising timeout")
                            await self._raise_input_timeout(page, exc)

                if type_input:
                    logger.info("Typing prompt content in textarea")
                    await self._type_message(page, self.PROMPT_SELECTOR, message)
                else:
                    logger.info("Pasting prompt content in textarea")
                    await self._paste_message(page, self.PROMPT_SELECTOR, message)

                await page.keyboard.press("Enter")
                logger.info("Prompt submitted; waiting for conversation URL")

                try:
                    await page.wait_for_url("**/c/**", timeout=self.WAIT_FOR_URL_TIMEOUT_MS)
                except Exception:
                    logger.info("Conversation URL not detected within timeout; continuing")

                current_url = page.url
                logger.info("Current page URL after submit: %s", current_url)

                try:
                    await page.close()
                    await context.close()
                except Exception as exc:
                    logger.warning("Error while closing ChatGPT page/context: %s", exc)

            slug = self._extract_slug_from_url(current_url if 'current_url' in locals() else url)
            logger.info("ChatGPT ask completed (conversation_id=%s)", slug)
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

        logger.info("Searching workspace '%s'", workspace_name)
        popover = await page.query_selector(".popover")
        if not popover:
            logger.error("Workspace picker popover not found")
            raise Exception(
                f"Workspace picker non trovato: impossibile selezionare workspace '{workspace_name}'."
            )

        popover_text = " ".join(((await popover.inner_text()) or "").lower().split())
        if "area di lavoro" not in popover_text and "workspace" not in popover_text:
            logger.error("Workspace picker popover found but does not contain workspace text")
            raise Exception(
                f"Workspace picker non disponibile: impossibile selezionare workspace '{workspace_name}'."
            )

        candidates = await popover.query_selector_all("button, [role='option'], [role='menuitem']")
        if not candidates:
            candidates = await page.query_selector_all("button, [role='option'], [role='menuitem']")
        for candidate in candidates:
            text = " ".join(((await candidate.inner_text()) or "").lower().split())
            if text == target_name:
                await candidate.click()
                logger.info("Workspace selected successfully: %s", workspace_name)
                return

        logger.error("Workspace not found in picker: %s", workspace_name)
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
        logger.error("Prompt textarea timeout. Screenshot path: %s", screenshot_path)

        raise TimeoutError(
            f"Input '{self.PROMPT_SELECTOR}' non trovato entro "
            f"{self.PROMPT_MAX_ATTEMPTS * self.PROMPT_WAIT_TIMEOUT_MS / 1000:.1f} secondi. "
            f"Screenshot creato: {screenshot_path}. "
            "Verifica se è necessario fornire CHATGPT_WORKSPACE_NAME per selezionare il workspace corretto."
        ) from original_exception

    async def _try_select_other_work_category(self, page) -> bool:
        prompt = await page.query_selector("text=What kind of work do you do?")
        if not prompt:
            return False

        logger.info("Detected work category onboarding; clicking 'Other'")
        other_button = await page.query_selector("button:has-text('Other')")
        if not other_button:
            buttons = await page.query_selector_all("button")
            for button in buttons:
                text = " ".join(((await button.inner_text()) or "").lower().split())
                if text == "other":
                    other_button = button
                    break

        if not other_button:
            return False

        await other_button.click()
        await page.wait_for_timeout(self.POST_RECOVERY_WAIT_MS)
        logger.info("Clicked 'Other' in work category onboarding")
        return True

    async def _try_skip_apps_at_work_selection(self, page) -> bool:
        prompt = await page.query_selector("text=Select apps you use at work")
        if not prompt:
            return False

        logger.info("Detected apps-at-work onboarding; clicking 'Skip'")
        skip_button = await page.query_selector("button:has-text('Skip')")
        if not skip_button:
            buttons = await page.query_selector_all("button")
            for button in buttons:
                text = " ".join(((await button.inner_text()) or "").lower().split())
                if text == "skip":
                    skip_button = button
                    break

        if not skip_button:
            return False

        await skip_button.click()
        await page.wait_for_timeout(self.POST_RECOVERY_WAIT_MS)
        logger.info("Clicked 'Skip' in apps-at-work onboarding")
        return True

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
                logger.warning("Error parsing conversation payload: %s", exc)

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
                logger.warning("Unable to persist ChatGPT storage state: %s", exc)
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
