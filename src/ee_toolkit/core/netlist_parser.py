"""Protel/DXP-style netlist parser.

Reads component and netlist sections into structured Python dicts. The
format is bracketed ``[...]`` for components with three lines
(designator, footprint, value) and parenthesized ``(...)`` for nets
with a name line followed by ``designator-pin`` nodes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

_COMPONENT_RE = re.compile(r"\[\s*\n(.*?)\n\]", re.S)
_NET_RE = re.compile(r"\(\s*\n(.*?)\n\)", re.S)
_NODE_RE = re.compile(r"^(.+)-([0-9A-Za-z]+)$")


def parse_netlist(path: str | Path) -> Tuple[dict, dict]:
    """Parse a Protel/DXP netlist file.

    Returns ``(components, nets)``:

    - components: ``{designator: (footprint, value)}``
    - nets: ``{net_name: [(designator, pin), ...]}``
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")

    components: dict[str, tuple[str, str]] = {}
    for block in _COMPONENT_RE.findall(text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) >= 3:
            components[lines[0]] = (lines[1], lines[2])

    nets: dict[str, list[tuple[str, str]]] = {}
    for block in _NET_RE.findall(text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        nodes: list[tuple[str, str]] = []
        for node_designator in lines[1:]:
            m = _NODE_RE.match(node_designator)
            if m:
                nodes.append((m.group(1), m.group(2)))
        nets[lines[0]] = nodes

    return components, nets
