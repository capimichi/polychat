import click
from perplexityapi.command.perplexity_login_command import perplexity_login_command


@click.group()
def cli():
    pass

cli.add_command(perplexity_login_command)

if __name__ == '__main__':
    cli()