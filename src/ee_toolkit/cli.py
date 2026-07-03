import argparse
import sys


def build_parser():
    parser = argparse.ArgumentParser(prog="ee", description="Electronics toolkit")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=False)
    return parser


def main(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)
    if not parsed.command:
        parser.print_help()
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
