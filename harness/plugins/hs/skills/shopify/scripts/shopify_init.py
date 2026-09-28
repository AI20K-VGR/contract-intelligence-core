#!/usr/bin/env python3
"""
Thin wrapper around official Shopify CLI project commands.

The wrapper builds list-based subprocess arguments, supports dry-run output, and
never writes Shopify config, secrets, package files, or generated scaffolds.
"""

import argparse
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence


@dataclass
class ShopifyCommand:
    """Executable command plus display metadata."""

    args: List[str]
    description: str


class ShopifyCliWrapper:
    """Build and run official Shopify CLI commands."""

    def __init__(
        self,
        executable: str = "shopify",
        input_func: Callable[[str], str] = input,
        print_func: Callable[..., None] = print,
    ):
        self.executable = executable
        self.input_func = input_func
        self.print_func = print_func

    def prompt(self, message: str, default: Optional[str] = None) -> str:
        """Prompt for a missing interactive value."""
        prompt = f"{message} [{default}]: " if default else f"{message}: "
        value = self.input_func(prompt).strip()
        return value or (default or "")

    def resolve_executable(self) -> Optional[str]:
        """Resolve Shopify CLI executable without auto-installing it."""
        return shutil.which(self.executable)

    def ensure_cli_available(self) -> Optional[str]:
        """Verify Shopify CLI exists and responds to version checks."""
        executable_path = self.resolve_executable()
        if not executable_path:
            self.print_func("Shopify CLI not found. Install with: npm install -g @shopify/cli@latest", file=sys.stderr)
            return None

        try:
            result = subprocess.run(
                [executable_path, "version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            self.print_func("Shopify CLI version check timed out.", file=sys.stderr)
            return None
        except OSError as error:
            self.print_func(f"Shopify CLI version check failed: {error}", file=sys.stderr)
            return None

        if result.returncode != 0:
            self.print_func("Shopify CLI version check failed.", file=sys.stderr)
            if result.stderr:
                self.print_func(result.stderr.strip(), file=sys.stderr)
            return None

        return executable_path

    def build_app_command(self, name: Optional[str], path: Optional[str], interactive: bool) -> ShopifyCommand:
        """Build `shopify app init` command."""
        args = [self.executable, "app", "init"]
        if name is None and interactive:
            name = self.prompt("App name", "my-shopify-app")
        if name:
            args.extend(["--name", name])
        if path:
            args.extend(["--path", path])
        return ShopifyCommand(args=args, description="Create Shopify app from official CLI template")

    def build_extension_command(self, extension_template: Optional[str], name: Optional[str], interactive: bool) -> ShopifyCommand:
        """Build `shopify app generate extension` command."""
        args = [self.executable, "app", "generate", "extension"]
        if extension_template is None and interactive:
            # No default: an empty answer falls through to the Shopify CLI
            # interactive template picker. Avoid defaulting to a hardcoded
            # template value, since extension templates change between CLI versions.
            extension_template = self.prompt("Extension template (leave blank for interactive picker)")
        if name is None and interactive:
            name = self.prompt("Extension name", "my-extension")
        if extension_template:
            args.extend(["--template", extension_template])
        if name:
            args.extend(["--name", name])
        return ShopifyCommand(args=args, description="Generate Shopify app extension from official CLI template")

    def build_theme_command(self, name: Optional[str], path: Optional[str], interactive: bool) -> ShopifyCommand:
        """Build `shopify theme init` command."""
        args = [self.executable, "theme", "init"]
        if name is None and interactive:
            name = self.prompt("Theme name", "my-theme")
        if name:
            args.append(name)
        if path:
            args.extend(["--path", path])
        return ShopifyCommand(args=args, description="Create Shopify theme from official CLI template")

    def build_config_link_command(self) -> ShopifyCommand:
        """Build `shopify app config link` command."""
        return ShopifyCommand(
            args=[self.executable, "app", "config", "link"],
            description="Link local app config to a Shopify app",
        )

    def build_config_use_command(self, config: Optional[str]) -> ShopifyCommand:
        """Build `shopify app config use` command."""
        args = [self.executable, "app", "config", "use"]
        if config:
            args.append(config)
        return ShopifyCommand(args=args, description="Select Shopify app config")

    def execute(self, command: ShopifyCommand, dry_run: bool) -> int:
        """Run a Shopify command or print a display-only dry run."""
        display_command = shlex.join(command.args)
        if dry_run:
            self.print_func(f"Dry run only; no subprocess executed: {display_command}")
            return 0

        executable_path = self.ensure_cli_available()
        if not executable_path:
            return 127

        run_args = [executable_path, *command.args[1:]]
        self.print_func(f"Running: {shlex.join(run_args)}")
        result = subprocess.run(run_args, check=False)
        return result.returncode


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    parser = argparse.ArgumentParser(
        description="Thin wrapper around official Shopify CLI project commands.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print command without executing Shopify CLI")
    parser.add_argument("--non-interactive", action="store_true", help="Do not prompt for missing optional values")

    subparsers = parser.add_subparsers(dest="command")

    app_parser = subparsers.add_parser("app", help="Run shopify app init")
    app_parser.add_argument("--name", help="App name passed as one CLI argument")
    app_parser.add_argument("--path", help="Target path passed as one CLI argument")

    extension_parser = subparsers.add_parser("extension", help="Run shopify app generate extension")
    extension_parser.add_argument("--template", dest="extension_template", help="Extension template")
    extension_parser.add_argument("--type", dest="extension_template", help=argparse.SUPPRESS)
    extension_parser.add_argument("--name", help="Extension name passed as one CLI argument")

    theme_parser = subparsers.add_parser("theme", help="Run shopify theme init")
    theme_parser.add_argument("--name", help="Theme name passed as one CLI argument")
    theme_parser.add_argument("--path", help="Target path passed as one CLI argument")

    subparsers.add_parser("config-link", help="Run shopify app config link")

    config_use_parser = subparsers.add_parser("config-use", help="Run shopify app config use")
    config_use_parser.add_argument("config_name", nargs="?", help="Named app config to select")
    config_use_parser.add_argument("--config", dest="config_flag", help=argparse.SUPPRESS)

    return parser


def build_command(args: argparse.Namespace, wrapper: ShopifyCliWrapper) -> Optional[ShopifyCommand]:
    """Convert parsed arguments into a Shopify command."""
    interactive = not args.non_interactive

    if args.command == "app":
        return wrapper.build_app_command(args.name, args.path, interactive)
    if args.command == "extension":
        return wrapper.build_extension_command(args.extension_template, args.name, interactive)
    if args.command == "theme":
        return wrapper.build_theme_command(args.name, args.path, interactive)
    if args.command == "config-link":
        return wrapper.build_config_link_command()
    if args.command == "config-use":
        return wrapper.build_config_use_command(args.config_name or args.config_flag)

    return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse arguments and return process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 2

    wrapper = ShopifyCliWrapper()
    command = build_command(args, wrapper)
    if command is None:
        parser.print_help()
        return 2

    return wrapper.execute(command, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
