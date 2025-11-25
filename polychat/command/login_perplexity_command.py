import click
import asyncio
from polychat.container.default_container import DefaultContainer
from polychat.service.perplexity_service import PerplexityService


@click.command(
    name='login:perplexity'
)
def login_perplexity_command():
    """
    Login to Perplexity AI by opening a browser and waiting 45 seconds for manual login.
    The session will be saved for future requests.
    """
    default_container: DefaultContainer = DefaultContainer.getInstance()
    perplexity_service: PerplexityService = default_container.get(PerplexityService)

    click.echo('Opening browser for Perplexity login...')
    click.echo('Please login manually. You have 45 seconds.')

    try:
        # Run the async login method
        asyncio.run(perplexity_service.login())
        click.echo('Login successful! Session saved.')
    except Exception as e:
        click.echo(f'Login failed: {str(e)}', err=True)
