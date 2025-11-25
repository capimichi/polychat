import asyncio

import click

from polychat.container.default_container import DefaultContainer
from polychat.service.kimi_service import KimiService


@click.command(
    name="login:kimi"
)
def login_kimi_command():
    """
    Login to Kimi by opening a browser and waiting 60 seconds for manual login.
    The session will be saved for future requests.
    """
    default_container: DefaultContainer = DefaultContainer.getInstance()
    kimi_service: KimiService = default_container.get(KimiService)

    click.echo("Opening browser for Kimi login...")
    click.echo("Please login manually. You have 60 seconds.")

    try:
        asyncio.run(kimi_service.login())
        click.echo("Login successful! Session saved.")
    except Exception as e:
        click.echo(f"Login failed: {str(e)}", err=True)
