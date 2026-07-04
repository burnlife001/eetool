"""Tests for `eetool doctor` — all hardware-dependent calls are mocked."""

from __future__ import annotations

import sys
from typing import NamedTuple
from unittest import mock

import pytest

from eetool.commands import doctor


class FakeVersion(NamedTuple):
    major: int
    minor: int
    micro: int = 0
    releaselevel: str = "final"
    serial: int = 0


@pytest.fixture
def fake_metadata():
    pkgs = {name: "1.0.0" for name in doctor.REQUIRED_DEPS}
    with mock.patch.object(doctor.importlib.metadata, "version", side_effect=lambda n: pkgs[n]):
        yield pkgs


def test_check_python_pass(monkeypatch):
    monkeypatch.setattr(doctor.sys, "version_info", FakeVersion(3, 11))
    r = doctor._check_python()
    assert r.status == "PASS"


def test_check_python_fail(monkeypatch):
    monkeypatch.setattr(doctor.sys, "version_info", FakeVersion(3, 9))
    r = doctor._check_python()
    assert r.status == "FAIL"
    assert "3.10" in r.fix


def test_check_dependencies_all_pass(fake_metadata):
    results = doctor._check_dependencies()
    assert all(r.status == "PASS" for r in results)
    assert len(results) == len(doctor.REQUIRED_DEPS)


def test_check_dependencies_missing():
    def raise_not_found(name):
        raise doctor.importlib.metadata.PackageNotFoundError(name)

    with mock.patch.object(doctor.importlib.metadata, "version", side_effect=raise_not_found):
        results = doctor._check_dependencies()
    assert all(r.status == "FAIL" for r in results)
    assert all("pip install" in r.fix for r in results)


class FakePort:
    def __init__(self, device):
        self.device = device


def test_check_serial_ports_none():
    comports = lambda: []  # noqa: E731
    results = doctor._check_serial_ports(comports=comports)
    assert results[0].status == "WARN"


def test_check_serial_ports_some():
    comports = lambda: [FakePort("COM7"), FakePort("COM8"), FakePort("COM9")]  # noqa: E731
    results = doctor._check_serial_ports(comports=comports)
    assert results[0].status == "PASS"
    assert "3 found" in results[0].detail


def test_check_serial_ports_pyserial_missing(monkeypatch):
    """When pyserial is not installed, return FAIL with fix hint."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "serial.tools.list_ports" or name.startswith("serial"):
            raise ImportError("pyserial not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    results = doctor._check_serial_ports()
    assert results[0].status == "FAIL"
    assert "pip install pyserial" in results[0].fix


def test_exit_code_zero_when_no_fail():
    results = [doctor.CheckResult("x", "PASS", ""), doctor.CheckResult("y", "WARN", "")]
    assert doctor.exit_code(results) == 0


def test_exit_code_nonzero_on_fail():
    results = [doctor.CheckResult("x", "PASS", ""), doctor.CheckResult("y", "FAIL", "")]
    assert doctor.exit_code(results) == 1


def test_collect_checks_aggregates():
    results = doctor.collect_checks()
    assert any(r.name == "Python version" for r in results)
    assert any(r.name.startswith("dep:") for r in results)
    assert any(r.name == "serial ports" for r in results)