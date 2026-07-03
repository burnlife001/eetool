"""Unit tests for ee_toolkit.core.netlist_parser."""

from __future__ import annotations

from pathlib import Path

from ee_toolkit.core.netlist_parser import parse_netlist


def test_parse_netlist_components_and_nets(tmp_path):
    txt = (
        "[\n"
        "U1\n"
        "LQFP-48\n"
        "MM32F0140\n"
        "]\n"
        "[\n"
        "C1\n"
        "0603\n"
        "100nF\n"
        "]\n"
        "(\n"
        "VCC\n"
        "U1-1\n"
        "C1-1\n"
        ")\n"
        "(\n"
        "GND\n"
        "U1-48\n"
        "C1-2\n"
        ")\n"
    )
    net = tmp_path / "board.NET"
    net.write_text(txt, encoding="utf-8")
    comp, nets = parse_netlist(net)
    assert comp == {
        "U1": ("LQFP-48", "MM32F0140"),
        "C1": ("0603", "100nF"),
    }
    assert nets == {
        "VCC": [("U1", "1"), ("C1", "1")],
        "GND": [("U1", "48"), ("C1", "2")],
    }


def test_parse_netlist_accepts_string_path(tmp_path):
    path = tmp_path / "x.NET"
    path.write_text("(\nN\nA-1\n)\n", encoding="utf-8")
    comp, nets = parse_netlist(str(path))
    assert comp == {}
    assert nets == {"N": [("A", "1")]}


def test_parse_netlist_empty_input(tmp_path):
    path = tmp_path / "empty.NET"
    path.write_text("", encoding="utf-8")
    comp, nets = parse_netlist(path)
    assert comp == {}
    assert nets == {}


def test_parse_netlist_ignores_unparseable_nodes(tmp_path):
    path = tmp_path / "weird.NET"
    path.write_text("(\nNAME\nthisisnotanode\nU1-3\n)\n", encoding="utf-8")
    comp, nets = parse_netlist(path)
    # "thisisnotanode" has no '-' so it is skipped; only "U1-3" remains
    assert nets == {"NAME": [("U1", "3")]}
    assert comp == {}


def test_parse_netlist_handles_windows_line_endings(tmp_path):
    path = tmp_path / "crlf.NET"
    body = (
        "[\r\nU1\r\nLQFP48\r\nMCU\r\n]\r\n"
        "(\r\nVDD\r\nU1-1\r\n)\r\n"
    )
    path.write_bytes(body.encode("utf-8"))
    comp, nets = parse_netlist(path)
    assert comp == {"U1": ("LQFP48", "MCU")}
    assert nets == {"VDD": [("U1", "1")]}
