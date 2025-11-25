from polychat.model.perplexity_response import PerplexityResponse


def make_perplexity_response(answer: str = "hello world") -> PerplexityResponse:
    """Build a minimal PerplexityResponse with a synthetic answer."""
    return PerplexityResponse(
        backend_uuid="backend-uuid",
        uuid="response-uuid",
        text=answer,
        blocks=[
            {
                "intended_usage": "ask_text",
                "markdown_block": {"answer": answer},
            }
        ],
    )
