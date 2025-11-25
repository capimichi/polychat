import click
from polychat.command.login_perplexity_command import login_perplexity_command
from polychat.command.login_chatgpt_command import login_chatgpt_command
from polychat.command.login_kimi_command import login_kimi_command


@click.group()
def cli():
    pass

cli.add_command(login_perplexity_command)
cli.add_command(login_chatgpt_command)
cli.add_command(login_kimi_command)

if __name__ == '__main__':
    cli()
