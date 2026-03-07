from polychat.client.gemini_client import GeminiClient


def test_extract_chat_id_from_url():
    chat_id = GeminiClient._extract_chat_id_from_url("https://gemini.google.com/app/e0ccb7f20d4d6c53")
    assert chat_id == "e0ccb7f20d4d6c53"


def test_extract_response_container_id():
    payload = '[["wrb.fr","hNvQHb","[[[[\"c_e0ccb7f20d4d6c53\",\"r_a1a70693a88a0106\"]'  # noqa: E501
    extracted = GeminiClient._extract_response_container_id(payload, "e0ccb7f20d4d6c53")
    assert extracted == "r_a1a70693a88a0106"
