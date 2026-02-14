import asyncio

import click

from polychat.container.default_container import DefaultContainer
from polychat.service.chat_gpt_service import ChatGptService


@click.command(
    name='login:chatgpt'
)
def login_chatgpt_command():
    """
    Login to ChatGPT by saving a provided session cookie.
    """
    default_container: DefaultContainer = DefaultContainer.getInstance()
    chatgpt_service: ChatGptService = default_container.get(ChatGptService)

    click.echo('Inserisci il cookie __Secure-next-auth.session-token:')
    session_cookie = click.prompt('Cookie', hide_input=False)

    try:
        asyncio.run(chatgpt_service.login(session_cookie))
        click.echo('Cookie salvato correttamente.')
    except Exception as e:
        click.echo(f'Login failed: {str(e)}', err=True)
