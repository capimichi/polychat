from polychat.client.qwen_client import QwenClient
from polychat.model.client.qwen_response import QwenResponse


def test_extract_chat_id_from_url():
    chat_id = QwenClient._extract_chat_id_from_url("https://chat.qwen.ai/c/82f75ff7-3bc5-4589-a40d-d7fa5e075f08")
    assert chat_id == "82f75ff7-3bc5-4589-a40d-d7fa5e075f08"


def test_qwen_response_answer_and_done():
    payload = {
        "success": True,
        "request_id": "req-1",
        "data": {
            "id": "chat-1",
            "title": "Titolo",
            "chat": {
                "history": {
                    "currentId": "assistant-1",
                    "messages": {
                        "assistant-1": {
                            "id": "assistant-1",
                            "role": "assistant",
                            "done": True,
                            "content_list": [
                                {"phase": "thinking_summary", "status": "finished", "content": ""},
                                {"phase": "answer", "status": "finished", "content": "Risposta finale"},
                            ],
                        }
                    },
                },
                "models": ["qwen3.5-plus"],
            },
            "created_at": 1772606744,
            "updated_at": 1772606748,
        },
    }

    response = QwenResponse.model_validate(payload)

    assert response.chat_id == "chat-1"
    assert response.answer == "Risposta finale"
    assert response.done is True
    assert response.model_name == "qwen3.5-plus"
