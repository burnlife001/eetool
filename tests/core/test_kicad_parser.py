"""Unit tests for ee_toolkit.core.kicad_parser."""

from __future__ import annotations

from pathlib import Path

from ee_toolkit.core.kicad_parser import parse_kicad_sym, parse_symbol


def test_parse_symbol_extracts_name_and_pins(tmp_path):
    sym = tmp_path / "sym.kicad_sym"
    sym.write_text(
        '(kicad_symbol_lib (version 20211014) (generator "test")\n'
        '(symbol "LM321"\n'
        '(pin passive line (at 5.08 0 0) (length 2.54)\n'
        '(name "OUT" (effects (font (size 1.27 1.27))))\n'
        '(number "1" (effects (font (size 1.27 1.27))))\n'
        ')\n'
        '(pin passive line (at -5.08 0 180) (length 2.54)\n'
        '(name "V+" (effects (font (size 1.27 1.27))))\n'
        '(number "2" (effects (font (size 1.27 1.27))))\n'
        ')\n'
        '(pin passive line (at 0 5.08 90) (length 2.54)\n'
        '(name "NC" (effects (font (size 1.27 1.27))))\n'
        '(number "3" (effects (font (size 1.27 1.27))))\n'
        ')\n'
        ')\n'
        ')\n',
        encoding="utf-8",
    )
    name, pins = parse_symbol(sym)
    assert name == "LM321"
    assert [p["number"] for p in pins] == ["1", "2", "3"]
    assert [p["name"] for p in pins] == ["OUT", "V+", "NC"]
    # angle → direction mapping
    directions = {p["number"]: p["direction"] for p in pins}
    assert directions["1"] == "right"
    assert directions["2"] == "left"
    assert directions["3"] == "up"


def test_parse_symbol_sorts_non_numeric_pins_last(tmp_path):
    sym = tmp_path / "sym.kicad_sym"
    sym.write_text(
        '(symbol "B"\n'
        '(pin passive line (at 0 0 0) (length 2.54)\n'
        '(name "B" (effects (font (size 1.27 1.27))))\n'
        '(number "B" (effects (font (size 1.27 1.27))))\n'
        ')\n'
        '(pin passive line (at 0 0 0) (length 2.54)\n'
        '(name "A" (effects (font (size 1.27 1.27))))\n'
        '(number "1" (effects (font (size 1.27 1.27))))\n'
        ')\n'
        ')\n',
        encoding="utf-8",
    )
    _, pins = parse_symbol(sym)
    assert [p["number"] for p in pins] == ["1", "B"]


def test_parse_symbol_no_match_returns_none_name(tmp_path):
    sym = tmp_path / "empty.kicad_sym"
    sym.write_text("(kicad_symbol_lib)\n", encoding="utf-8")
    name, pins = parse_symbol(sym)
    assert name is None
    assert pins == []


def test_parse_kicad_sym_alias_matches_parse_symbol(tmp_path):
    sym = tmp_path / "x.kicad_sym"
    sym.write_text(
        '(symbol "X"\n'
        '(pin passive line (at 0 0 0) (length 2.54)\n'
        '(name "a" (effects (font (size 1.27 1.27))))\n'
        '(number "1" (effects (font (size 1.27 1.27))))\n'
        ')\n)\n',
        encoding="utf-8",
    )
    assert parse_kicad_sym(sym) == parse_symbol(sym)


def test_parse_symbol_accepts_string_path(tmp_path):
    sym = tmp_path / "p.kicad_sym"
    sym.write_text(
        '(symbol "P"\n'
        '(pin passive line (at 0 0 0) (length 2.54)\n'
        '(name "x" (effects (font (size 1.27 1.27))))\n'
        '(number "9" (effects (font (size 1.27 1.27))))\n'
        ')\n)\n',
        encoding="utf-8",
    )
    name, pins = parse_symbol(str(sym))
    assert name == "P"
    assert pins[0]["number"] == "9"
