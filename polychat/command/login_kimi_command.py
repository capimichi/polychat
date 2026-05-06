import asyncio
import json

import click

from polychat.container.default_container import DefaultContainer
from polychat.service.kimi_service import KimiService


@click.command(
    name="login:kimi"
)
def login_kimi_command():
    """
    Login to Kimi using KIMI_ACCESS_TOKEN and KIMI_REFRESH_TOKEN.
    """
    default_container: DefaultContainer = DefaultContainer.getInstance()
    kimi_service: KimiService = default_container.get(KimiService)
    payload = json.dumps(
        {
            "access_token": default_container.get_var("kimi_access_token"),
            "refresh_token": default_container.get_var("kimi_refresh_token"),
        },
        ensure_ascii=True,
    )

    click.echo("Saving Kimi session from KIMI_ACCESS_TOKEN and KIMI_REFRESH_TOKEN...")

    try:
        asyncio.run(kimi_service.login(payload))
        click.echo("Login successful! Session saved.")
    except Exception as e:
        click.echo(f"Login failed: {str(e)}", err=True)
