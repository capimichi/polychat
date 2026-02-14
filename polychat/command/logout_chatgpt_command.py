import click

from polychat.container.default_container import DefaultContainer
from polychat.service.chat_gpt_service import ChatGptService


@click.command(
    name='logout:chatgpt'
)
def logout_chatgpt_command():
    """Logout da ChatGPT rimuovendo la sessione salvata."""
    default_container: DefaultContainer = DefaultContainer.getInstance()
    chatgpt_service: ChatGptService = default_container.get(ChatGptService)

    try:
        chatgpt_service.logout()
        click.echo('Logout completato.')
    except Exception as e:
        click.echo(f'Logout failed: {str(e)}', err=True)
