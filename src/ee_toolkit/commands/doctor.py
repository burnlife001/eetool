"""Diagnostic command — checks Python version, runtime deps, serial port availability."""

from __future__ import annotations

import argparse
import importlib.metadata
import sys
from dataclasses import dataclass
from typing import Callable

# Hardcoded dependency list; keep in sync with pyproject.toml [project.dependencies].
REQUIRED_DEPS: tuple[str, ...] = (
    "filelock",
    "pyserial",
    "pywin32",
    "camelot-py",
    "numpy",
    "pandas",
    "opencv-python-headless",
    "pypdfium2",
    "pillow",
    "playa-pdf",
    "JLC2KiCadLib",
)

PYTHON_MIN = (3, 10)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # "PASS" | "WARN" | "FAIL"
    detail: str
    fix: str = ""

    def render(self) -> str:
        suffix = f"  → fix: {self.fix}" if self.fix else ""
        return f"[{self.status:>4}]  {self.name:30s}  {self.detail}{suffix}"


def _check_python() -> CheckResult:
    current = sys.version_info
    if current >= PYTHON_MIN:
        return CheckResult(
            name="Python version",
            status="PASS",
            detail=f"{current.major}.{current.minor}.{current.micro} (>= {'.'.join(map(str, PYTHON_MIN))})",
        )
    return CheckResult(
        name="Python version",
        status="FAIL",
        detail=f"{current.major}.{current.minor}.{current.micro} (< {'.'.join(map(str, PYTHON_MIN))})",
        fix=f"install Python >= {'.'.join(map(str, PYTHON_MIN))} from https://python.org",
    )


def _check_dependencies() -> list[CheckResult]:
    results: list[CheckResult] = []
    for name in REQUIRED_DEPS:
        normalized = name.replace("-", "_").lower()
        try:
            version = importlib.metadata.version(name)
            results.append(CheckResult(name=f"dep: {name}", status="PASS", detail=f"v{version}"))
        except importlib.metadata.PackageNotFoundError:
            results.append(
                CheckResult(
                    name=f"dep: {name}",
                    status="FAIL",
                    detail="not installed",
                    fix=f"pip install {name}",
                )
            )
        except Exception as exc:  # malformed metadata, etc.
            results.append(
                CheckResult(
                    name=f"dep: {name}",
                    status="WARN",
                    detail=f"installed but unreadable ({type(exc).__name__})",
                    fix=f"try: pip install --force-reinstall {normalized}",
                )
            )
    return results


def _check_serial_ports(comports=None) -> list[CheckResult]:
    if comports is None:
        try:
            from serial.tools.list_ports import comports as _comports
        except ImportError:
            return [
                CheckResult(
                    name="serial ports",
                    status="FAIL",
                    detail="pyserial not importable",
                    fix="pip install pyserial",
                )
            ]
        comports = _comports
    ports = list(comports())
    if not ports:
        return [
            CheckResult(
                name="serial ports",
                status="WARN",
                detail="no serial devices detected",
                fix="check USB connection / driver install",
            )
        ]
    details = ", ".join(p.device for p in ports[:5])
    extra = f" (+{len(ports) - 5} more)" if len(ports) > 5 else ""
    return [CheckResult(name="serial ports", status="PASS", detail=f"{len(ports)} found: {details}{extra}")]


def collect_checks() -> list[CheckResult]:
    return [_check_python(), *_check_dependencies(), *_check_serial_ports()]


def render_report(results: list[CheckResult]) -> str:
    lines = [r.render() for r in results]
    fails = sum(1 for r in results if r.status == "FAIL")
    warns = sum(1 for r in results if r.status == "WARN")
    passes = sum(1 for r in results if r.status == "PASS")
    lines.append("")
    lines.append(f"summary: {passes} pass / {warns} warn / {fails} fail")
    return "\n".join(lines)


def exit_code(results: list[CheckResult]) -> int:
    return 1 if any(r.status == "FAIL" for r in results) else 0


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "doctor",
        help="diagnose environment (Python version, deps, serial ports)",
    )
    parser.set_defaults(_handler="doctor")


def run(parsed: argparse.Namespace) -> int:
    results = collect_checks()
    print(render_report(results))
    return exit_code(results)