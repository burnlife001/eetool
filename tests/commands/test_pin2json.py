import json
from pathlib import Path

from ee_toolkit.commands.pin2json import run


_KICAD_SYM = """(kicad_symbol_lib (version 20211014)
  (symbol "LM321MFX{slash}NOPB"
    (pin power_in line (at -7.62 5.08 0) (length 2.54)
      (name "VCC" (effects (font (size 1.27 1.27))))
      (number "1" (effects (font (size 1.27 1.27))))
    )
    (pin input line (at -7.62 0 0) (length 2.54)
      (name "IN+" (effects (font (size 1.27 1.27))))
      (number "2" (effects (font (size 1.27 1.27))))
    )
    (pin output line (at 7.62 0 180) (length 2.54)
      (name "OUT" (effects (font (size 1.27 1.27))))
      (number "3" (effects (font (size 1.27 1.27))))
    )
  )
)"""


def test_pin2json_kicad_file(tmp_path, capsys):
    sym = tmp_path / "test.kicad_sym"
    sym.write_text(_KICAD_SYM, encoding="utf-8")
    args = type("Args", (), {"input": str(sym), "output": None})()
    assert run(args) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["symbol"] == "LM321MFX"
    assert result["pin_count"] == 3
    assert result["pins"]["1"] == "VCC"


def test_pin2json_kicad_file_with_output(tmp_path):
    sym = tmp_path / "test.kicad_sym"
    sym.write_text(_KICAD_SYM, encoding="utf-8")
    out = tmp_path / "pins.json"
    args = type("Args", (), {"input": str(sym), "output": str(out)})()
    assert run(args) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["symbol"] == "LM321MFX"
    assert result["pin_count"] == 3


def test_pin2json_missing_file(capsys):
    args = type("Args", (), {"input": "does-not-exist.kicad_sym", "output": None})()
    assert run(args) == 1
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert "error" in result


def test_is_part_id():
    from ee_toolkit.commands.pin2json import is_part_id

    assert is_part_id("C9405")
    assert is_part_id("c12345")
    assert not is_part_id("LM321")
    assert not is_part_id("")
