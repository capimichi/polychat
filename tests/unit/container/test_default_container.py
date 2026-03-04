import os

from polychat.client.chat_gpt_client import ChatGptClient
from polychat.client.qwen_client import QwenClient
from polychat.container.default_container import DefaultContainer


def test_init_environment_variables_reads_chatgpt_env(monkeypatch):
    monkeypatch.setenv("CHATGPT_SESSION_COOKIE", "cookie-123")
    monkeypatch.setenv("CHATGPT_WORKSPACE_NAME", "  Team Workspace  ")
    monkeypatch.setenv("QWEN_SESSION_COOKIE", "qwen-cookie")

    container = DefaultContainer.__new__(DefaultContainer)
    container._init_environment_variables()

    assert container.chatgpt_session_cookie == "cookie-123"
    assert container.chatgpt_workspace_name == "Team Workspace"
    assert container.qwen_session_cookie == "qwen-cookie"


def test_default_container_passes_chatgpt_env_to_client(monkeypatch):
    DefaultContainer.instance = None

    monkeypatch.setenv("CHATGPT_SESSION_COOKIE", "cookie-from-env")
    monkeypatch.setenv("CHATGPT_WORKSPACE_NAME", "My Workspace")
    monkeypatch.setenv("QWEN_SESSION_COOKIE", "qwen-from-env")

    container = DefaultContainer()
    client = container.get(ChatGptClient)
    qwen_client = container.get(QwenClient)

    assert client.session_cookie == "cookie-from-env"
    assert client.workspace_name == "My Workspace"
    assert qwen_client.session_cookie == "qwen-from-env"

    DefaultContainer.instance = None

    app_log_path = os.path.join("var", "log", "app.log")
    if os.path.exists(app_log_path):
        os.remove(app_log_path)
