import asyncio
from datetime import datetime
import logging
import os
import shutil
import subprocess
from typing import Awaitable, Callable, Optional, TypeVar

import requests


T = TypeVar("T")


class AbstractClient:
    """Base client condiviso per incollare messaggi tramite clipboard nel browser."""

    def __init__(self) -> None:
        self._http_logger = logging.getLogger("polychat.http")

    def _log_http_request(self, method: str, url: str) -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")
        self._http_logger.info("%s %s %s", timestamp, method.upper(), url)

    def _attach_page_request_logger(self, page) -> None:  # noqa: ANN001
        if not hasattr(page, "on"):
            return

        def _handle_request(request):  # noqa: ANN001
            method = getattr(request, "method", "GET")
            url = getattr(request, "url", "")
            self._log_http_request(str(method), str(url))

        page.on("request", _handle_request)

    async def _goto(self, page, url: str, **kwargs):  # noqa: ANN001
        self._log_http_request("GET", url)
        return await page.goto(url, **kwargs)

    def _requests_request(self, session, method: str, url: str, **kwargs):  # noqa: ANN001
        self._log_http_request(method, url)
        return session.request(method=method.upper(), url=url, **kwargs)

    async def _paste_message(self, page, selector: str, content: str) -> None:
        """Copia il contenuto in clipboard e lo incolla nel campo indicato."""
        pbcopy_path = shutil.which("pbcopy")
        if not pbcopy_path:
            raise RuntimeError(
                "Utility 'pbcopy' non trovata: impossibile copiare il contenuto nella clipboard."
            )

        safe_content = self._sanitize_message(content)
        subprocess.run([pbcopy_path], input=safe_content.encode("utf-8"), check=True)

        await page.wait_for_selector(selector)
        await page.click(selector)
        await page.keyboard.press("ControlOrMeta+V")

    async def _type_message(self, page, selector: str, content: str, chunk_size: int = 500) -> None:
        """Digita il contenuto nel campo indicato, suddividendolo in chunk."""
        safe_content = self._sanitize_message(content)
        await page.wait_for_selector(selector)
        await page.click(selector)

        chunks = [safe_content[i:i + chunk_size] for i in range(0, len(safe_content), chunk_size)]
        for chunk in chunks:
            await page.type(selector, chunk)

    @staticmethod
    def _sanitize_message(content: str) -> str:
        """Rimuove i newline sostituendoli con spazi per evitare invii indesiderati."""
        return content.replace("\n", " ")

    async def _retry_async(
        self,
        operation: Callable[[], Awaitable[T]],
        attempts: int = 3,
        delay_seconds: float = 1.5,
    ) -> T:
        """
        Esegue un'operazione asincrona con politiche di retry.
        Riprova fino a `attempts` volte con backoff lineare se solleva eccezioni.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                return await operation()
            except Exception as exc:
                last_exc = exc
                if attempt == attempts:
                    raise
                await asyncio.sleep(delay_seconds * attempt)
        raise last_exc if last_exc else Exception("Operazione fallita senza eccezione.")

    @staticmethod
    def _clear_session_dir(path: str) -> None:
        if os.path.exists(path):
            shutil.rmtree(path)

    def _fetch_page_content(self, url: str, headers: Optional[dict] = None, timeout: int = 15) -> str:
        with requests.Session() as session:
            response = self._requests_request(
                session,
                "GET",
                url,
                headers=headers or {},
                timeout=timeout,
            )
            response.raise_for_status()
            return response.text or ""
