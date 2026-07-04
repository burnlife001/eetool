"""Tests for eetool.commands.capture.

The capture command delegates to eetool.capture.atk_cli via subprocess,
so we mock subprocess.call to assert the correct invocation.
"""

from __future__ import annotations

import argparse
import sys
from unittest.mock import patch

import pytest

from eetool.commands import capture


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
    with patch("eetool.commands.capture.subprocess.call", return_value=0) as mock_call:
        rc = capture.run(args)
    assert rc == 0
    mock_call.assert_called_once()
    cmd = mock_call.call_args[0][0]
    assert cmd[0] == sys.executable
    assert cmd[1] == "-m"
    expected_module = capture.ALT_MODULES.get(subcommand, capture.CLI_MODULE)
    assert cmd[2] == expected_module
    parent = capture.CAPTURE_VERB_PARENT.get(subcommand)
    if parent:
        assert cmd[3] == parent
        assert cmd[4] == subcommand
        assert cmd[5:] == ["--ch", "0,1", "--duration", "3s"]
    else:
        assert cmd[3] == subcommand
        assert cmd[4:] == ["--ch", "0,1", "--duration", "3s"]


def test_run_routes_start_to_capture_verb():
    """Regression: eetool capture start … must reach atk_cli as ``capture start …``.

    Previous bug: the wrapper forwarded ``start`` verbatim, but atk_cli
    only accepts ``capture`` as the top-level verb and ``start`` as its
    sub-action — so ``eetool capture start --ch 0`` was unreachable.
    """
    args = argparse.Namespace(
        capture_command="start", extra_args=["--ch", "0", "--duration", "5s"]
    )
    with patch("eetool.commands.capture.subprocess.call", return_value=0) as mock_call:
        rc = capture.run(args)
    assert rc == 0
    cmd = mock_call.call_args[0][0]
    assert cmd[2] == capture.CLI_MODULE
    assert cmd[3:5] == ["capture", "start"]
    assert cmd[5:] == ["--ch", "0", "--duration", "5s"]


def test_run_routes_classify_to_analyze_module():
    """``eetool capture classify`` must dispatch to the analyze subpackage, not atk_cli."""
    args = argparse.Namespace(
        capture_command="classify", extra_args=["wave.atkdl", "--json"]
    )
    with patch("eetool.commands.capture.subprocess.call", return_value=0) as mock_call:
        rc = capture.run(args)
    assert rc == 0
    cmd = mock_call.call_args[0][0]
    assert cmd[2] == "eetool.capture.analyze.atk_classify"
    assert cmd[3] == "classify"
    assert cmd[4:] == ["wave.atkdl", "--json"]


def test_run_routes_preflight_to_preflight_module():
    """``eetool capture preflight`` is a standalone script, not part of atk_cli."""
    args = argparse.Namespace(capture_command="preflight", extra_args=["--fix"])
    with patch("eetool.commands.capture.subprocess.call", return_value=0) as mock_call:
        rc = capture.run(args)
    assert rc == 0
    cmd = mock_call.call_args[0][0]
    assert cmd[2] == "eetool.capture.capture.atk_preflight"
    assert cmd[3] == "preflight"
    assert cmd[4:] == ["--fix"]


def test_run_forwards_extra_args():
    args = argparse.Namespace(capture_command="export", extra_args=["x.atkdl", "--ch", "0"])
    with patch("eetool.commands.capture.subprocess.call", return_value=0) as mock_call:
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

    with patch("eetool.commands.capture.ProcessLock", return_value=fake_lock_inst) as mock_cls:
        with patch("eetool.commands.capture.subprocess.call", return_value=0):
            capture.run(args)
    mock_cls.assert_called_once_with(capture.LOCK_NAME, timeout=0)
    fake_lock_inst.__enter__.assert_called_once()
    fake_lock_inst.__exit__.assert_called_once()


# ---------- failure paths ----------


def test_run_handles_subprocess_missing_executable(capsys):
    args = argparse.Namespace(capture_command="info", extra_args=[])
    with patch("eetool.commands.capture.subprocess.call", side_effect=FileNotFoundError):
        rc = capture.run(args)
    assert rc == 1
    assert "failed to invoke" in capsys.readouterr().err
