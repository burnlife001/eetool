"""Integration smoke tests for the assembled `eetool` CLI."""

from __future__ import annotations

import re
import subprocess
import sys

EXPECTED_TOP_LEVEL = {
    "serial",
    "pin2json",
    "pin",
    "schmd-from-netlist",
    "keil",
    "capture",
}


def test_all_top_level_commands_in_help():
    """`eetool --help` must expose every top-level command."""
    result = subprocess.run(
        [sys.executable, "-m", "eetool.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    normalized = re.sub(r"\s+", " ", result.stdout)
    for cmd in EXPECTED_TOP_LEVEL:
        assert cmd in normalized, (
            f"expected '{cmd}' in help output, got:\n{result.stdout}"
        )


def test_help_does_not_omit_legacy_flags():
    """Sanity: --version must still report the program's version."""
    result = subprocess.run(
        [sys.executable, "-m", "eetool.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_each_command_module_imports_clean():
    """Import every command module to surface missing deps at startup."""
    from eetool.commands import (
        capture,
        keil,
        pin2json,
        pin_extract,
        schmd_from_netlist,
        serial,
    )

    for module in (capture, keil, pin2json, pin_extract, schmd_from_netlist, serial):
        assert hasattr(module, "add_subparser")
        assert hasattr(module, "run")
        assert callable(module.add_subparser)
        assert callable(module.run)
