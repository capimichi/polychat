import os
import asyncio
from camoufox.async_api import AsyncCamoufox
from typing import Any, Literal, Optional
from injector import inject
from browserforge.fingerprints import Screen

from polychat.client.abstract_client import AbstractClient
from polychat.model.client.perplexity_response import PerplexityResponse


class PerplexityClient(AbstractClient):
    SESSION_URL_MARKER = "api/auth/session"
    SESSION_RESPONSE_TIMEOUT_MS = 5_000

    @inject
    def __init__(
        self,
        session_dir: str,
        headless: bool | Literal["virtual"] = False,
        session_cookie: str = "",
    ):
        super().__init__()
        self.session_dir = os.path.join(session_dir, "perplexity")
        self.storage_state_path = os.path.join(self.session_dir, "perplexity_state.json")
        self.cookie_path = os.path.join(self.session_dir, "perplexity_cookie.txt")
        self.headless = headless
        self.session_cookie = session_cookie
        self.base_url = "https://www.perplexity.ai/"
        os.makedirs(self.session_dir, exist_ok=True)

    async def login(self, session_cookie: str) -> None:
        """Salva il cookie di sessione fornito manualmente."""
        cookie_value = (session_cookie or "").strip()
        if not cookie_value:
            raise ValueError("Cookie di sessione mancante")

        os.makedirs(self.session_dir, exist_ok=True)
        with open(self.cookie_path, "w", encoding="utf-8") as f:
            f.write(cookie_value)

    async def ask(self, message: str, chat_id: Optional[str] = None, type_input: bool = True) -> PerplexityResponse:
        """
        Ask a question to Perplexity AI and wait for the complete response.

        Args:
            message: The question/message to ask
            chat_id: Optional chat id to continue an existing conversation

        Returns:
            The complete response content from Perplexity
        """
        constraints = Screen(max_width=1920, max_height=1080)
        session_cookie = self._load_session_cookie()

        async def _attempt() -> PerplexityResponse:
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
                        "domain": ".perplexity.ai",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "None",
                    }
                ])
                page = await context.new_page()
                self._attach_page_request_logger(page)

                if chat_id:
                    url = f"https://www.perplexity.ai/search/{chat_id}"
                else:
                    url = "https://www.perplexity.ai/"

                await self._goto(page, url)

                if type_input:
                    await self._type_message(page, "#ask-input", message)
                else:
                    await self._paste_message(page, "#ask-input", message)

                await page.wait_for_timeout(1000)
                await page.click("button.interactable.rounded-full.bg-button-bg")
                await page.wait_for_timeout(3_000)
                current_slug = self._extract_slug_from_url(page.url or "")

                if not current_slug:
                    raise Exception("Slug Perplexity non trovato dopo invio messaggio")

                response_content = PerplexityResponse(thread_url_slug=current_slug)

                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception:
                    pass

                await page.close()
                await context.close()

                return response_content

        return await _attempt()

    def logout(self) -> None:
        self._clear_session_dir(self.session_dir)

    async def status(self) -> dict:
        constraints = Screen(max_width=1920, max_height=1080)
        session_cookie = self._load_session_cookie()
        session_payload = None
        session_response_seen = False
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
                await context.add_cookies([
                    {
                        "name": "__Secure-next-auth.session-token",
                        "value": session_cookie,
                        "domain": ".perplexity.ai",
                        "path": "/",
                        "httpOnly": True,
                        "secure": True,
                        "sameSite": "None",
                    }
                ])
                page = await context.new_page()
                self._attach_page_request_logger(page)
                session_detection_task = asyncio.create_task(
                    self._detect_login_state_from_session_response(page)
                )
                await self._goto(page, self.base_url, wait_until="domcontentloaded", timeout=20_000)
                try:
                    await page.wait_for_timeout(1_500)
                except Exception:
                    pass
                session_response_seen, session_payload = await session_detection_task

                try:
                    await context.storage_state(path=self.storage_state_path)
                except Exception:
                    pass
                await page.close()
                await context.close()
        except Exception as exc:
            return {
                "provider": "perplexity",
                "is_available": False,
                "is_logged_in": False,
                "detail": f"Status check failed: {exc}",
            }

        is_logged_in = self._is_non_empty_session_payload(session_payload)
        if is_logged_in:
            detail = None
        elif not session_response_seen:
            detail = "Session response api/auth/session not detected within 5 seconds"
        else:
            detail = "Session response api/auth/session was empty or missing data"

        return {
            "provider": "perplexity",
            "is_available": True,
            "is_logged_in": is_logged_in,
            "detail": detail,
        }

    async def get_conversation(self, chat_id: str) -> PerplexityResponse:
        """Recupera il dettaglio del thread Perplexity a partire dallo slug."""
        if not chat_id:
            raise ValueError("chat_id mancante")

        session_cookie = self._load_session_cookie()
        constraints = Screen(max_width=1920, max_height=1080)

        async with AsyncCamoufox(
            headless=self.headless,
            humanize=True,
            screen=constraints,
        ) as browser:
            context_options = {}
            if os.path.exists(self.storage_state_path):
                context_options["storage_state"] = self.storage_state_path

            context = await browser.new_context(**context_options)
            await context.add_cookies([
                {
                    "name": "__Secure-next-auth.session-token",
                    "value": session_cookie,
                    "domain": ".perplexity.ai",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "None",
                }
            ])
            page = await context.new_page()
            self._attach_page_request_logger(page)
            response_content = await self._wait_for_thread_response(page, chat_id, post_navigation_wait_ms=10_000)

            try:
                await context.storage_state(path=self.storage_state_path)
            except Exception:
                pass

            await page.close()
            await context.close()

        return response_content

    async def _wait_for_thread_response(self, page, slug: str, post_navigation_wait_ms: int = 0) -> PerplexityResponse:
        """
        Attende la response AJAX /rest/thread/{slug} e valida l'ultima entry.
        """
        response_content = None
        response_received = asyncio.Event()
        thread_path = f"/rest/thread/{slug}"

        async def handle_response(response):  # noqa: ANN001
            nonlocal response_content
            if thread_path in response.url:
                try:
                    payload = await response.json()
                    entries = payload.get("entries") if isinstance(payload, dict) else None
                    if not entries:
                        return
                    last_entry = entries[-1]
                    if not isinstance(last_entry, dict):
                        return
                    response_content = last_entry
                    response_received.set()
                except Exception as e:
                    print(f"Error reading response: {e}")

        page.on("response", handle_response)
        await self._goto(page, f"https://www.perplexity.ai/search/{slug}")
        if post_navigation_wait_ms > 0:
            await page.wait_for_timeout(post_navigation_wait_ms)

        try:
            await asyncio.wait_for(response_received.wait(), timeout=120)
        except asyncio.TimeoutError:
            raise Exception("Timeout waiting for Perplexity thread response")

        return PerplexityResponse.model_validate(response_content)

    def _load_session_cookie(self) -> str:
        cookie_value = (self.session_cookie or "").strip()
        if cookie_value:
            return cookie_value

        if os.path.exists(self.cookie_path):
            with open(self.cookie_path, "r", encoding="utf-8") as f:
                cookie_value = f.read().strip()
            if cookie_value:
                return cookie_value

        raise ValueError("PERPLEXITY_SESSION_COOKIE mancante o vuoto")

    @classmethod
    def _extract_slug_from_url(cls, current_url: str) -> str:
        if not current_url:
            return ""
        return cls._extract_slug_from_href(current_url)

    @staticmethod
    def _extract_slug_from_href(href: str) -> str:
        if not href:
            return ""

        prefix = "/search/"
        if "://www.perplexity.ai/search/" in href:
            prefix = "://www.perplexity.ai/search/"
        elif "://perplexity.ai/search/" in href:
            prefix = "://perplexity.ai/search/"

        idx = href.find(prefix)
        if idx == -1:
            return ""

        slug = href[idx + len(prefix):]
        slug = slug.split("?", 1)[0].split("#", 1)[0]
        return slug.rstrip("/")

    async def _detect_login_state_from_session_response(self, page) -> tuple[bool, Optional[Any]]:  # noqa: ANN001
        response_received = asyncio.Event()
        session_payload = None
        session_response_seen = False

        async def handle_response(response):  # noqa: ANN001
            nonlocal session_payload, session_response_seen
            if self.SESSION_URL_MARKER not in getattr(response, "url", ""):
                return

            session_response_seen = True
            try:
                session_payload = await response.json()
            except Exception:
                session_payload = None
            finally:
                response_received.set()

        page.on("response", handle_response)

        try:
            await asyncio.wait_for(
                response_received.wait(),
                timeout=self.SESSION_RESPONSE_TIMEOUT_MS / 1000,
            )
        except asyncio.TimeoutError:
            return False, None

        return session_response_seen, session_payload

    @staticmethod
    def _is_non_empty_session_payload(payload: Optional[Any]) -> bool:
        return isinstance(payload, dict) and len(payload) > 0
