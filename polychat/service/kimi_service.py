from injector import inject

from polychat.client.kimi_client import KimiClient
from polychat.model import ChatResponse


class KimiService:

    @inject
    def __init__(self, kimi_client: KimiClient):
        self.kimi_client = kimi_client

    async def login(self) -> None:
        """Esegue il login a Kimi tramite il client."""
        await self.kimi_client.login()

    async def ask(self, message: str) -> ChatResponse:
        """Invia una domanda a Kimi e restituisce la risposta come ChatResponse."""
        try:
            return await self.kimi_client.ask(message)
        except Exception as exc:
            raise Exception(f"Error asking Kimi: {exc}")
