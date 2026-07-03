"""Tests for ee_toolkit.commands.capture.

The capture command delegates to ee_toolkit.capture.atk_cli via subprocess,
so we mock subprocess.call to assert the correct invocation.
"""

from __future__ import annotations

import argparse
import sys
from unittest.mock import patch

import pytest

from ee_toolkit.commands import capture


# ---------- add_subparser ----------


def test_add_subparser_parses_subcommand():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    capture.add_subparser(sub)
    parsed = parser.parse_args(["capture", "info", "wave.atkdl"])
    assert parsed.command == "capture"
    assert parsed.capture_command == "info"
    assert parsed.extra_args == ["wave.atkdl"]


def test_add_subparser_allows_no_subcommand():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    capture.add_subparser(sub)
    parsed = parser.parse_args(["capture"])
    assert parsed.capture_command is None
    assert parsed.extra_args == []


# ---------- run dispatcher (validation) ----------


def test_run_missing_subcommand_returns_2(capsys):
    args = argparse.Namespace(capture_command=None, extra_args=[])
    rc = capture.run(args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "missing subcommand" in err


def test_run_unknown_subcommand_returns_2(capsys):
    args = argparse.Namespace(capture_command="bogus", extra_args=[])
    rc = capture.run(args)
    assert rc == 2
    err = capsys.readouterr().err
    assert "unknown subcommand" in err
    assert "bogus" in err


@pytest.mark.parametrize("subcommand", sorted(capture.ALLOWED_SUBCOMMANDS))
def test_run_dispatches_known_subcommand(subcommand):
    args = argparse.Namespace(
        capture_command=subcommand, extra_args=["--ch", "0,1", "--duration", "3s"]
    )
    with patch("ee_toolkit.commands.capture.subprocess.call", return_value=0) as mock_call:
        rc = capture.run(args)
    assert rc == 0
    mock_call.assert_called_once()
    cmd = mock_call.call_args[0][0]
    assert cmd[0] == sys.executable
    assert cmd[1] == "-m"
    assert cmd[2] == capture.CLI_MODULE
    assert cmd[3] == subcommand
    assert cmd[4:] == ["--ch", "0,1", "--duration", "3s"]


def test_run_forwards_extra_args():
    args = argparse.Namespace(capture_command="export", extra_args=["x.atkdl", "--ch", "0"])
    with patch("ee_toolkit.commands.capture.subprocess.call", return_value=0) as mock_call:
        capture.run(args)
    cmd = mock_call.call_args[0][0]
    assert cmd[-3:] == ["x.atkdl", "--ch", "0"]


# ---------- lock integration ----------


def test_run_acquires_capture_lock():
    """run() must wrap the subprocess call in ProcessLock('capture')."""
    from unittest.mock import MagicMock

    args = argparse.Namespace(capture_command="info", extra_args=[])
    fake_lock_inst = MagicMock()
    fake_lock_inst.__enter__.return_value = fake_lock_inst
    fake_lock_inst.__exit__.return_value = False

    with patch("ee_toolkit.commands.capture.ProcessLock", return_value=fake_lock_inst) as mock_cls:
        with patch("ee_toolkit.commands.capture.subprocess.call", return_value=0):
            capture.run(args)
    mock_cls.assert_called_once_with(capture.LOCK_NAME, timeout=0)
    fake_lock_inst.__enter__.assert_called_once()
    fake_lock_inst.__exit__.assert_called_once()


# ---------- failure paths ----------


def test_run_handles_subprocess_missing_executable(capsys):
    args = argparse.Namespace(capture_command="info", extra_args=[])
    with patch("ee_toolkit.commands.capture.subprocess.call", side_effect=FileNotFoundError):
        rc = capture.run(args)
    assert rc == 1
    assert "failed to invoke" in capsys.readouterr().err
