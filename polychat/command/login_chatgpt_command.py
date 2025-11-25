import asyncio

import click

from polychat.container.default_container import DefaultContainer
from polychat.service.chat_gpt_service import ChatGptService


@click.command(
    name='login:chatgpt'
)
def login_chatgpt_command():
    """
    Login to ChatGPT by opening a browser and waiting 45 seconds for manual login.
    The session will be saved for future requests.
    """
    default_container: DefaultContainer = DefaultContainer.getInstance()
    chatgpt_service: ChatGptService = default_container.get(ChatGptService)

    click.echo('Opening browser for ChatGPT login...')
    click.echo('Please login manually. You have 45 seconds.')

    try:
        asyncio.run(chatgpt_service.login())
        click.echo('Login successful! Session saved.')
    except Exception as e:
        click.echo(f'Login failed: {str(e)}', err=True)
