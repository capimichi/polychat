from click.testing import CliRunner

from polychat.cli import cli


def test_cli_help_does_not_show_login_chatgpt_command():
    runner = CliRunner()

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "login:chatgpt" not in result.output
    assert "logout:chatgpt" in result.output
