import click
import asyncio
from perplexityapi.container.default_container import DefaultContainer
from perplexityapi.service.chat_service import ChatService


@click.command(
    name='perplexity:login'
)
def perplexity_login_command():
    """
    Login to Perplexity AI by opening a browser and waiting 45 seconds for manual login.
    The session will be saved for future requests.
    """
    default_container: DefaultContainer = DefaultContainer.getInstance()
    chat_service: ChatService = default_container.get(ChatService)

    click.echo('Opening browser for Perplexity login...')
    click.echo('Please login manually. You have 45 seconds.')

    try:
        # Run the async login method
        asyncio.run(chat_service.login())
        click.echo('Login successful! Session saved.')
    except Exception as e:
        click.echo(f'Login failed: {str(e)}', err=True)