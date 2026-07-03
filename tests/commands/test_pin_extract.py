import argparse
from unittest.mock import MagicMock, patch

from ee_toolkit.commands.pin_extract import (
    add_subparser,
    run,
    cmd_verify,
    parse_md_tables,
    check_file,
    check_pin_table,
)


def test_add_subparser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    add_subparser(subparsers)
    parsed = parser.parse_args(["pin", "extract-search", "dummy.pdf"])
    assert parsed.pin_command == "extract-search"
    assert parsed.pdf == "dummy.pdf"


def test_cmd_search(capsys):
    args = type("Args", (), {"pin_command": "extract-search", "pdf": "dummy.pdf"})()
    with patch("ee_toolkit.commands.pin_extract.search_pages", return_value=([32, 33], [36, 37])):
        assert run(args) == 0
        captured = capsys.readouterr()
        assert "Pin assignment pages" in captured.out


def test_cmd_extract_mocked():
    args = type("Args", (), {
        "pin_command": "extract",
        "pdf": "dummy.pdf",
        "pin_pages": "32-33",
        "mux_pages": "36-37",
        "ports": "PA,PB,PC,PD",
        "mux_cols": None,
        "output": None,
        "chip_name": "TEST",
        "flavor": "lattice",
        "package": None,
    })()

    pin_df = MagicMock()
    pin_df.columns = ["Name", "Type", "LQFP48"]
    pin_df.iterrows.return_value = iter([])
    pin_df.__bool__ = lambda self: True

    with patch("ee_toolkit.commands.pin_extract.search_pages", return_value=([32, 33], [36, 37])):
        with patch("ee_toolkit.commands.pin_extract.detect_ports", return_value=["PA", "PB", "PC", "PD"]):
            with patch("ee_toolkit.commands.pin_extract.detect_mux_cols", return_value=(9, ["Pin"] + [f"AF{i}" for i in range(8)], 8)):
                with patch("ee_toolkit.commands.pin_extract.extract_pin_assignment", return_value=pin_df):
                    with patch("ee_toolkit.commands.pin_extract.extract_multiplexing", return_value={"PA": MagicMock()}):
                        with patch("ee_toolkit.commands.pin_extract.build_json", return_value={"chip_name": "TEST"}):
                            with patch("builtins.open") as mock_open:
                                assert run(args) == 0


def test_cmd_verify_with_valid_markdown(tmp_path):
    rows = "\n".join([f"| {i} | PA{i} | IO |" for i in range(20)])
    md = tmp_path / "test.md"
    md.write_text(
        f"# Test\n\n## Pin Assignment\n\n| Pin | Name | Type |\n| --- | --- | --- |\n{rows}\n\n"
        "## PA Port Multiplexing\n\n| Pin | AF0 | AF1 |\n| --- | --- | --- |\n"
        + "\n".join([f"| PA{i} | AF | AF |" for i in range(20)])
        + "\n",
        encoding="utf-8",
    )
    args = type("Args", (), {
        "pin_command": "extract-verify",
        "markdown": str(md),
        "ports": "PA",
        "mux_cols": 3,
    })()
    assert cmd_verify(args) == 0


def test_parse_md_tables():
    text = "## T\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    tables = parse_md_tables(text)
    assert len(tables) == 1
    assert tables[0]["h2"] == "T"
    assert tables[0]["columns"] == ["A", "B"]
    assert tables[0]["rows"] == [["1", "2"]]


def test_check_file(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("hello", encoding="utf-8")
    p, w, fail, msgs = check_file(str(f))
    assert p == 1
    assert fail == 0


def test_check_pin_table():
    tables = [{
        "h2": "Pin Assignment",
        "columns": ["Pin", "Name", "Type"],
        "rows": [["1", "PA0", "IO"]] * 20,
    }]
    p, w, f, msgs = check_pin_table(tables, "")
    assert f == 0
    assert p >= 1
