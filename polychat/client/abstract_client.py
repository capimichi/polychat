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

        safe_content = content.replace("\n", " ")
        subprocess.run([pbcopy_path], input=safe_content.encode("utf-8"), check=True)

        await page.wait_for_selector(selector)
        await page.click(selector)
        await page.keyboard.press("ControlOrMeta+V")
