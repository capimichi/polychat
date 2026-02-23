import click
import asyncio
from polychat.container.default_container import DefaultContainer
from polychat.service.perplexity_service import PerplexityService


@click.command(
    name='login:perplexity'
)
def login_perplexity_command():
    """
    Login to Perplexity salvando il cookie __Secure-next-auth.session-token.
    """
    default_container: DefaultContainer = DefaultContainer.getInstance()
    perplexity_service: PerplexityService = default_container.get(PerplexityService)

    click.echo('Inserisci il cookie __Secure-next-auth.session-token:')
    session_cookie = click.prompt('Cookie', hide_input=False)

    try:
        asyncio.run(perplexity_service.login(session_cookie))
        click.echo('Cookie salvato correttamente.')
    except Exception as e:
        click.echo(f'Login failed: {str(e)}', err=True)
