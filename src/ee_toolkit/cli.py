import argparse
import sys

from ee_toolkit.commands import serial


def build_parser():
    parser = argparse.ArgumentParser(prog="ee", description="Electronics toolkit")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=False)

    serial.add_subparser(subparsers)

    return parser


def main(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)
    if not parsed.command:
        parser.print_help()
        return 0

    command_dispatch = {
        "serial": serial.run,
    }
    handler = command_dispatch.get(parsed.command)
    if handler is None:
        parser.print_help()
        return 0
    return handler(parsed)


if __name__ == "__main__":
    sys.exit(main())
