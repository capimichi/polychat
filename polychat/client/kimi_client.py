import os
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from browserforge.fingerprints import Screen
from camoufox.async_api import AsyncCamoufox
from injector import inject
from strip_tags import strip_tags

from polychat.client.abstract_client import AbstractClient
from polychat.model.client.kimi_response import KimiResponse
from polychat.parser.auth_payload_parser import AuthPayloadParser


class KimiClient(AbstractClient):
    """Client per interagire con Kimi tramite automazione browser."""

    BASE_URL = "https://www.kimi.com/"
    GET_CHAT_URL = "https://www.kimi.com/apiv2/kimi.gateway.chat.v1.ChatService/GetChat"
    POST_SUBMIT_WAIT_MS = 5_000
    COMPLETE_WAIT_TIMEOUT_SECONDS = 60.0
    COMPLETE_WAIT_CHECK_INTERVAL_SECONDS = 2.0
    GET_CHAT_WAIT_TIMEOUT_MS = 10_000
    GET_CHAT_MAX_WAIT_MS = 90_000

    @inject
    def __init__(
        self,
        session_dir: str,
        headless: bool | Literal["virtual"] = False,
        access_token: str = "",
        refresh_token: str = "",
    ):
        super().__init__()
        self.session_dir = os.path.join(session_dir, "kimi")
        self.storage_state_path = os.path.join(self.session_dir, "kimi_state.json")
        self.tokens_path = os.path.join(self.session_dir, "kimi_tokens.json")
        self.headless = headless
        self.access_token = access_token
        self.refresh_token = refresh_token
        os.makedirs(self.session_dir, exist_ok=True)

    async def login(self, content: str) -> None:
        """Imposta i token Kimi in localStorage e salva lo stato della sessione."""
        os.makedirs(self.session_dir, exist_ok=True)
        constraints = Screen(max_width=1920, max_height=1080)
        access_token, refresh_token = self._resolve_auth_tokens_from_login_content(content)
        self._write_json_file(
            self.tokens_path,
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
            },
        )
        async with AsyncCamoufox(headless=self.headless, humanize=True, screen=constraints) as browser:
            context = await browser.new_context()
            page = await context.new_page()
            self._attach_page_request_logger(page)

            await self._bootstrap_authenticated_page(page, self.BASE_URL, access_token, refresh_token)
            await page.wait_for_timeout(2_000)

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
                access_token, refresh_token = self._load_auth_tokens()
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path

                context = await browser.new_context(**context_options)
                page = await context.new_page()
                self._attach_page_request_logger(page)

                chat_id = await self._submit_prompt(
                    page,
                    message,
                    chat_id,
                    type_input,
                    access_token,
                    refresh_token,
                )

                await page.close()
                await context.close()

            return KimiResponse(chat_id=chat_id, message="")

        return await self._retry_async(_attempt, attempts=3)

    async def get_conversation(self, chat_id: str) -> KimiResponse:
        if not chat_id:
            raise ValueError("chat_id mancante")

        async def _attempt() -> KimiResponse:
            constraints = Screen(max_width=1920, max_height=1080)

            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constraints
            ) as browser:
                access_token, refresh_token = self._load_auth_tokens()
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path

                context = await browser.new_context(**context_options)
                page = await context.new_page()
                self._attach_page_request_logger(page)
                await self._bootstrap_authenticated_page(
                    page,
                    f"{self.BASE_URL}chat/{chat_id}",
                    access_token,
                    refresh_token,
                )
                content = await self._fetch_conversation_via_page(page, chat_id)

                await page.close()
                await context.close()

            return KimiResponse(chat_id=chat_id, message=content)

        return await self._retry_async(_attempt, attempts=3)

    async def ask_and_wait(
        self,
        message: str,
        chat_id: Optional[str] = None,
        type_input: bool = True,
    ) -> KimiResponse:
        async def _attempt() -> KimiResponse:
            constraints = Screen(max_width=1920, max_height=1080)

            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constraints
            ) as browser:
                access_token, refresh_token = self._load_auth_tokens()
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path

                context = await browser.new_context(**context_options)
                page = await context.new_page()
                self._attach_page_request_logger(page)

                try:
                    resolved_chat_id = await self._submit_prompt(
                        page,
                        message,
                        chat_id,
                        type_input,
                        access_token,
                        refresh_token,
                    )
                    await page.wait_for_timeout(self.POST_SUBMIT_WAIT_MS)
                    await self._open_chat_page(page, resolved_chat_id)
                    content = await self._fetch_conversation_via_page(
                        page,
                        resolved_chat_id,
                    )
                finally:
                    await page.close()
                    await context.close()

                return KimiResponse(chat_id=resolved_chat_id, message=content)

        return await self._retry_async(_attempt, attempts=3)

    def logout(self) -> None:
        self._clear_session_dir(self.session_dir)

    async def status(self) -> dict:
        constraints = Screen(max_width=1920, max_height=1080)
        user_name_text = ""
        try:
            async with AsyncCamoufox(
                headless=self.headless,
                humanize=True,
                screen=constraints
            ) as browser:
                access_token, refresh_token = self._load_auth_tokens()
                context_options = {}
                if os.path.exists(self.storage_state_path):
                    context_options["storage_state"] = self.storage_state_path
                context = await browser.new_context(**context_options)
                page = await context.new_page()
                self._attach_page_request_logger(page)
                await self._bootstrap_authenticated_page(
                    page,
                    self.BASE_URL,
                    access_token,
                    refresh_token,
                    wait_until="domcontentloaded",
                    timeout=20_000,
                )
                await page.wait_for_timeout(1_500)
                user_name = await page.query_selector(".user-name")
                if user_name is not None:
                    user_name_text = (await user_name.inner_text() or "").strip()
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
                "detail": f"Kimi status check failed: {exc}",
            }

        is_logged_in = self._is_logged_in_from_user_name_text(user_name_text)
        if not user_name_text:
            detail = "Kimi user-name element not found"
        elif not is_logged_in:
            detail = "Kimi login prompt detected"
        else:
            detail = None

        return {
            "provider": "kimi",
            "is_available": True,
            "is_logged_in": is_logged_in,
            "detail": detail,
        }

    @staticmethod
    def _is_logged_in_from_user_name_text(user_name_text: str) -> bool:
        normalized_text = (user_name_text or "").strip()
        return normalized_text != "" and normalized_text != "Log In"

    def _load_auth_tokens(self) -> tuple[str, str]:
        access_token = (self.access_token or "").strip()
        refresh_token = (self.refresh_token or "").strip()
        if access_token or refresh_token:
            return self._validate_auth_tokens(
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                }
            )

        if os.path.exists(self.tokens_path):
            return self._validate_auth_tokens(self._read_json_file(self.tokens_path))

        raise ValueError("KIMI_ACCESS_TOKEN o KIMI_REFRESH_TOKEN mancante o vuoto")

    def _resolve_auth_tokens_from_login_content(self, content: str) -> tuple[str, str]:
        parsed = AuthPayloadParser.parse(content)
        if not isinstance(parsed.raw_json_value, dict):
            raise ValueError("Kimi login payload deve essere un JSON con access_token e refresh_token")
        return self._validate_auth_tokens(parsed.raw_json_value)

    @staticmethod
    def _validate_auth_tokens(payload: dict[str, Any]) -> tuple[str, str]:
        access_token = str(payload.get("access_token", "")).strip()
        refresh_token = str(payload.get("refresh_token", "")).strip()
        if not access_token or not refresh_token:
            raise ValueError("KIMI_ACCESS_TOKEN e KIMI_REFRESH_TOKEN devono essere entrambi valorizzati")
        return access_token, refresh_token

    async def _bootstrap_authenticated_page(
        self,
        page,
        url: str,
        access_token: str,
        refresh_token: str,
        wait_until: str = "load",
        timeout: int = 30_000,
    ) -> None:  # noqa: ANN001
        await self._goto(page, url, wait_until=wait_until, timeout=timeout)
        await self._set_auth_tokens(page, access_token, refresh_token)
        await self._goto(page, url, wait_until=wait_until, timeout=timeout)

    async def _set_auth_tokens(self, page, access_token: str, refresh_token: str) -> None:  # noqa: ANN001
        await page.evaluate(
            """([accessToken, refreshToken]) => {
                window.localStorage.setItem('access_token', accessToken);
                window.localStorage.setItem('refresh_token', refreshToken);
            }""",
            [access_token, refresh_token],
        )

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

    async def _submit_prompt(
        self,
        page,
        message: str,
        chat_id: Optional[str],
        type_input: bool,
        access_token: str,
        refresh_token: str,
    ) -> str:
        url = f"{self.BASE_URL}chat/{chat_id}" if chat_id else self.BASE_URL
        await self._bootstrap_authenticated_page(page, url, access_token, refresh_token)
        await page.wait_for_timeout(5_000)
        await self._dismiss_later_dialog_if_present(page)
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
        resolved_chat_id = self._extract_chat_id_from_url(page.url or "")
        if not resolved_chat_id:
            raise ValueError("Chat ID Kimi non trovato nella URL dopo l'invio del messaggio")
        return resolved_chat_id

    async def _dismiss_later_dialog_if_present(self, page) -> None:  # noqa: ANN001
        buttons = await page.query_selector_all(".common-dialog-button")
        for button in buttons:
            text = " ".join(((await button.inner_text()) or "").lower().split())
            if "later" not in text:
                continue

            await button.click()
            await page.wait_for_timeout(500)
            return

    async def _open_chat_page(self, page, chat_id: str) -> None:  # noqa: ANN001
        await self._goto(page, f"{self.BASE_URL}chat/{chat_id}", wait_until="domcontentloaded", timeout=20_000)
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=20_000)
        except Exception:
            pass

    async def _fetch_conversation_via_page(
        self,
        page,
        chat_id: str,
    ) -> str:  # noqa: ANN001
        if not chat_id:
            raise ValueError("chat_id mancante")

        waited_ms = 0

        while waited_ms < self.GET_CHAT_MAX_WAIT_MS:
            try:
                async with page.expect_response(
                    lambda response: self._is_matching_get_chat_response(response.url),
                    timeout=self.GET_CHAT_WAIT_TIMEOUT_MS,
                ) as response_info:
                    await page.wait_for_timeout(self.GET_CHAT_WAIT_TIMEOUT_MS)
                response = await response_info.value
            except Exception:
                waited_ms += self.GET_CHAT_WAIT_TIMEOUT_MS
                if waited_ms >= self.GET_CHAT_MAX_WAIT_MS:
                    break
                await page.reload(wait_until="domcontentloaded", timeout=20_000)
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=20_000)
                except Exception:
                    pass
                continue

            waited_ms += self.GET_CHAT_WAIT_TIMEOUT_MS
            payload = await response.json()
            message = self._extract_message_from_get_chat_payload(payload, chat_id)
            if message is not None:
                return message

            if waited_ms >= self.GET_CHAT_MAX_WAIT_MS:
                break
            await page.reload(wait_until="domcontentloaded", timeout=20_000)
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=20_000)
            except Exception:
                pass

        raise TimeoutError("Risposta conversazione Kimi ancora in caricamento dopo 90 secondi")

    @classmethod
    def _extract_message_from_get_chat_payload(cls, payload: dict[str, Any], chat_id: str) -> Optional[str]:
        chat = payload.get("chat") if isinstance(payload, dict) else None
        if not isinstance(chat, dict):
            return None

        payload_chat_id = str(chat.get("id", "")).strip()
        if payload_chat_id != chat_id:
            return None

        message_content = chat.get("messageContent")
        if message_content is None:
            return ""
        return str(message_content)

    @classmethod
    def _is_matching_get_chat_response(cls, response_url: str) -> bool:
        normalized_response_url = response_url.split("?", 1)[0].rstrip("/")
        return normalized_response_url == cls.GET_CHAT_URL

    @staticmethod
    def _clean_message_html(content: str) -> str:
        if not content:
            return ""
        stripped = strip_tags(content, minify=True, remove_blank_lines=True)
        return " ".join(stripped.split())
