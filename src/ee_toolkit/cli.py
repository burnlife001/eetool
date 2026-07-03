import argparse
import sys

from ee_toolkit.commands import (
    capture,
    keil,
    pin2json,
    pin_extract,
    schmd_from_netlist,
    serial,
)


def build_parser():
    parser = argparse.ArgumentParser(prog="ee", description="Electronics toolkit")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=False)

    serial.add_subparser(subparsers)
    pin2json.add_subparser(subparsers)
    pin_extract.add_subparser(subparsers)
    schmd_from_netlist.add_subparser(subparsers)
    keil.add_subparser(subparsers)
    capture.add_subparser(subparsers)

    return parser


def main(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)
    if not parsed.command:
        parser.print_help()
        return 0

    command_dispatch = {
        "serial": serial.run,
        "pin2json": pin2json.run,
        "pin": pin_extract.run,
        "schmd-from-netlist": schmd_from_netlist.run,
        "keil": keil.run,
        "capture": capture.run,
    }
    handler = command_dispatch.get(parsed.command)
    if handler is None:
        parser.print_help()
        return 0
    return handler(parsed)


if __name__ == "__main__":
    sys.exit(main())
