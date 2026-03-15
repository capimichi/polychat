import asyncio

import click

from polychat.container.default_container import DefaultContainer
from polychat.service.kimi_service import KimiService


@click.command(
    name="login:kimi"
)
def login_kimi_command():
    """
    Login to Kimi using KIMI_AUTH_TOKEN and save the browser session.
    """
    default_container: DefaultContainer = DefaultContainer.getInstance()
    kimi_service: KimiService = default_container.get(KimiService)

    click.echo("Saving Kimi session from KIMI_AUTH_TOKEN...")

    try:
        asyncio.run(kimi_service.login())
        click.echo("Login successful! Session saved.")
    except Exception as e:
        click.echo(f"Login failed: {str(e)}", err=True)
