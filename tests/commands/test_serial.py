import argparse
from unittest.mock import MagicMock, patch

import pytest

from eetool.commands import serial


@pytest.fixture(autouse=True)
def isolate_serial_ini(tmp_path, monkeypatch):
    """Keep serial.ini in a temp directory so tests do not pollute ~/.local/share."""
    monkeypatch.setattr(serial, "_SERIAL_INI", tmp_path / "serial.ini")


def test_add_subparser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    serial.add_subparser(subparsers)
    parsed = parser.parse_args(["serial", "list"])
    assert parsed.serial_command == "list"


def test_serial_list_with_no_ports(capsys):
    with patch("eetool.commands.serial.serial.tools.list_ports.comports", return_value=[]):
        assert serial.run(_args("list")) == 0
        captured = capsys.readouterr()
        assert "No serial ports detected" in captured.out


def test_serial_list_with_ports(capsys):
    port = MagicMock()
    port.device = "COM7"
    port.description = "USB-SERIAL CH340"
    with patch("eetool.commands.serial.serial.tools.list_ports.comports", return_value=[port]):
        assert serial.run(_args("list")) == 0
        captured = capsys.readouterr()
        assert "COM7" in captured.out
        assert "CH340" in captured.out


def test_serial_send_success():
    mock_ser = MagicMock()
    with patch("eetool.commands.serial._open_serial", return_value=mock_ser) as mock_open:
        with patch("eetool.commands.serial.ProcessLock") as mock_lock_cls:
            mock_lock = MagicMock()
            mock_lock_cls.return_value = mock_lock
            args = _args("send", cmd="k1", port="COM7", baud=115200,
                         bytesize=8, parity="N", stopbits=1)
            assert serial.run(args) == 0
            mock_open.assert_called_once_with("COM7", 115200, 8, "N", 1)
            mock_ser.write.assert_called_once()


def test_serial_send_missing_port():
    with patch("eetool.commands.serial.find_ch340_ports", return_value=([], [])):
        args = _args("send", cmd="k1", port=None, baud=115200,
                     bytesize=8, parity="N", stopbits=1)
        assert serial.run(args) == 1


def test_serial_listen_success():
    mock_ser = MagicMock()
    mock_ser.in_waiting = True
    mock_ser.readline.return_value = b"hello\n"
    mock_ser.port = "COM7"
    mock_ser.baudrate = 115200

    calls = []

    def fake_read_loop(ser, **kwargs):
        calls.append(kwargs)

    with patch("eetool.commands.serial._open_serial", return_value=mock_ser):
        with patch("eetool.commands.serial._read_loop", side_effect=fake_read_loop):
            with patch("eetool.commands.serial.ProcessLock") as mock_lock_cls:
                mock_lock = MagicMock()
                mock_lock_cls.return_value = mock_lock
                args = _args("listen", port="COM7", baud=115200, hex=False,
                             timeout=None, log="test.log",
                             bytesize=8, parity="N", stopbits=1)
                assert serial.run(args) == 0
                assert calls


def test_load_serial_config_returns_typed_values(tmp_path, monkeypatch):
    monkeypatch.setattr(serial, "_SERIAL_INI", tmp_path / "serial.ini")
    ini = tmp_path / "serial.ini"
    ini.write_text(
        "[serial]\nport = COM7\nbaud = 9600\nbytesize = 7\n"
        "parity = E\nstopbits = 2\ntimeout = 5\nhex = true\n",
        encoding="utf-8",
    )
    cfg = serial.load_serial_config()
    assert cfg["port"] == "COM7"
    assert cfg["baud"] == 9600
    assert cfg["bytesize"] == 7
    assert cfg["parity"] == "E"
    assert cfg["stopbits"] == 2.0
    assert cfg["timeout"] == 5.0
    assert cfg["hex"] is True


def test_load_serial_config_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(serial, "_SERIAL_INI", tmp_path / "missing.ini")
    assert serial.load_serial_config() == {}


def test_save_serial_config_writes_ini(tmp_path, monkeypatch):
    monkeypatch.setattr(serial, "_SERIAL_INI", tmp_path / "serial.ini")
    args = _args(
        "send", port="COM7", baud=9600, bytesize=7,
        parity="E", stopbits=2, hex=True, timeout=5.0,
    )
    serial.save_serial_config(args)
    text = (tmp_path / "serial.ini").read_text(encoding="utf-8")
    assert "port = COM7" in text
    assert "baud = 9600" in text
    assert "bytesize = 7" in text
    assert "parity = E" in text
    assert "stopbits = 2" in text
    assert "hex = true" in text
    assert "timeout = 5.0" in text


def test_apply_ini_defaults_fills_missing_values(tmp_path, monkeypatch):
    monkeypatch.setattr(serial, "_SERIAL_INI", tmp_path / "serial.ini")
    (tmp_path / "serial.ini").write_text(
        "[serial]\nbaud = 9600\nbytesize = 7\nparity = E\nstopbits = 2\nhex = true\n",
        encoding="utf-8",
    )
    args = _args("listen", port=None, baud=None, bytesize=None,
                 parity=None, stopbits=None, hex=None, timeout=None, log="test.log")
    serial._apply_ini_defaults(args)
    assert args.baud == 9600
    assert args.bytesize == 7
    assert args.parity == "E"
    assert args.stopbits == 2.0
    assert args.hex is True


def _args(command, **kwargs):
    base = {"serial_command": command}
    base.update(kwargs)
    return type("Args", (), base)()
