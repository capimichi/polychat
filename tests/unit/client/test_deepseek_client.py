from pathlib import Path

from polychat.client.deepseek_client import DeepseekClient


def test_extract_chat_id_from_url():
    chat_id = DeepseekClient._extract_chat_id_from_url(
        "https://chat.deepseek.com/a/chat/s/40021dbb-89ca-46f0-b9f2-60da13551daa"
    )
    assert chat_id == "40021dbb-89ca-46f0-b9f2-60da13551daa"


def test_extract_assistant_message_prefers_finished_response_fragment():
    payload = {
        "data": {
            "biz_data": {
                "chat_messages": [
                    {
                        "role": "USER",
                        "status": "FINISHED",
                        "fragments": [{"type": "REQUEST", "content": "hello"}],
                    },
                    {
                        "role": "ASSISTANT",
                        "status": "FINISHED",
                        "fragments": [
                            {"type": "SEARCH", "content": None},
                            {"type": "RESPONSE", "content": "final answer"},
                        ],
                    },
                ]
            }
        }
    }

    message, done = DeepseekClient._extract_assistant_message(payload)

    assert message == "final answer"
    assert done is True


def test_load_user_token_json_reads_persisted_file(tmp_path):
    client = DeepseekClient(str(tmp_path), user_token_json="")
    Path(client.user_token_path).write_text('{"token":"abc"}', encoding="utf-8")

    assert client._load_user_token_json() == '{"token": "abc"}'


def test_resolve_user_token_json_from_json_payload(tmp_path):
    client = DeepseekClient(str(tmp_path), user_token_json="")

    token_json = client._resolve_user_token_json_from_login_content('{"token":"abc"}')

    assert token_json == '{"token": "abc"}'
