from polychat.model.perplexity_response import PerplexityResponse
from tests.fakes.perplexity_response_factory import make_perplexity_response


class FakePerplexityClient:
    """Lightweight fake that mimics the PerplexityClient API."""

    def __init__(
        self,
        response: PerplexityResponse | None = None,
        conversation_response: PerplexityResponse | None = None,
    ):
        self.response = response or make_perplexity_response(answer="")
        self.conversation_response = conversation_response or make_perplexity_response()
        self.calls = []
        self.logged_in = False
        self.conversation_calls = []

    async def login(self, session_cookie: str):
        self.logged_in = True

    async def ask(self, message: str, chat_id: str | None = None, type_input: bool = True) -> PerplexityResponse:
        self.calls.append((message, chat_id, type_input))
        return self.response

    async def ask_and_wait(self, message: str, chat_id: str | None = None, type_input: bool = True) -> PerplexityResponse:
        self.calls.append((message, chat_id, type_input, "complete"))
        return self.conversation_response

    async def get_conversation(self, chat_id: str) -> PerplexityResponse:
        self.conversation_calls.append(chat_id)
        return self.conversation_response
