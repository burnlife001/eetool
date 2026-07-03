"""KiCad .kicad_sym parser.

Pure-Python, no external dependencies. Returns the symbol name and a
list of pin dicts with stable keys (number, name, electrical_type,
graphic_type, direction, pos, length).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_PIN_RE = re.compile(
    r"\(pin\s+(\S+)\s+(\S+).*?"
    r"\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\).*?"
    r"\(length\s+([-\d.]+)\).*?"
    r'\(name\s+"((?:[^"\\]|\\.)*)".*?'
    r'\(number\s+"((?:[^"\\]|\\.)*)".*?'
    r"\)",
    re.DOTALL,
)

_ANGLE_TO_DIRECTION = {0: "right", 90: "up", 180: "left", 270: "down"}


def _pin_sort_key(p: dict) -> tuple:
    """Sort numeric pins first, then non-numeric by their string."""
    try:
        return (0, int(p["number"]))
    except ValueError:
        return (1, p["number"])


def parse_symbol(path: str | Path) -> tuple[Optional[str], list[dict]]:
    """Parse a .kicad_sym file.

    Returns ``(symbol_name, pins)`` where ``pins`` is sorted by number.
    ``symbol_name`` is None when the top-level ``(symbol "...")`` regex
    cannot match.
    """
    text = Path(path).read_text(encoding="utf-8")

    sym_match = re.search(r'\(symbol\s+"([^"]+)"', text)
    symbol_name = sym_match.group(1) if sym_match else None

    pins: list[dict] = []
    for m in _PIN_RE.finditer(text):
        elec_type, graphic_type, x, y, angle, length, name, number = m.groups()
        angle_int = int(float(angle)) % 360
        direction = _ANGLE_TO_DIRECTION.get(angle_int, str(angle_int))
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

    pins.sort(key=_pin_sort_key)
    return symbol_name, pins


# Backwards-compatible alias used by the original pin2json command.
def parse_kicad_sym(path: str | Path) -> tuple[Optional[str], list[dict]]:
    return parse_symbol(path)
