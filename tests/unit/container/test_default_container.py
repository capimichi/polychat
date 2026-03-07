import os

from polychat.client.chat_gpt_client import ChatGptClient
from polychat.client.deepseek_client import DeepseekClient
from polychat.client.gemini_client import GeminiClient
from polychat.client.qwen_client import QwenClient
from polychat.container.default_container import DefaultContainer


def test_init_environment_variables_reads_chatgpt_env(monkeypatch):
    monkeypatch.setenv("CHATGPT_SESSION_COOKIE", "cookie-123")
    monkeypatch.setenv("CHATGPT_WORKSPACE_NAME", "  Team Workspace  ")
    monkeypatch.setenv("QWEN_SESSION_COOKIE", "qwen-cookie")
    monkeypatch.setenv("GEMINI_COOKIE_1PSID", "gemini-cookie-1")
    monkeypatch.setenv("GEMINI_COOKIE_1PSIDTS", "gemini-cookie-2")
    monkeypatch.setenv("DEEPSEEK_USER_TOKEN_JSON", "{\"token\":\"abc\"}")

    container = DefaultContainer.__new__(DefaultContainer)
    container._init_environment_variables()

    assert container.chatgpt_session_cookie == "cookie-123"
    assert container.chatgpt_workspace_name == "Team Workspace"
    assert container.qwen_session_cookie == "qwen-cookie"
    assert container.gemini_cookie_1psid == "gemini-cookie-1"
    assert container.gemini_cookie_1psidts == "gemini-cookie-2"
    assert container.deepseek_user_token_json == "{\"token\":\"abc\"}"


def test_default_container_passes_chatgpt_env_to_client(monkeypatch):
    DefaultContainer.instance = None

    monkeypatch.setenv("CHATGPT_SESSION_COOKIE", "cookie-from-env")
    monkeypatch.setenv("CHATGPT_WORKSPACE_NAME", "My Workspace")
    monkeypatch.setenv("QWEN_SESSION_COOKIE", "qwen-from-env")
    monkeypatch.setenv("GEMINI_COOKIE_1PSID", "g1")
    monkeypatch.setenv("GEMINI_COOKIE_1PSIDTS", "g2")
    monkeypatch.setenv("DEEPSEEK_USER_TOKEN_JSON", "{\"token\":\"xyz\"}")

    container = DefaultContainer()
    client = container.get(ChatGptClient)
    qwen_client = container.get(QwenClient)
    gemini_client = container.get(GeminiClient)
    deepseek_client = container.get(DeepseekClient)

    assert client.session_cookie == "cookie-from-env"
    assert client.workspace_name == "My Workspace"
    assert qwen_client.session_cookie == "qwen-from-env"
    assert gemini_client.cookie_1psid == "g1"
    assert gemini_client.cookie_1psidts == "g2"
    assert deepseek_client.user_token_json == "{\"token\":\"xyz\"}"

    DefaultContainer.instance = None

    app_log_path = os.path.join("var", "log", "app.log")
    if os.path.exists(app_log_path):
        os.remove(app_log_path)
