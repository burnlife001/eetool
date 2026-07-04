import argparse
from unittest.mock import MagicMock, patch

import pytest

from eetool.commands import serial


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
            args = _args("send", cmd="k1", port="COM7", baud=115200)
            assert serial.run(args) == 0
            mock_open.assert_called_once_with("COM7", 115200)
            mock_ser.write.assert_called_once()


def test_serial_send_missing_port():
    with patch("eetool.commands.serial.find_ch340_ports", return_value=([], [])):
        args = _args("send", cmd="k1", port=None, baud=115200)
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
                args = _args("listen", port="COM7", baud=115200, hex=False, timeout=None, log="test.log")
                assert serial.run(args) == 0
                assert calls


def _args(command, **kwargs):
    base = {"serial_command": command}
    base.update(kwargs)
    return type("Args", (), base)()
