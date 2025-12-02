from polychat.model.perplexity_response import PerplexityResponse
from tests.fakes.perplexity_response_factory import make_perplexity_response


class FakePerplexityClient:
    """Lightweight fake that mimics the PerplexityClient API."""

    def __init__(self, response: PerplexityResponse | None = None):
        self.response = response or make_perplexity_response()
        self.calls = []
        self.logged_in = False

    async def login(self):
        self.logged_in = True

    async def ask(self, message: str, chat_slug: str | None = None, type_input: bool = True) -> PerplexityResponse:
        self.calls.append((message, chat_slug, type_input))
        return self.response
