import asyncio
from datetime import datetime
import json
import logging
import os
import time
from typing import Any, Literal, Optional

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
    CONVERSATION_FETCH_TIMEOUT_MS = 30_000
    CONVERSATION_PAGE_LOAD_TIMEOUT_MS = 10_000
    IMAGE_DOWNLOAD_GRACE_PERIOD_MS = 5_000

    @inject
    def __init__(
        self,
        session_dir: str,
        headless: bool | Literal["virtual"] = False,
        session_cookie: str = "",
        session_cookie_chunks: Optional[list[str]] = None,
        workspace_name: str = "",
    ):
        super().__init__()
        self.session_dir = os.path.join(session_dir, "chatgpt")
        self.storage_state_path = os.path.join(self.session_dir, "chatgpt_state.json")
        self.cookie_path = os.path.join(self.session_dir, "chatgpt_cookie.txt")
        self.headless = headless
        self.session_cookie = session_cookie
        self.session_cookie_chunks = session_cookie_chunks or []
        self.workspace_name = (workspace_name or "").strip()
        os.makedirs(self.session_dir, exist_ok=True)

    async def login(self, content: str) -> None:
        session_auth = self._resolve_session_auth_from_login_content(content)
        self._persist_session_auth(session_auth)

        constraints = Screen(max_width=1920, max_height=1080)
        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context = await browser.new_context()
            await context.add_cookies(session_auth["browser_cookies"])
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
        constraints = Screen(max_width=1920, max_height=1080)
        content = ""
        try:
            session_auth = self._load_session_auth(optional=True)
            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constraints,
            ) as browser:
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path
                context = await browser.new_context(**context_options)
                if session_auth:
                    await context.add_cookies(session_auth["browser_cookies"])

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
        session_auth = self._load_session_auth()

        url = self.CHAT_LIST_URL.format(offset=offset, limit=limit)

        with requests.Session() as session:
            response = self._requests_request(
                session,
                "GET",
                url,
                headers=self._auth_headers(session_auth["joined_value"], session_auth["cookie_header"], ""),
                timeout=30,
            )
            response.raise_for_status()
            return ConversationList.model_validate_json(response.text)

    async def get_conversation(self, chat_id: str) -> ConversationDetail:
        """Recupera i dettagli di una conversazione tramite il browser."""
        if not chat_id:
            raise ValueError("chat_id mancante")

        session_auth = self._load_session_auth()
        payload = await self._fetch_conversation_via_browser(chat_id, session_auth)
        return ConversationDetail.model_validate(payload)

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> ChatGptAskResult:
        """
        Invia un messaggio compilando #prompt-textarea, attende il completamento dello stream
        su /backend-api/f/conversation, poi copia l'ultima risposta cliccando il bottone
        con aria-label="Copia" e restituisce il contenuto della clipboard come ChatGptAskResult.
        """
        session_auth = self._load_session_auth()

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
                await context.add_cookies(session_auth["browser_cookies"])
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
        session_auth = self._load_session_auth()
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
            await context.add_cookies(session_auth["browser_cookies"])
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
        cookie_value = (self.session_cookie or "").strip()
        if cookie_value:
            return cookie_value

        if os.path.exists(self.cookie_path):
            persisted_auth = self._read_persisted_session_auth()
            if persisted_auth:
                return persisted_auth["joined_value"]

        raise ValueError("CHATGPT_SESSION_COOKIE mancante o vuoto")

    def _resolve_session_cookie_from_login_content(self, content: str) -> str:
        return self._resolve_session_auth_from_login_content(content)["joined_value"]

    def _resolve_session_auth_from_login_content(self, content: str) -> dict[str, Any]:
        parsed = AuthPayloadParser.parse(content)
        session_cookies = self._extract_session_cookies(parsed.cookies)
        if session_cookies:
            return self._create_session_auth_from_cookies(session_cookies)

        cookie_value = parsed.raw_text.strip()
        if not cookie_value:
            raise ValueError("Cookie ChatGPT '__Secure-next-auth.session-token' mancante")
        return self._create_session_auth_from_token(cookie_value)

    def _load_session_auth(self, optional: bool = False) -> Optional[dict[str, Any]]:
        cookie_value = (self.session_cookie or "").strip()
        if cookie_value:
            return self._create_session_auth_from_token(cookie_value)

        if self.session_cookie_chunks:
            return self._create_session_auth_from_chunk_values(self.session_cookie_chunks)

        if os.path.exists(self.cookie_path):
            persisted_auth = self._read_persisted_session_auth()
            if persisted_auth:
                return persisted_auth

        if optional:
            return None
        raise ValueError("CHATGPT_SESSION_COOKIE mancante o vuoto")

    def _read_persisted_session_auth(self) -> Optional[dict[str, Any]]:
        raw_content = self._read_text_file(self.cookie_path)
        if not raw_content:
            return None

        if raw_content.startswith("{"):
            try:
                persisted = json.loads(raw_content)
            except json.JSONDecodeError:
                return self._create_session_auth_from_token(raw_content)
            cookies = persisted.get("cookies") if isinstance(persisted, dict) else None
            if isinstance(cookies, list):
                return self._create_session_auth_from_cookies(cookies)

        return self._create_session_auth_from_token(raw_content)

    def _persist_session_auth(self, session_auth: dict[str, Any]) -> None:
        if session_auth.get("is_chunked"):
            self._write_json_file(self.cookie_path, {"cookies": session_auth["browser_cookies"]})
            return
        self._write_text_file(self.cookie_path, session_auth["joined_value"])

    @staticmethod
    def _build_session_cookie(name: str, value: str) -> dict[str, Any]:
        return {
            "name": name,
            "value": value,
            "domain": "chatgpt.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        }

    @classmethod
    def _create_session_auth_from_token(cls, cookie_value: str) -> dict[str, Any]:
        browser_cookies = [cls._build_session_cookie("__Secure-next-auth.session-token", cookie_value)]
        return {
            "is_chunked": False,
            "joined_value": cookie_value,
            "browser_cookies": browser_cookies,
            "cookie_header": cls._build_cookie_header(browser_cookies),
        }

    @classmethod
    def _create_session_auth_from_chunk_values(cls, chunk_values: list[str]) -> dict[str, Any]:
        normalized_values = []
        for index, value in enumerate(chunk_values):
            normalized_value = str(value).strip()
            if not normalized_value:
                raise ValueError(f"CHATGPT_SESSION_COOKIE_{index} mancante o vuoto")
            normalized_values.append(normalized_value)

        browser_cookies = [
            cls._build_session_cookie(f"__Secure-next-auth.session-token.{index}", value)
            for index, value in enumerate(normalized_values)
        ]
        return {
            "is_chunked": True,
            "joined_value": "".join(normalized_values),
            "browser_cookies": browser_cookies,
            "cookie_header": cls._build_cookie_header(browser_cookies),
        }

    @classmethod
    def _create_session_auth_from_cookies(cls, cookies: list[dict[str, Any]]) -> dict[str, Any]:
        chunk_values: list[str] = []
        single_value = ""
        for cookie in cookies:
            name = str(cookie.get("name", "")).strip()
            if name == "__Secure-next-auth.session-token":
                single_value = str(cookie.get("value", ""))
            elif name.startswith("__Secure-next-auth.session-token."):
                suffix = name.rsplit(".", 1)[-1]
                if suffix.isdigit():
                    index = int(suffix)
                    while len(chunk_values) <= index:
                        chunk_values.append("")
                    chunk_values[index] = str(cookie.get("value", ""))

        if single_value:
            return cls._create_session_auth_from_token(single_value)
        if chunk_values:
            return cls._create_session_auth_from_chunk_values(chunk_values)
        raise ValueError("Cookie ChatGPT '__Secure-next-auth.session-token' mancante")

    @staticmethod
    def _extract_session_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        session_cookies = []
        for cookie in cookies:
            name = str(cookie.get("name", "")).strip()
            if name == "__Secure-next-auth.session-token" or name.startswith("__Secure-next-auth.session-token."):
                session_cookies.append(cookie)
        return session_cookies

    @staticmethod
    def _build_cookie_header(cookies: list[dict[str, Any]]) -> str:
        return "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)

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

    async def _fetch_conversation_via_browser(self, chat_id: str, session_auth: dict[str, Any]) -> dict:
        constraints = Screen(max_width=1920, max_height=1080)

        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context_options = {}
            if os.path.exists(self.storage_state_path):
                context_options["storage_state"] = self.storage_state_path
            context = await browser.new_context(**context_options)
            await context.add_cookies(session_auth["browser_cookies"])
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
        image_download_url = ""
        last_image_seen_at = 0.0

        async def handle_response(response):
            nonlocal image_download_url, last_image_seen_at
            try:
                if "/backend-api/files/download/" in response.url and f"conversation_id={chat_id}" in response.url:
                    payload = await response.json()
                    if isinstance(payload, dict) and payload.get("download_url"):
                        image_download_url = payload["download_url"]
                        last_image_seen_at = time.monotonic()
            except Exception as exc:
                logger.warning("Error parsing ChatGPT response payload: %s", exc)

        page.on("response", handle_response)

        url = f"https://chatgpt.com/c/{chat_id}"
        async with page.expect_response(
            lambda response: self._is_matching_conversation_response(response.url, conversation_url),
            timeout=self.CONVERSATION_FETCH_TIMEOUT_MS,
        ) as conversation_response_info:
            await self._goto(page, url, wait_until="domcontentloaded", timeout=self.CONVERSATION_PAGE_LOAD_TIMEOUT_MS)
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=self.CONVERSATION_PAGE_LOAD_TIMEOUT_MS)
            except Exception:
                logger.info("Conversation page did not reach domcontentloaded quickly; continuing")

        conversation_response = await conversation_response_info.value
        conversation_payload = await conversation_response.json()
        await page.wait_for_timeout(self.IMAGE_DOWNLOAD_GRACE_PERIOD_MS)

        if last_image_seen_at > 0:
            while True:
                elapsed = time.monotonic() - last_image_seen_at
                if elapsed >= 2.0:
                    break
                await page.wait_for_timeout(200)

        if image_download_url:
            initial_image_download_url = image_download_url
            image_download_url = ""
            last_image_seen_at = 0.0
            await page.wait_for_timeout(self.IMAGE_DOWNLOAD_GRACE_PERIOD_MS)
            try:
                await page.reload(wait_until="domcontentloaded", timeout=self.CONVERSATION_PAGE_LOAD_TIMEOUT_MS)
                await page.wait_for_load_state("domcontentloaded", timeout=self.CONVERSATION_PAGE_LOAD_TIMEOUT_MS)
            except Exception:
                logger.info("Conversation page reload did not reach domcontentloaded quickly; continuing")
            await page.wait_for_timeout(self.IMAGE_DOWNLOAD_GRACE_PERIOD_MS)

            if last_image_seen_at > 0:
                while True:
                    elapsed = time.monotonic() - last_image_seen_at
                    if elapsed >= 2.0:
                        break
                    await page.wait_for_timeout(200)

            if not image_download_url:
                image_download_url = initial_image_download_url

        if not conversation_payload:
            raise Exception("Risposta conversazione non intercettata")
        if image_download_url:
            conversation_payload["image_download_url"] = image_download_url
        return conversation_payload

    @staticmethod
    def _is_matching_conversation_response(response_url: str, conversation_url: str) -> bool:
        normalized_response_url = response_url.split("?", 1)[0].rstrip("/")
        normalized_conversation_url = conversation_url.rstrip("/")
        return normalized_response_url == normalized_conversation_url

    def proxy_download(self, download_url: str) -> tuple[bytes, int, str, str]:
        """Proxy download usando il cookie ChatGPT in header Cookie."""
        if not download_url:
            raise ValueError("download_url mancante")
        if not download_url.startswith("https://chatgpt.com/"):
            raise ValueError("download_url non valida: deve iniziare con https://chatgpt.com/")

        session_auth = self._load_session_auth()
        headers = {
            "Cookie": session_auth["cookie_header"],
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
    def _auth_headers(session_cookie: str, cookie_header: str = "", account_id: str = "") -> dict:
        headers = {
            "accept": "*/*",
            "authorization": f"Bearer {session_cookie}",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/144.0.0.0 Safari/537.36"
            ),
        }
        if cookie_header:
            headers["cookie"] = cookie_header
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
