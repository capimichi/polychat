import shutil
import subprocess


class AbstractClient:
    """Base client condiviso per incollare messaggi tramite clipboard nel browser."""

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
