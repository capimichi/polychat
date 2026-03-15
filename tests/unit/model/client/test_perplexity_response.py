from polychat.model.client.perplexity_response import PerplexityResponse


def test_answer_combines_all_markdown_blocks_in_order():
    response = PerplexityResponse(
        blocks=[
            {
                "intended_usage": "plan",
                "plan_block": {"progress": "DONE"},
            },
            {
                "intended_usage": "ask_text_0_markdown",
                "markdown_block": {"answer": "Primo paragrafo."},
            },
            {
                "intended_usage": "ask_text_1_markdown",
                "markdown_block": {"answer": "## Seconda sezione"},
            },
            {
                "intended_usage": "ask_text_2_markdown",
                "markdown_block": {"answer": "Terza riga"},
            },
        ]
    )

    assert response.answer == "Primo paragrafo.\n\n## Seconda sezione\n\nTerza riga"


def test_answer_returns_none_when_no_text_blocks_are_present():
    response = PerplexityResponse(
        blocks=[
            {
                "intended_usage": "plan",
                "plan_block": {"progress": "DONE"},
            }
        ]
    )

    assert response.answer is None


def test_answer_ignores_empty_text_blocks():
    response = PerplexityResponse(
        blocks=[
            {
                "intended_usage": "ask_text_0_markdown",
                "markdown_block": {"answer": "  "},
            },
            {
                "intended_usage": "ask_text_1_markdown",
                "markdown_block": {"answer": "Contenuto finale"},
            },
        ]
    )

    assert response.answer == "Contenuto finale"
