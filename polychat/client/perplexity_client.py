import os
import asyncio
from camoufox.async_api import AsyncCamoufox
from typing import Literal, Optional
from injector import inject
from browserforge.fingerprints import Screen

from polychat.client.abstract_client import AbstractClient
from polychat.model.client.perplexity_response import PerplexityResponse


class PerplexityClient(AbstractClient):

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

    async def ask(self, message: str, chat_slug: Optional[str] = None, type_input: bool = True) -> PerplexityResponse:
        """
        Ask a question to Perplexity AI and wait for the complete response.

        Args:
            message: The question/message to ask
            chat_slug: Optional chat slug to continue an existing conversation

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

                if chat_slug:
                    url = f"https://www.perplexity.ai/search/{chat_slug}"
                else:
                    url = "https://www.perplexity.ai/"

                await self._goto(page, url)

                if type_input:
                    await self._type_message(page, "#ask-input", message)
                else:
                    await self._paste_message(page, "#ask-input", message)

                await page.wait_for_timeout(1000)
                await page.click("button.interactable.rounded-full.bg-button-bg")
                await page.wait_for_timeout(1000)
                await self._goto(page, "https://www.perplexity.ai/library", wait_until="domcontentloaded")
                await page.wait_for_selector('a[href*="/search/"]', timeout=20_000)

                current_slug = ""
                search_links = await page.query_selector_all('a[href*="/search/"]')
                for link in search_links:
                    href = await link.get_attribute("href")
                    slug_from_href = self._extract_slug_from_href(href or "")
                    if slug_from_href:
                        current_slug = slug_from_href
                        break

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

    def status(self) -> dict:
        self._fetch_page_content(self.base_url)
        return {
            "provider": "perplexity",
            "is_available": True,
            "is_logged_in": None,
            "detail": "TODO: implement Perplexity login detection",
        }

    async def get_conversation(self, conversation_id: str) -> PerplexityResponse:
        """Recupera il dettaglio del thread Perplexity a partire dallo slug."""
        if not conversation_id:
            raise ValueError("conversation_id mancante")

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
            response_content = await self._wait_for_thread_response(page, conversation_id, post_navigation_wait_ms=10_000)

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
