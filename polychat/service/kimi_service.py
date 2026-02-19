from injector import inject

from polychat.client.kimi_client import KimiClient
from polychat.mapper.client.kimi_chat_mapper import KimiChatMapper
from polychat.model import Chat


class KimiService:

    @inject
    def __init__(self, kimi_client: KimiClient, kimi_chat_mapper: KimiChatMapper):
        self.kimi_client = kimi_client
        self.kimi_chat_mapper = kimi_chat_mapper

    async def login(self) -> None:
        """Esegue il login a Kimi tramite il client."""
        await self.kimi_client.login()

    async def ask(self, message: str, type_input: bool = True) -> Chat:
        """Invia una domanda a Kimi e restituisce la risposta come Chat."""
        try:
            response = await self.kimi_client.ask(message, type_input=type_input)
            return self.kimi_chat_mapper.create_from(response)
        except Exception as exc:
            raise Exception(f"Error asking Kimi: {exc}")
