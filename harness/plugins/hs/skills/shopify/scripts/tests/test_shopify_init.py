"""Tests for the Shopify CLI wrapper."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from shopify_init import ShopifyCliWrapper, build_parser, main


@pytest.fixture
def printed():
    """Collect printed lines for assertions."""
    lines = []

    def capture(*args, **kwargs):
        lines.append(" ".join(str(arg) for arg in args))

    return lines, capture


@pytest.fixture
def wrapper(printed):
    """Create wrapper with captured output."""
    _, capture = printed
    return ShopifyCliWrapper(print_func=capture)


def parse_args(argv):
    """Parse argv with the production parser."""
    return build_parser().parse_args(argv)


class TestCommandBuilding:
    """Command builders keep user values as separate list args."""

    def test_app_command_with_name_and_path(self, wrapper):
        command = wrapper.build_app_command("my-app", "/tmp/my app", interactive=False)

        assert command.args == ["shopify", "app", "init", "--name", "my-app", "--path", "/tmp/my app"]

    def test_extension_command_with_template_and_name(self, wrapper):
        command = wrapper.build_extension_command("function", "gift message", interactive=False)

        assert command.args == [
            "shopify",
            "app",
            "generate",
            "extension",
            "--template",
            "function",
            "--name",
            "gift message",
        ]

    def test_theme_command_with_name_and_path(self, wrapper):
        command = wrapper.build_theme_command("demo theme", "themes/demo", interactive=False)

        assert command.args == ["shopify", "theme", "init", "demo theme", "--path", "themes/demo"]

    def test_config_link_command(self, wrapper):
        command = wrapper.build_config_link_command()

        assert command.args == ["shopify", "app", "config", "link"]

    def test_config_use_command_with_name(self, wrapper):
        command = wrapper.build_config_use_command("production")

        assert command.args == ["shopify", "app", "config", "use", "production"]

    def test_malicious_values_remain_single_args(self, wrapper):
        malicious = '"; rm -rf /"'
        command = wrapper.build_app_command(malicious, malicious, interactive=False)

        assert command.args == ["shopify", "app", "init", "--name", malicious, "--path", malicious]
        assert command.args.count(malicious) == 2

    def test_interactive_prompt_supplies_missing_app_name(self, printed):
        _, capture = printed
        wrapper = ShopifyCliWrapper(input_func=lambda _: "prompted-app", print_func=capture)

        command = wrapper.build_app_command(None, None, interactive=True)

        assert command.args == ["shopify", "app", "init", "--name", "prompted-app"]


class TestExecution:
    """Execution is list-based and dry-run safe."""

    def test_dry_run_executes_no_subprocess(self, wrapper, printed):
        lines, _ = printed
        command = wrapper.build_config_link_command()

        with patch("shopify_init.shutil.which") as mock_which, patch("shopify_init.subprocess.run") as mock_run:
            result = wrapper.execute(command, dry_run=True)

        assert result == 0
        mock_which.assert_not_called()
        mock_run.assert_not_called()
        assert lines == ["Dry run only; no subprocess executed: shopify app config link"]

    def test_missing_cli_returns_nonzero(self, wrapper):
        with patch("shopify_init.shutil.which", return_value=None), patch("shopify_init.subprocess.run") as mock_run:
            result = wrapper.execute(wrapper.build_config_link_command(), dry_run=False)

        assert result == 127
        mock_run.assert_not_called()

    def test_version_check_failure_returns_nonzero(self, wrapper):
        version_result = Mock(returncode=1, stderr="bad install")

        with patch("shopify_init.shutil.which", return_value="/bin/shopify"), patch(
            "shopify_init.subprocess.run", return_value=version_result
        ) as mock_run:
            result = wrapper.execute(wrapper.build_config_link_command(), dry_run=False)

        assert result == 127
        mock_run.assert_called_once_with(
            ["/bin/shopify", "version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    def test_version_check_timeout_returns_nonzero(self, wrapper):
        with patch("shopify_init.shutil.which", return_value="/bin/shopify"), patch(
            "shopify_init.subprocess.run", side_effect=subprocess.TimeoutExpired(["/bin/shopify", "version"], 10)
        ) as mock_run:
            result = wrapper.execute(wrapper.build_config_link_command(), dry_run=False)

        assert result == 127
        mock_run.assert_called_once()

    def test_version_check_os_error_returns_nonzero(self, wrapper):
        with patch("shopify_init.shutil.which", return_value="/bin/shopify"), patch(
            "shopify_init.subprocess.run", side_effect=OSError("cannot execute")
        ) as mock_run:
            result = wrapper.execute(wrapper.build_config_link_command(), dry_run=False)

        assert result == 127
        mock_run.assert_called_once()

    def test_nonzero_shopify_exit_code_propagates(self, wrapper):
        version_result = Mock(returncode=0, stderr="")
        command_result = Mock(returncode=42)

        with patch("shopify_init.shutil.which", return_value="/bin/shopify"), patch(
            "shopify_init.subprocess.run", side_effect=[version_result, command_result]
        ) as mock_run:
            result = wrapper.execute(wrapper.build_config_use_command("production"), dry_run=False)

        assert result == 42
        assert mock_run.call_args_list[1].args[0] == ["/bin/shopify", "app", "config", "use", "production"]
        assert mock_run.call_args_list[1].kwargs == {"check": False}

    def test_execute_uses_list_args_for_malicious_values(self, wrapper):
        version_result = Mock(returncode=0, stderr="")
        command_result = Mock(returncode=0)
        command = wrapper.build_app_command('"; rm -rf /"', None, interactive=False)

        with patch("shopify_init.shutil.which", return_value="/bin/shopify"), patch(
            "shopify_init.subprocess.run", side_effect=[version_result, command_result]
        ) as mock_run:
            result = wrapper.execute(command, dry_run=False)

        assert result == 0
        assert mock_run.call_args_list[1].args[0] == ["/bin/shopify", "app", "init", "--name", '"; rm -rf /"']
        assert mock_run.call_args_list[1].kwargs == {"check": False}


class TestMain:
    """Main dispatches subcommands and returns exit codes."""

    @pytest.mark.parametrize(
        ("argv", "expected"),
        [
            (["--dry-run", "app", "--name", "demo"], ["shopify", "app", "init", "--name", "demo"]),
            (
                ["--dry-run", "extension", "--template", "function", "--name", "gift"],
                ["shopify", "app", "generate", "extension", "--template", "function", "--name", "gift"],
            ),
            (["--dry-run", "theme", "--name", "theme-demo"], ["shopify", "theme", "init", "theme-demo"]),
            (["--dry-run", "config-link"], ["shopify", "app", "config", "link"]),
            (["--dry-run", "config-use", "production"], ["shopify", "app", "config", "use", "production"]),
        ],
    )
    def test_main_dispatches_commands(self, argv, expected):
        with patch.object(ShopifyCliWrapper, "execute", return_value=0) as mock_execute:
            result = main(argv)

        assert result == 0
        command = mock_execute.call_args.args[0]
        assert command.args == expected
        assert mock_execute.call_args.args[1] is True

    def test_main_without_subcommand_returns_usage_error(self):
        assert main([]) == 2

    def test_parser_non_interactive_flag(self):
        args = parse_args(["--non-interactive", "app"])

        assert args.non_interactive is True
        assert args.command == "app"

    def test_deprecated_type_alias_maps_to_template_flag(self):
        with patch.object(ShopifyCliWrapper, "execute", return_value=0) as mock_execute:
            result = main(["--dry-run", "--non-interactive", "extension", "--type", "function"])

        assert result == 0
        command = mock_execute.call_args.args[0]
        assert command.args == ["shopify", "app", "generate", "extension", "--template", "function"]

    def test_config_flag_alias_maps_to_positional_config(self):
        with patch.object(ShopifyCliWrapper, "execute", return_value=0) as mock_execute:
            result = main(["--dry-run", "config-use", "--config", "production"])

        assert result == 0
        command = mock_execute.call_args.args[0]
        assert command.args == ["shopify", "app", "config", "use", "production"]
