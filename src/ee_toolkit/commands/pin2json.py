import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def is_part_id(arg: str) -> bool:
    """Return True if arg looks like a JLCPCB/LCSC part id (Cxxxxx)."""
    return bool(arg) and arg[0].upper() == "C" and arg[1:].isdigit()


_PACKAGE_SUFFIXES = (
    "/NOPB",
    "/T&R",
    "/REEL",
    "/TAPE",
    "/TR",
    "/MP",
    "/EE",
    "/T",
)


def clean_symbol_name(raw: str) -> str:
    """Decode KiCad S-expression escapes and strip common packaging suffixes."""
    if not raw:
        return raw
    name = raw.replace("{slash}", "/").replace("{backslash}", "\\")
    upper = name.upper()
    changed = True
    while changed:
        changed = False
        for sfx in _PACKAGE_SUFFIXES:
            if upper.endswith(sfx) and len(name) > len(sfx):
                name = name[: -len(sfx)]
                upper = name.upper()
                changed = True
                break
    return name


def generate_symbol(part_id: str):
    """Generate a KiCad symbol for part_id using JLC2KiCadLib.

    Returns the path to the generated .kicad_sym file and the temp directory.
    """
    tmp_root = tempfile.mkdtemp(prefix="ee-pin2json-")
    out_dir = os.path.join(tmp_root, "out")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "JLC2KiCadLib.JLC2KiCadLib",
            part_id,
            "--no_footprint",
            "-dir",
            out_dir,
            "-symbol_lib",
            "tmp",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    sym_file = os.path.join(out_dir, "symbol", "tmp.kicad_sym")
    if not os.path.exists(sym_file):
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise RuntimeError(f"Symbol file not created at expected path: {sym_file}")

    return sym_file, tmp_root


def parse_kicad_sym(path: str):
    """Parse a .kicad_sym file and return (symbol_name, pins)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()

    sym_match = re.search(r'\(symbol\s+"([^"]+)"', text)
    symbol_name = sym_match.group(1) if sym_match else None

    pins = []
    pin_re = re.compile(
        r'\(pin\s+(\S+)\s+(\S+).*?'
        r'\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\).*?'
        r'\(length\s+([-\d.]+)\).*?'
        r'\(name\s+"((?:[^"\\]|\\.)*)".*?'
        r'\(number\s+"((?:[^"\\]|\\.)*)".*?'
        r'\)',
        re.DOTALL,
    )

    for m in pin_re.finditer(text):
        elec_type, graphic_type, x, y, angle, length, name, number = m.groups()
        angle_int = int(float(angle)) % 360
        direction = {
            0: "right",
            90: "up",
            180: "left",
            270: "down",
        }.get(angle_int, str(angle_int))

        pins.append(
            {
                "number": number,
                "name": name,
                "electrical_type": elec_type,
                "graphic_type": graphic_type,
                "direction": direction,
                "pos": [float(x), float(y)],
                "length": float(length),
            }
        )

    def sort_key(p):
        try:
            return (0, int(p["number"]))
        except ValueError:
            return (1, p["number"])

    pins.sort(key=sort_key)
    return symbol_name, pins


def run(args):
    source = args.input.strip()
    output_path = args.output.strip() if args.output else None
    cleanup_dir = None

    try:
        if is_part_id(source):
            sym_file, cleanup_dir = generate_symbol(source)
        else:
            sym_file = source
            if not os.path.exists(sym_file):
                print(
                    json.dumps(
                        {"error": f"file not found: {sym_file}", "symbol": None, "pins": []},
                        ensure_ascii=False,
                    )
                )
                return 1

        symbol_name, pins = parse_kicad_sym(sym_file)
        pin_dict = {p["number"]: p["name"] for p in pins}

        result = {
            "symbol": clean_symbol_name(symbol_name),
            "source": source,
            "pin_count": len(pins),
            "pins": pin_dict,
        }
        json_text = json.dumps(result, indent=2, ensure_ascii=False)
        print(json_text)

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(json_text + "\n")

        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {"error": str(exc), "source": source, "symbol": None, "pins": []},
                ensure_ascii=False,
            )
        )
        return 1
    finally:
        if cleanup_dir:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


def add_subparser(subparsers):
    parser = subparsers.add_parser("pin2json", help="Convert KiCad symbol or JLC part to pin JSON")
    parser.add_argument("input", help="JLCPCB part id (Cxxxxx) or path to .kicad_sym file")
    parser.add_argument("--output", "-o", default=None, help="Optional output JSON file path")
