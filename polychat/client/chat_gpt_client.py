import asyncio
from datetime import datetime
import logging
import os
import time
from typing import Literal, Optional

import requests
from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from injector import inject

from polychat.client.abstract_client import AbstractClient
from polychat.model.client.chatgpt_ask_result import ChatGptAskResult
from polychat.model.client.chatgpt_conversation_detail import ConversationDetail
from polychat.model.client.chatgpt_conversation_list import ConversationList
from polychat.parser.auth_payload_parser import AuthPayloadParser

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
    PROMPT_SHORTCUT_WAIT_MS = 1_000
    WAIT_FOR_URL_TIMEOUT_MS = 8_000
    POST_SUBMIT_WAIT_MS = 5_000
    COMPLETE_WAIT_TIMEOUT_SECONDS = 60.0
    COMPLETE_WAIT_CHECK_INTERVAL_SECONDS = 2.0

    @inject
    def __init__(
        self,
        session_dir: str,
        headless: bool | Literal["virtual"] = False,
        session_cookie: str = "",
        workspace_name: str = "",
    ):
        super().__init__()
        self.session_dir = os.path.join(session_dir, "chatgpt")
        self.storage_state_path = os.path.join(self.session_dir, "chatgpt_state.json")
        self.cookie_path = os.path.join(self.session_dir, "chatgpt_cookie.txt")
        self.headless = headless
        self.session_cookie = session_cookie
        self.workspace_name = (workspace_name or "").strip()
        os.makedirs(self.session_dir, exist_ok=True)

    async def login(self, content: str) -> None:
        session_cookie = self._resolve_session_cookie_from_login_content(content)
        self._write_text_file(self.cookie_path, session_cookie)

        constraints = Screen(max_width=1920, max_height=1080)
        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context = await browser.new_context()
            await context.add_cookies([self._build_session_cookie(session_cookie)])
            page = await context.new_page()
            self._attach_page_request_logger(page)
            await self._goto(page, "https://chatgpt.com/", wait_until="domcontentloaded", timeout=20_000)
            await page.wait_for_timeout(1_500)
            await context.storage_state(path=self.storage_state_path)
            await page.close()
            await context.close()

    def logout(self) -> None:
        """Rimuove la cartella sessione ChatGPT."""
        self._clear_session_dir(self.session_dir)

    async def status(self) -> dict:
        session_cookie = (self.session_cookie or "").strip()
        constraints = Screen(max_width=1920, max_height=1080)
        content = ""
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
                if session_cookie:
                    await context.add_cookies([self._build_session_cookie(session_cookie)])

                page = await context.new_page()
                self._attach_page_request_logger(page)
                await self._goto(page, "https://chatgpt.com/", wait_until="domcontentloaded", timeout=20_000)
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
                "provider": "chatgpt",
                "is_available": False,
                "is_logged_in": False,
                "detail": f"Status check failed: {exc}",
            }

        marker = '"authStatus":"logged_in"'
        is_logged_in = marker in content
        return {
            "provider": "chatgpt",
            "is_available": True,
            "is_logged_in": is_logged_in,
            "detail": None if is_logged_in else "Marker auth non trovato nella homepage",
        }

    def get_conversations(self, offset: int = 0, limit: int = 28) -> ConversationList:
        """Recupera la lista delle conversazioni esistenti."""
        session_cookie = self._load_session_cookie()

        url = self.CHAT_LIST_URL.format(offset=offset, limit=limit)

        with requests.Session() as session:
            response = self._requests_request(
                session,
                "GET",
                url,
                headers=self._auth_headers(session_cookie, ""),
                timeout=30,
            )
            response.raise_for_status()
            return ConversationList.model_validate_json(response.text)

    async def get_conversation(self, chat_id: str) -> ConversationDetail:
        """Recupera i dettagli di una conversazione tramite il browser."""
        if not chat_id:
            raise ValueError("chat_id mancante")

        session_cookie = self._load_session_cookie()
        payload = await self._fetch_conversation_via_browser(chat_id, session_cookie)
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
                await context.add_cookies([self._build_session_cookie(session_cookie)])
                page = await context.new_page()
                self._attach_page_request_logger(page)

                url = f"https://chatgpt.com/c/{chat_id}" if chat_id else "https://chatgpt.com/"
                logger.info("Opening ChatGPT page: %s", url)
                await self._goto(page, url, wait_until="domcontentloaded", timeout=12_000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=4_000)
                except Exception:
                    logger.info("Network idle not reached quickly; continuing anyway")
                await page.wait_for_timeout(self.POST_NAVIGATION_WAIT_MS)
                await self._ensure_workspace_active(page)

                if self.workspace_name:
                    logger.info("Workspace configured; selecting workspace by name: %s", self.workspace_name)
                    await self._select_workspace_by_name(page, self.workspace_name)
                    await page.wait_for_timeout(self.POST_RECOVERY_WAIT_MS)
                    try:
                        await context.storage_state(path=self.storage_state_path)
                    except Exception as exc:
                        logger.warning("Unable to persist ChatGPT storage state: %s", exc)

                await self._focus_prompt_input(page)

                if type_input:
                    logger.info("Typing prompt content in textarea")
                    try:
                        await self._type_into_focused_input(page, message)
                    except Exception:
                        await self._ensure_workspace_active(page)
                        await self._focus_prompt_input(page)
                        try:
                            await self._type_into_focused_input(page, message)
                        except Exception as retry_exc:
                            screenshot_path = await self._capture_debug_screenshot(page, "input-interaction")
                            raise RuntimeError(
                                f"Errore durante interazione con input '{self.PROMPT_SELECTOR}'. "
                                f"Screenshot creato: {screenshot_path}."
                            ) from retry_exc
                else:
                    logger.info("Pasting prompt content in textarea")
                    try:
                        await self._paste_into_focused_input(page, message)
                    except Exception:
                        await self._ensure_workspace_active(page)
                        await self._focus_prompt_input(page)
                        try:
                            await self._paste_into_focused_input(page, message)
                        except Exception as retry_exc:
                            screenshot_path = await self._capture_debug_screenshot(page, "input-interaction")
                            raise RuntimeError(
                                f"Errore durante interazione con input '{self.PROMPT_SELECTOR}'. "
                                f"Screenshot creato: {screenshot_path}."
                            ) from retry_exc

                await page.keyboard.press("Enter")
                logger.info("Prompt submitted; waiting for conversation URL")

                try:
                    await page.wait_for_url("**/c/**", timeout=self.WAIT_FOR_URL_TIMEOUT_MS)
                except Exception:
                    logger.info("Conversation URL not detected within timeout; continuing")

                logger.info("Waiting %sms before closing page after submit", self.POST_SUBMIT_WAIT_MS)
                await page.wait_for_timeout(self.POST_SUBMIT_WAIT_MS)

                current_url = page.url
                logger.info("Current page URL after submit: %s", current_url)

                try:
                    await page.close()
                    await context.close()
                except Exception as exc:
                    logger.warning("Error while closing ChatGPT page/context: %s", exc)

            slug = self._extract_slug_from_url(current_url if 'current_url' in locals() else url)
            logger.info("ChatGPT ask completed (chat_id=%s)", slug)
            return ChatGptAskResult(chat_id=slug, message="")

        return await _attempt()

    async def ask_and_wait(
        self,
        message: str,
        chat_id: Optional[str] = None,
        type_input: bool = True,
    ) -> ConversationDetail:
        session_cookie = self._load_session_cookie()
        constraints = Screen(max_width=1920, max_height=1080)

        logger.info("ChatGPT ask_and_wait started (chat_id=%s, workspace=%s)", chat_id, self.workspace_name or "<none>")
        async with AsyncCamoufox(
            headless=self.headless,
            humanize=True,
            screen=constraints
        ) as browser:
            context_options = {}
            if os.path.exists(self.storage_state_path):
                context_options["storage_state"] = self.storage_state_path
            context = await browser.new_context(**context_options)
            await context.add_cookies([self._build_session_cookie(session_cookie)])
            page = await context.new_page()
            self._attach_page_request_logger(page)

            try:
                resolved_chat_id = await self._submit_prompt(page, message, chat_id, type_input)
                await self._wait_for_network_to_settle(
                    page,
                    timeout_seconds=self.COMPLETE_WAIT_TIMEOUT_SECONDS,
                    check_interval_seconds=self.COMPLETE_WAIT_CHECK_INTERVAL_SECONDS,
                )
                payload = await self._fetch_conversation_via_page(page, resolved_chat_id)
                return ConversationDetail.model_validate(payload)
            finally:
                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception as exc:
                    logger.warning("Unable to persist ChatGPT storage state: %s", exc)
                await page.close()
                await context.close()

    def _load_session_cookie(self) -> str:
        """Carica il cookie di sessione da variabile ambiente."""
        cookie_value = (self.session_cookie or "").strip()
        if cookie_value:
            return cookie_value

        if os.path.exists(self.cookie_path):
            cookie_value = self._read_text_file(self.cookie_path)
            if cookie_value:
                return cookie_value

        raise ValueError("CHATGPT_SESSION_COOKIE mancante o vuoto")

    def _resolve_session_cookie_from_login_content(self, content: str) -> str:
        parsed = AuthPayloadParser.parse(content)
        for cookie in parsed.cookies:
            if cookie.get("name") == "__Secure-next-auth.session-token":
                return str(cookie["value"])

        cookie_value = parsed.raw_text.strip()
        if not cookie_value:
            raise ValueError("Cookie ChatGPT '__Secure-next-auth.session-token' mancante")
        return cookie_value

    @staticmethod
    def _build_session_cookie(session_cookie: str) -> dict:
        return {
            "name": "__Secure-next-auth.session-token",
            "value": session_cookie,
            "domain": "chatgpt.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        }

    async def _select_workspace_by_name(self, page, workspace_name: str) -> None:
        target_name = " ".join(workspace_name.strip().lower().split())
        if not target_name:
            return

        logger.info("Searching workspace '%s'", workspace_name)
        popover = await page.query_selector(".popover")
        if not popover:
            logger.info("Workspace picker popover not found; skipping workspace selection")
            return

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

    async def _ensure_workspace_active(self, page) -> None:
        needs_selection = "workspace/deactivated" in (page.url or "")
        if not needs_selection:
            needs_selection = (await page.query_selector("text=Select a workspace to continue")) is not None
        if not needs_selection:
            return

        logger.info("Detected deactivated workspace screen; selecting an active workspace")
        if self.workspace_name:
            try:
                await self._select_workspace_by_name(page, self.workspace_name)
                await page.wait_for_timeout(self.POST_RECOVERY_WAIT_MS)
                return
            except Exception as exc:
                logger.warning("Configured workspace selection failed: %s", exc)

        options = await page.query_selector_all("button, [role='button'], [role='option'], [role='menuitem']")
        for option in options:
            text = " ".join(((await option.inner_text()) or "").lower().split())
            if not text:
                continue
            if "select a workspace to continue" in text:
                continue
            if "deactivated" in text:
                continue
            await option.click()
            await page.wait_for_timeout(self.POST_RECOVERY_WAIT_MS)
            return

        raise Exception(
            "Workspace disattivato e nessun workspace alternativo selezionabile trovato."
        )

    async def _focus_prompt_input(self, page) -> None:
        logger.info("Focusing prompt input via shortcut ControlOrMeta+Shift+O")
        await page.keyboard.press("ControlOrMeta+Shift+O")
        await page.wait_for_timeout(self.PROMPT_SHORTCUT_WAIT_MS)

    async def _type_into_focused_input(self, page, content: str) -> None:
        safe_content = self._sanitize_message(content)
        await page.keyboard.type(safe_content)

    async def _paste_into_focused_input(self, page, content: str) -> None:
        safe_content = self._sanitize_message(content)
        await page.keyboard.insert_text(safe_content)

    async def _raise_input_timeout(self, page, original_exception: Exception) -> None:
        screenshot_path = await self._capture_debug_screenshot(page, "input-timeout")
        logger.error("Prompt textarea timeout. Screenshot path: %s", screenshot_path)

        raise TimeoutError(
            f"Input '{self.PROMPT_SELECTOR}' non trovato entro "
            f"{self.PROMPT_MAX_ATTEMPTS * self.PROMPT_WAIT_TIMEOUT_MS / 1000:.1f} secondi. "
            f"Screenshot creato: {screenshot_path}. "
            "Verifica se è necessario fornire CHATGPT_WORKSPACE_NAME per selezionare il workspace corretto."
        ) from original_exception

    async def _capture_debug_screenshot(self, page, reason: str) -> str:
        screenshots_dir = os.path.join(os.path.dirname(self.session_dir), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        screenshot_path = os.path.join(screenshots_dir, f"chatgpt-{reason}-{timestamp}.png")

        try:
            await page.screenshot(path=screenshot_path, full_page=True)
            return screenshot_path
        except Exception as exc:
            failed_path = f"{screenshot_path} (screenshot non riuscito)"
            logger.warning("Unable to create debug screenshot: %s", exc)
            return failed_path

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

    async def _fetch_conversation_via_browser(self, chat_id: str, session_cookie: str) -> dict:
        constraints = Screen(max_width=1920, max_height=1080)

        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context_options = {}
            if os.path.exists(self.storage_state_path):
                context_options["storage_state"] = self.storage_state_path
            context = await browser.new_context(**context_options)
            await context.add_cookies([self._build_session_cookie(session_cookie)])
            page = await context.new_page()
            self._attach_page_request_logger(page)
            conversation_payload = await self._fetch_conversation_via_page(page, chat_id)

            try:
                await context.storage_state(path=self.storage_state_path)
            except Exception as exc:
                logger.warning("Unable to persist ChatGPT storage state: %s", exc)
            await page.close()
            await context.close()

        return conversation_payload

    async def _submit_prompt(
        self,
        page,
        message: str,
        chat_id: Optional[str],
        type_input: bool,
    ) -> str:
        url = f"https://chatgpt.com/c/{chat_id}" if chat_id else "https://chatgpt.com/"
        logger.info("Opening ChatGPT page: %s", url)
        await self._goto(page, url, wait_until="domcontentloaded", timeout=12_000)
        try:
            await page.wait_for_load_state("networkidle", timeout=4_000)
        except Exception:
            logger.info("Network idle not reached quickly; continuing anyway")
        await page.wait_for_timeout(self.POST_NAVIGATION_WAIT_MS)
        await self._ensure_workspace_active(page)

        if self.workspace_name:
            logger.info("Workspace configured; selecting workspace by name: %s", self.workspace_name)
            await self._select_workspace_by_name(page, self.workspace_name)
            await page.wait_for_timeout(self.POST_RECOVERY_WAIT_MS)

        await self._focus_prompt_input(page)

        if type_input:
            logger.info("Typing prompt content in textarea")
            try:
                await self._type_into_focused_input(page, message)
            except Exception:
                await self._ensure_workspace_active(page)
                await self._focus_prompt_input(page)
                try:
                    await self._type_into_focused_input(page, message)
                except Exception as retry_exc:
                    screenshot_path = await self._capture_debug_screenshot(page, "input-interaction")
                    raise RuntimeError(
                        f"Errore durante interazione con input '{self.PROMPT_SELECTOR}'. "
                        f"Screenshot creato: {screenshot_path}."
                    ) from retry_exc
        else:
            logger.info("Pasting prompt content in textarea")
            try:
                await self._paste_into_focused_input(page, message)
            except Exception:
                await self._ensure_workspace_active(page)
                await self._focus_prompt_input(page)
                try:
                    await self._paste_into_focused_input(page, message)
                except Exception as retry_exc:
                    screenshot_path = await self._capture_debug_screenshot(page, "input-interaction")
                    raise RuntimeError(
                        f"Errore durante interazione con input '{self.PROMPT_SELECTOR}'. "
                        f"Screenshot creato: {screenshot_path}."
                    ) from retry_exc

        await page.keyboard.press("Enter")
        logger.info("Prompt submitted; waiting for conversation URL")

        try:
            await page.wait_for_url("**/c/**", timeout=self.WAIT_FOR_URL_TIMEOUT_MS)
        except Exception:
            logger.info("Conversation URL not detected within timeout; continuing")

        logger.info("Waiting %sms before continuing after submit", self.POST_SUBMIT_WAIT_MS)
        await page.wait_for_timeout(self.POST_SUBMIT_WAIT_MS)

        current_url = page.url or ""
        logger.info("Current page URL after submit: %s", current_url)

        slug = self._extract_slug_from_url(current_url if current_url else url)
        logger.info("ChatGPT submit completed (chat_id=%s)", slug)
        return slug

    async def _fetch_conversation_via_page(self, page, chat_id: str) -> dict:  # noqa: ANN001
        conversation_url = f"https://chatgpt.com/backend-api/conversation/{chat_id}"
        conversation_payload = {}
        image_download_url = ""
        response_received = asyncio.Event()
        last_image_seen_at = 0.0

        async def handle_response(response):
            nonlocal conversation_payload, image_download_url, last_image_seen_at
            try:
                if response.url == conversation_url:
                    conversation_payload = await response.json()
                    response_received.set()
                    return

                if "/backend-api/files/download/" in response.url and f"conversation_id={chat_id}" in response.url:
                    payload = await response.json()
                    if isinstance(payload, dict) and payload.get("download_url"):
                        image_download_url = payload["download_url"]
                        last_image_seen_at = time.monotonic()
            except Exception as exc:
                logger.warning("Error parsing ChatGPT response payload: %s", exc)

        page.on("response", handle_response)

        url = f"https://chatgpt.com/c/{chat_id}"
        await self._goto(page, url)
        await page.wait_for_load_state("networkidle")
        wait_timeout_ms = 30_000
        poll_interval_ms = 1_000
        elapsed_ms = 0

        while not response_received.is_set() and elapsed_ms < wait_timeout_ms:
            await page.wait_for_timeout(poll_interval_ms)
            elapsed_ms += poll_interval_ms

        if response_received.is_set() and last_image_seen_at > 0:
            while True:
                elapsed = time.monotonic() - last_image_seen_at
                if elapsed >= 2.0:
                    break
                await page.wait_for_timeout(200)

        if not conversation_payload:
            raise Exception("Risposta conversazione non intercettata")
        if image_download_url:
            conversation_payload["image_download_url"] = image_download_url
        return conversation_payload

    def proxy_download(self, download_url: str) -> tuple[bytes, int, str, str]:
        """Proxy download usando il cookie ChatGPT in header Cookie."""
        if not download_url:
            raise ValueError("download_url mancante")
        if not download_url.startswith("https://chatgpt.com/"):
            raise ValueError("download_url non valida: deve iniziare con https://chatgpt.com/")

        session_cookie = self._load_session_cookie()
        headers = {
            "Cookie": f"__Secure-next-auth.session-token={session_cookie}",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/144.0.0.0 Safari/537.36"
            ),
        }

        with requests.Session() as session:
            response = self._requests_request(session, "GET", download_url, headers=headers, timeout=60)
            response.raise_for_status()
            content = response.content
            status_code = response.status_code
            content_type = response.headers.get("content-type", "application/octet-stream")
            content_disposition = response.headers.get("content-disposition", "")
            return content, status_code, content_type, content_disposition

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
