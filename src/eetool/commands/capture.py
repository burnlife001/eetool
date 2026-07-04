"""ATK-Logic capture command — wraps the eetool.capture package.

The heavy lifting (CLI parsing, file IO, decoding) lives in the
``eetool.capture`` package. This module re-exposes a flat
``eetool capture <subcommand> [args...]`` surface with a cross-process
``ProcessLock`` so concurrent launches don't fight over the GUI/USB device.

We only validate the subcommand name here; everything after is forwarded
verbatim to the underlying CLI module via subprocess.

Hardware dependency: ATK-Logic.exe at ``D:/Programs/ATK-Logic`` and a
proxy DLL at ``E:/__electric/atk-logic-data``. Tests skip hardware via mocks.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from eetool.core.locks import ProcessLock

LOCK_NAME = "capture"
CLI_MODULE = "eetool.capture.atk_cli"

#: Flat set of ``eetool capture`` subcommands exposed to the user. Some of these
#: are top-level verbs in :mod:`eetool.capture.atk_cli` (e.g. ``info``,
#: ``export``); others are second-level verbs that the CLI module exposes
#: under a parent (``capture start``, ``config set``); the rest live in
#: separate entry-point modules (classify, pwm, preflight).
ALLOWED_SUBCOMMANDS = {
    # atk_cli top-level verbs (forwarded as-is)
    "info",
    "export",
    "decode",
    "list-decoders",
    # atk_cli second-level verbs (parent verb inserted on dispatch)
    "start",
    "stop",
    "show",
    "set",
    # separate entry-point modules
    "classify",
    "pwm",
    "preflight",
}

#: Second-level verbs that must be dispatched under a parent verb in
#: :mod:`eetool.capture.atk_cli`. Mapping is ``subcommand → parent``.
CAPTURE_VERB_PARENT = {
    "start": "capture",
    "stop": "capture",
    "show": "config",
    "set": "config",
}

#: Subcommands that live in a different module than :data:`CLI_MODULE`.
ALT_MODULES = {
    "classify": "eetool.capture.analyze.atk_classify",
    "pwm": "eetool.capture.analyze.atk_pwm",
    "preflight": "eetool.capture.capture.atk_preflight",
}


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register ``eetool capture <subcommand> [args...]``."""
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
        help="Forwarded verbatim to the underlying CLI module",
    )


def run(args: argparse.Namespace) -> int:
    """Dispatch ``eetool capture ...`` to the appropriate CLI entry point."""
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

    module = ALT_MODULES.get(args.capture_command, CLI_MODULE)
    parent = CAPTURE_VERB_PARENT.get(args.capture_command)
    forwarded_verb = [parent, args.capture_command] if parent else [args.capture_command]

    with ProcessLock(LOCK_NAME, timeout=0):
        cmd = [
            sys.executable,
            "-m",
            module,
            *forwarded_verb,
            *args.extra_args,
        ]
        try:
            return subprocess.call(cmd)
        except FileNotFoundError:
            print(f"capture: failed to invoke {cmd}", file=sys.stderr)
            return 1
