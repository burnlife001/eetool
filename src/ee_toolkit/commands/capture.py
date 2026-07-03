"""ATK-Logic capture command — wraps ee_toolkit.capture.atk_cli.

The heavy lifting (CLI parsing, file IO, decoding) lives in the
``ee_toolkit.capture`` package. This module re-exposes the same subcommands
under ``ee capture <subcommand> [args...]`` with a cross-process
``ProcessLock`` so concurrent launches don't fight over the GUI/USB device.

We only validate the subcommand name here; everything after is forwarded
verbatim to ``atk_cli.main`` via subprocess.

Hardware dependency: ATK-Logic.exe at ``D:/Programs/ATK-Logic`` and a
proxy DLL at ``E:/__electric/atk-logic-data``. Tests skip hardware via mocks.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from ee_toolkit.core.locks import ProcessLock

ALLOWED_SUBCOMMANDS = {
    "start",
    "info",
    "export",
    "decode",
    "list-decoders",
    "config",
    "classify",
    "pwm",
    "preflight",
}

LOCK_NAME = "capture"
CLI_MODULE = "ee_toolkit.capture.atk_cli"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register ``ee capture <subcommand> [args...]``."""
    parser = subparsers.add_parser("capture", help="ATK-Logic capture tools")
    parser.add_argument(
        "capture_command",
        nargs="?",
        default=None,
        help="capture subcommand (one of: %s)"
        % ", ".join(sorted(ALLOWED_SUBCOMMANDS)),
    )
    parser.add_argument(
        "extra_args",
        nargs=argparse.REMAINDER,
        help="Forwarded verbatim to atk_cli",
    )


def run(args: argparse.Namespace) -> int:
    """Dispatch ``ee capture ...`` to ee_toolkit.capture.atk_cli.main."""
    if args.capture_command is None:
        print(
            "capture: missing subcommand. Allowed: "
            + ", ".join(sorted(ALLOWED_SUBCOMMANDS)),
            file=sys.stderr,
        )
        return 2
    if args.capture_command not in ALLOWED_SUBCOMMANDS:
        print(
            f"capture: unknown subcommand {args.capture_command!r}. "
            f"Allowed: {', '.join(sorted(ALLOWED_SUBCOMMANDS))}",
            file=sys.stderr,
        )
        return 2

    with ProcessLock(LOCK_NAME, timeout=0):
        cmd = [
            sys.executable,
            "-m",
            CLI_MODULE,
            args.capture_command,
            *args.extra_args,
        ]
        try:
            return subprocess.call(cmd)
        except FileNotFoundError:
            print(f"capture: failed to invoke {cmd}", file=sys.stderr)
            return 1
