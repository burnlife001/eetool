import json
from pathlib import Path

from ee_toolkit.commands.schmd_from_netlist import run


def _args(command, **kwargs):
    base = {"schmd_command": command, "netlist": None}
    base.update(kwargs)
    return type("Args", (), base)()


def _make_netlist_and_docs(tmp_path):
    net = tmp_path / "board.NET"
    net.write_text(
        "[\nU1\nLQFP-48\nMM32F0140\n]\n(\nVCC\nU1-1\n)\n(\nNetXxx_1\nU1-2\nR1-1\n)\n",
        encoding="utf-8",
    )
    shared = tmp_path / "__shared_docs"
    shared.mkdir()
    chip = shared / "mm32f0140.json"
    chip.write_text(json.dumps({
        "chip_name": "MM32F0140",
        "packages": ["LQFP48"],
        "pins": [
            {"name": "VDD", "type": "S", "main_function": "VDD", "packages": {"LQFP48": 1}},
            {"name": "PA0", "type": "IO", "main_function": "PA0", "packages": {"LQFP48": 2}},
        ]
    }), encoding="utf-8")
    return net, shared


def test_schmd_map(tmp_path, capsys):
    net, shared = _make_netlist_and_docs(tmp_path)
    args = _args("map", netlist=str(net), designator="U1", package="LQFP48", shared_docs=str(shared), source_dir=None, out=None)
    assert run(args) == 0
    captured = capsys.readouterr()
    assert "MM32F0140" in captured.out


def test_schmd_infer(tmp_path, capsys):
    net, shared = _make_netlist_and_docs(tmp_path)
    args = _args("infer", netlist=str(net), designator="U1", package="LQFP48", shared_docs=str(shared), out=None)
    assert run(args) == 0
    captured = capsys.readouterr()
    assert "待定引脚邻接拓扑" in captured.out


def test_parse_netlist():
    from ee_toolkit.commands.schmd_from_netlist import parse_netlist

    text = "[\nU1\nLQFP48\nMM32F0140\n]\n(\nVCC\nU1-1\n)\n"
    comp, nets = parse_netlist_from_text(text)
    assert comp["U1"] == ("LQFP48", "MM32F0140")
    assert nets["VCC"] == [("U1", "1")]


def parse_netlist_from_text(text):
    from ee_toolkit.commands.schmd_from_netlist import parse_netlist
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".NET", delete=False, encoding="utf-8") as f:
        f.write(text)
        name = f.name
    try:
        return parse_netlist(name)
    finally:
        import os
        os.unlink(name)
