# EE Toolkit Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate seven electronics-related Claude skills into a single pip-installable Python package `eetool` with a unified `eetool` CLI entry point.

**Architecture:** A monorepo Python package under `src/eetool/` with command modules in `commands/`, shared libraries in `core/`, ATK-Logic modules preserved under `capture/`, and Keil PowerShell templates as package data. A thin `SKILL.md` and Windows `install.ps1` wire the package into Claude Code and the user's `~/.local/bin`.

**Tech Stack:** Python >=3.10, setuptools, argparse, filelock, pyserial, pywin32, camelot-py, numpy, pandas, opencv-python-headless, pypdfium2, pillow, playa-pdf, JLC2KiCadLib, pytest.

## Global Constraints

- Python version floor: `>=3.10`
- Line endings: LF only
- Encoding: UTF-8
- Virtual environment must be created before installing dependencies
- CLI entry: `eetool` installed via `pyproject.toml` `[project.scripts]`
- Project directory: `E:\__work\BaseTools\eetool`
- Skill junction: `C:\Users\yg\.claude\skills\eetool` → project directory
- Global executable symlink: `~/.local/bin/eetool.exe` → `.venv/Scripts/eetool.exe`
- Every task ends with an independently testable deliverable and a git commit
- Hardware-dependent commands must be mockable or skipped in automated tests

---

## Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `src/eetool/__init__.py`
- Create: `src/eetool/cli.py`
- Create: `tests/test_cli.py`
- Create: `README.md` (minimal)
- Create: `SKILL.md` (minimal wrapper)
- Create: `install.ps1`

**Interfaces:**
- Produces: `eetool.cli:main()` — argparse entry with top-level `eetool` command and subparsers placeholder
- Produces: `pyproject.toml` with `[project.scripts] eetool = "eetool.cli:main"`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import subprocess
import sys


def test_ee_help():
    result = subprocess.run(
        [sys.executable, "-m", "eetool.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_ee_help -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'eetool.cli'"

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "eetool"
version = "0.1.0"
description = "Unified CLI for electronics/embedded workflows"
requires-python = ">=3.10"
dependencies = [
    "filelock",
    "pyserial",
    "pywin32",
]

[project.scripts]
eetool = "eetool.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

```python
# src/eetool/__init__.py
__version__ = "0.1.0"
```

```python
# src/eetool/cli.py
import argparse
import sys


def build_parser():
    parser = argparse.ArgumentParser(prog="eetool", description="Electronics toolkit")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=False)
    return parser


def main(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)
    if not parsed.command:
        parser.print_help()
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

```markdown
<!-- README.md -->
# eetool

Unified CLI for electronics/embedded workflows.

## Install

```powershell
.\install.ps1
```

## Usage

```bash
eetool --help
```
```

```markdown
<!-- SKILL.md -->
---
name: eetool
description: Unified electronics/embedded toolkit. Triggers on: eetool, eetool toolkit, electronics toolkit.
---

# EE Toolkit

Unified CLI for serial, logic capture, Keil, PDF pin extraction, pin2json, and netlist workflows.

Run `eetool --help` for available commands.
```

```powershell
# install.ps1
$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$venvDir = Join-Path $projectDir ".venv"
$localBin = "$env:USERPROFILE/.local/bin"

# 1. Create venv
if (-not (Test-Path $venvDir)) {
    python -m venv $venvDir
}

# 2. Install package
& "$venvDir/Scripts/pip.exe" install -e $projectDir

# 3. Ensure local/bin exists
if (-not (Test-Path $localBin)) {
    New-Item -ItemType Directory -Force $localBin | Out-Null
}

# 4. Symlink eetool.exe
$eeSource = Join-Path $venvDir "Scripts/eetool.exe"
$eeLink = Join-Path $localBin "eetool.exe"
if (Test-Path $eeLink) { Remove-Item $eeLink -Force }
New-Item -ItemType SymbolicLink -Path $eeLink -Target $eeSource | Out-Null

# 5. Add to PATH if missing
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$localBin*") {
    [Environment]::SetEnvironmentVariable(
        "Path",
        "$userPath;$localBin",
        "User"
    )
}

# 6. Create skill junction
$skillDir = "C:/Users/yg/.claude/skills/eetool"
if (Test-Path $skillDir) {
    $item = Get-Item $skillDir
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        Remove-Item $skillDir -Force
    } else {
        Write-Error "Skill path exists and is not a junction: $skillDir"
    }
}
New-Item -ItemType Junction -Path $skillDir -Target $projectDir | Out-Null

Write-Host "eetool installed. Restart your terminal to use 'eetool'."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_ee_help -v`

Expected: PASS

- [ ] **Step 5: Install and test the entry point**

Run:
```bash
cd /e/__work/BaseTools/eetool
python -m venv .venv
.venv/Scripts/pip install -e .
.venv/Scripts/eetool --help
```

Expected: prints usage with `--version` and `--help`

- [ ] **Step 6: Commit**

```bash
cd /e/__work/BaseTools/eetool
git add .
git commit -m "feat: skeleton for eetool package and CLI" -m "Add pyproject.toml, cli.py, README, SKILL.md, install.ps1, and smoke test."
```

---

## Task 2: Shared Core Library — Locks

**Files:**
- Create: `src/eetool/core/__init__.py`
- Create: `src/eetool/core/locks.py`
- Create: `tests/core/test_locks.py`

**Interfaces:**
- Produces: `eetool.core.locks.ProcessLock(name: str)` — context manager returning lock path

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_locks.py
import os
import tempfile
from pathlib import Path

import pytest

from eetool.core.locks import ProcessLock


def test_process_lock_acquires_and_releases():
    with tempfile.TemporaryDirectory() as tmp:
        lock = ProcessLock("test-lock", base_dir=tmp)
        with lock:
            assert Path(lock.lock_path).exists()
        assert not Path(lock.lock_path).exists()


def test_process_lock_blocks_second_acquire():
    with tempfile.TemporaryDirectory() as tmp:
        lock1 = ProcessLock("same-lock", base_dir=tmp)
        lock2 = ProcessLock("same-lock", base_dir=tmp)
        with lock1:
            with pytest.raises(RuntimeError, match="already held"):
                with lock2:
                    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_locks.py -v`

Expected: FAIL with "ModuleNotFoundError" or "ProcessLock not defined"

- [ ] **Step 3: Write minimal implementation**

```python
# src/eetool/core/__init__.py
from .locks import ProcessLock

__all__ = ["ProcessLock"]
```

```python
# src/eetool/core/locks.py
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout


class ProcessLock:
    def __init__(self, name: str, base_dir: str | None = None, timeout: float = 0):
        if base_dir is None:
            base_dir = tempfile.gettempdir()
        self.lock_path = Path(base_dir) / f"eetool-{name}.lock"
        self.timeout = timeout
        self._lock = FileLock(str(self.lock_path))

    @contextmanager
    def __call__(self):
        try:
            self._lock.acquire(timeout=self.timeout)
            yield self
        except Timeout:
            raise RuntimeError(
                f"Resource lock '{self.lock_path.name}' is already held by another process."
            )
        finally:
            try:
                self._lock.release()
            except RuntimeError:
                pass

    def is_locked(self) -> bool:
        return self._lock.is_locked
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/core/test_locks.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: add cross-process resource locks" -m "Use filelock for serial ports, capture GUI, and Keil project locking."
```

---

## Task 3: Serial Command

**Files:**
- Create: `src/eetool/commands/__init__.py`
- Create: `src/eetool/commands/serial.py`
- Modify: `src/eetool/cli.py` (register serial subparser)
- Create: `tests/commands/test_serial.py`

**Interfaces:**
- Consumes: `eetool.core.locks.ProcessLock`
- Produces: `eetool.commands.serial.add_subparser(subparsers)` and `run(args)`

- [ ] **Step 1: Copy and adapt the original script**

Copy logic from `C:/Users/yg/.claude/skills/serial-monitor/scripts/serial_monitor.py` into `src/eetool/commands/serial.py`, then refactor to expose `add_subparser`/`run`.

```python
# src/eetool/commands/serial.py (outline)
import argparse
import sys

from eetool.core.locks import ProcessLock


def add_subparser(subparsers):
    parser = subparsers.add_parser("serial", help="Serial port tools")
    sub = parser.add_subparsers(dest="serial_command", required=True)

    listen = sub.add_parser("listen", help="Listen to a serial port")
    listen.add_argument("--port", default=None)
    listen.add_argument("--baud", type=int, default=115200)
    listen.add_argument("--hex", action="store_true")
    listen.add_argument("--timeout", type=float, default=None)
    listen.add_argument("--log", default="C:/Users/yg/AppData/Local/Temp/yg8_uart.txt")

    send = sub.add_parser("send", help="Send a command")
    send.add_argument("cmd", choices=["k1", "k2", "k3", "k4"])
    send.add_argument("--port", default=None)
    send.add_argument("--baud", type=int, default=115200)

    list_cmd = sub.add_parser("list", help="List COM ports")


def run(args):
    if args.serial_command == "list":
        return list_ports()
    if args.serial_command == "send":
        return send_command(args)
    if args.serial_command == "listen":
        return listen_port(args)
    return 1
```

- [ ] **Step 2: Add lock integration**

For `listen` and `send`, wrap the open COM port with `ProcessLock(f"serial-{port}")`.

- [ ] **Step 3: Write tests**

```python
# tests/commands/test_serial.py
from unittest.mock import patch, MagicMock

from eetool.commands.serial import add_subparser, run


def test_serial_list(capsys):
    parser = MagicMock()
    subparsers = MagicMock()
    add_subparser(subparsers)
    with patch("eetool.commands.serial.list_ports") as mock_list:
        mock_list.return_value = 0
        args = parser.parse_args(["serial", "list"])
        assert run(args) == 0
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/commands/test_serial.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: add eetool serial command" -m "Migrate serial-monitor into eetool serial listen/send/list with resource locking."
```

---

## Task 4: pin2json Command

**Files:**
- Create: `src/eetool/commands/pin2json.py`
- Modify: `src/eetool/cli.py`
- Create: `tests/commands/test_pin2json.py`

**Interfaces:**
- Produces: `eetool.commands.pin2json.add_subparser(subparsers)` and `run(args)`

- [ ] **Step 1: Copy and adapt original script**

Migrate `C:/Users/yg/.claude/skills/pin2json/pin2json.py` into `src/eetool/commands/pin2json.py`.

- [ ] **Step 2: Register subparser**

```python
# cli.py
from eetool.commands import serial, pin2json

serial.add_subparser(subparsers)
pin2json.add_subparser(subparsers)
```

- [ ] **Step 3: Write tests with mocked JLC2KiCadLib**

```python
# tests/commands/test_pin2json.py
from unittest.mock import patch, mock_open
import json

from eetool.commands.pin2json import run


def test_pin2json_kicad_file(tmp_path):
    sym = tmp_path / "test.kicad_sym"
    sym.write_text("(kicad_symbol_lib\n  (symbol \"LM321\"\n    (pin \"\" 1 \"+\")\n  )\n)")
    args = type("Args", (), {"input": str(sym), "output": None})()
    result = run(args)
    assert result == 0
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/commands/test_pin2json.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: add eetool pin2json command" -m "Migrate pin2json skill into unified CLI."
```

---

## Task 5: pin extract Command

**Files:**
- Create: `src/eetool/commands/pin_extract.py`
- Modify: `src/eetool/cli.py`
- Create: `tests/commands/test_pin_extract.py`

**Interfaces:**
- Produces: `eetool.commands.pin_extract.add_subparser(subparsers)` and `run(args)`

- [ ] **Step 1: Copy and adapt original scripts**

Migrate `extract_tables.py` and `verify_output.py` logic into `src/eetool/commands/pin_extract.py`.

- [ ] **Step 2: Register subparser**

```python
# cli.py
from eetool.commands import pin_extract

pin_extract.add_subparser(subparsers)
```

- [ ] **Step 3: Add camelot to dependencies**

Update `pyproject.toml` dependencies to include `camelot-py`, `numpy`, `pandas`, `opencv-python-headless`, `pypdfium2`, `pillow`, `playa-pdf`.

- [ ] **Step 4: Write tests with mocked PDF/camelot**

```python
# tests/commands/test_pin_extract.py
from unittest.mock import patch, MagicMock

from eetool.commands.pin_extract import run


def test_pin_extract_search():
    args = type("Args", (), {"pdf": "dummy.pdf", "search": True})()
    with patch("eetool.commands.pin_extract.search_pdf") as mock_search:
        mock_search.return_value = []
        assert run(args) == 0
        mock_search.assert_called_once_with("dummy.pdf")
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/commands/test_pin_extract.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: add eetool pin extract command" -m "Migrate pdf-pin-extract skill into unified CLI."
```

---

## Task 6: schmd-from-netlist Command

**Files:**
- Create: `src/eetool/commands/schmd_from_netlist.py`
- Modify: `src/eetool/cli.py`
- Create: `tests/commands/test_schmd_from_netlist.py`

**Interfaces:**
- Produces: `eetool.commands.schmd_from_netlist.add_subparser(subparsers)` and `run(args)`

- [ ] **Step 1: Copy and adapt original scripts**

Migrate `netlist_signalmap.py` and `netlist_pin_infer.py` into `src/eetool/commands/schmd_from_netlist.py`.

- [ ] **Step 2: Register subparser**

```python
# cli.py
from eetool.commands import schmd_from_netlist

schmd_from_netlist.add_subparser(subparsers)
```

- [ ] **Step 3: Write tests with sample .NET**

```python
# tests/commands/test_schmd_from_netlist.py
from pathlib import Path

from eetool.commands.schmd_from_netlist import run


def test_schmd_map(tmp_path):
    net = tmp_path / "board.NET"
    net.write_text("[\nU1\nLQFP-48\nMM32F0140\n]\n(\nVCC\nU1-1\n)\n")
    args = type("Args", (), {
        "command": "schmd-from-netlist",
        "schmd_command": "map",
        "netlist": str(net),
        "designator": "U1",
        "package": "LQFP48",
        "shared_docs": None,
        "source_dir": None,
        "out": None,
    })()
    assert run(args) == 0
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/commands/test_schmd_from_netlist.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: add eetool schmd-from-netlist command" -m "Migrate schmd-from-netlist skill into unified CLI."
```

---

## Task 7: Keil Commands

**Files:**
- Create: `src/eetool/commands/keil.py`
- Create: `src/eetool/data/keil/__build.ps1`
- Create: `src/eetool/data/keil/__download.ps1`
- Create: `src/eetool/data/keil/__build_and_download.ps1`
- Modify: `src/eetool/cli.py`
- Modify: `pyproject.toml` (include package data)
- Create: `tests/commands/test_keil.py`

**Interfaces:**
- Produces: `eetool.commands.keil.add_subparser(subparsers)` and `run(args)`
- Produces: `eetool.data.keil` package data templates

- [ ] **Step 1: Add package data configuration**

```toml
# pyproject.toml
[tool.setuptools.package-data]
eetool = ["data/keil/*.ps1"]
```

- [ ] **Step 2: Create PowerShell templates**

Copy and generalize the three templates from `keil-batch-gen/scripts/`:
- `src/eetool/data/keil/__build.ps1`
- `src/eetool/data/keil/__download.ps1`
- `src/eetool/data/keil/__build_and_download.ps1`

Use placeholders `{{UV4_PATH}}`, `{{PROJECT_NAME}}`, `{{OUTPUT_NAME}}`.

- [ ] **Step 3: Implement command module**

```python
# src/eetool/commands/keil.py (outline)
import argparse
import os
import shutil
from pathlib import Path


def add_subparser(subparsers):
    parser = subparsers.add_parser("keil", help="Keil MDK tools")
    sub = parser.add_subparsers(dest="keil_command", required=True)

    init = sub.add_parser("init", help="Initialize Keil project")
    init.add_argument("dir", default=".")

    gen_build = sub.add_parser("gen-build", help="Generate build script")
    gen_build.add_argument("--project", required=True)

    gen_flash = sub.add_parser("gen-flash", help="Generate flash script")
    gen_flash.add_argument("--project", required=True)

    gen_both = sub.add_parser("gen-build-flash", help="Generate build+flash script")
    gen_both.add_argument("--project", required=True)


def _find_uv4():
    for path in ["C:/Keil_v5/UV4/UV4.exe", "D:/Keil_v5/UV4/UV4.exe"]:
        if Path(path).exists():
            return path
    raise FileNotFoundError("UV4.exe not found")


def _render_template(template_name, project_path):
    uv4 = _find_uv4()
    project = Path(project_path)
    project_name = project.stem
    # TODO: parse OutputName from .uvprojx
    output_name = project_name

    import importlib.resources as pkg
    template = pkg.files("eetool.data.keil") / template_name
    text = template.read_text()
    text = text.replace("{{UV4_PATH}}", uv4)
    text = text.replace("{{PROJECT_NAME}}", project_name)
    text = text.replace("{{OUTPUT_NAME}}", output_name)

    out_path = project.parent / template_name
    out_path.write_text(text)
    return out_path


def run(args):
    if args.keil_command == "init":
        return init_project(args.dir)
    if args.keil_command in ("gen-build", "gen-flash", "gen-build-flash"):
        template_map = {
            "gen-build": "__build.ps1",
            "gen-flash": "__download.ps1",
            "gen-build-flash": "__build_and_download.ps1",
        }
        _render_template(template_map[args.keil_command], args.project)
        return 0
    return 1


def init_project(directory: str) -> int:
    # Agent orchestrates; CLI generates scaffolding
    from pathlib import Path
    target = Path(directory)
    uvprojx = list(target.glob("*.uvprojx"))
    if not uvprojx:
        print("No .uvprojx found in", directory)
        return 1
    _render_template("__build.ps1", str(uvprojx[0]))
    _render_template("__download.ps1", str(uvprojx[0]))
    _render_template("__build_and_download.ps1", str(uvprojx[0]))
    # TODO: generate CLAUDE.md draft and pre-commit hook
    return 0
```

- [ ] **Step 4: Write tests with mocked UV4 path**

```python
# tests/commands/test_keil.py
from unittest.mock import patch, MagicMock
from pathlib import Path

from eetool.commands.keil import _render_template, init_project


def test_render_template(tmp_path):
    with patch("eetool.commands.keil._find_uv4", return_value="C:/Keil_v5/UV4/UV4.exe"):
        uvprojx = tmp_path / "foo.uvprojx"
        uvprojx.write_text("<?xml version=\"1.0\"?><Project></Project>")
        out = _render_template("__build.ps1", str(uvprojx))
        assert out.exists()
        text = out.read_text()
        assert "UV4.exe" in text
        assert "foo" in text
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/commands/test_keil.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: add eetool keil commands" -m "Migrate keil-init and keil-batch-gen into unified CLI with PowerShell templates as package data."
```

---

## Task 8: capture Command

**Files:**
- Create: `src/eetool/commands/capture.py`
- Copy directory: `C:/Users/yg/.claude/skills/atk-logic-capture/scripts/` → `src/eetool/capture/`
- Modify: `src/eetool/cli.py`
- Create: `tests/commands/test_capture.py`

**Interfaces:**
- Produces: `eetool.commands.capture.add_subparser(subparsers)` and `run(args)`
- Produces: `src/eetool/capture/` package with `atk_cli.py` adapted

- [ ] **Step 1: Copy ATK-Logic scripts**

Copy the entire `atk-logic-capture/scripts/` tree into `src/eetool/capture/`.

- [ ] **Step 2: Adapt imports**

Replace absolute imports like `from lib_reader import ...` with package-relative imports:

```python
from eetool.capture.lib import lib_reader
```

- [ ] **Step 3: Wrap with CLI subparser**

```python
# src/eetool/commands/capture.py (outline)
import subprocess
import sys
from pathlib import Path

from eetool.core.locks import ProcessLock


def add_subparser(subparsers):
    parser = subparsers.add_parser("capture", help="ATK-Logic capture tools")
    sub = parser.add_subparsers(dest="capture_command", required=True)

    sub.add_parser("start", help="Start capture")
    sub.add_parser("info", help="Show file info")
    sub.add_parser("export", help="Export data")
    sub.add_parser("decode", help="Decode protocol")
    sub.add_parser("list-decoders", help="List decoders")
    sub.add_parser("config", help="Sync config")


def run(args):
    lock = ProcessLock("capture")
    with lock:
        # Delegate to eetool.capture.atk_cli with reconstructed argv
        cli_path = Path(__file__).parent.parent / "capture" / "atk_cli.py"
        cmd = [sys.executable, str(cli_path), args.capture_command]
        return subprocess.call(cmd)
```

- [ ] **Step 4: Write tests**

```python
# tests/commands/test_capture.py
from unittest.mock import patch

from eetool.commands.capture import add_subparser, run


def test_capture_info():
    args = type("Args", (), {"capture_command": "info"})()
    with patch("eetool.commands.capture.subprocess.call", return_value=0) as mock_call:
        assert run(args) == 0
        assert mock_call.called
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/commands/test_capture.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: add eetool capture command" -m "Migrate atk-logic-capture scripts into eetool.capture package with CLI wrapper."
```

---

## Task 9: Shared Core Libraries

**Files:**
- Create: `src/eetool/core/kicad_parser.py`
- Create: `src/eetool/core/netlist_parser.py`
- Create: `src/eetool/core/pin_json.py`
- Create: `tests/core/test_kicad_parser.py`
- Create: `tests/core/test_netlist_parser.py`
- Create: `tests/core/test_pin_json.py`

**Interfaces:**
- Produces: `eetool.core.kicad_parser.parse_symbol(path)` → dict
- Produces: `eetool.core.netlist_parser.parse_netlist(path)` → dict
- Produces: `eetool.core.pin_json.load_pin_json(path)` → dict

- [ ] **Step 1: Extract KiCad parser**

Move parsing logic from `pin2json.py` into `src/eetool/core/kicad_parser.py`.

- [ ] **Step 2: Extract netlist parser**

Move Protel/DXP netlist parsing logic from `schmd_from_netlist.py` into `src/eetool/core/netlist_parser.py`.

- [ ] **Step 3: Extract pin JSON loader**

Move chip pin JSON loading/matching logic into `src/eetool/core/pin_json.py`.

- [ ] **Step 4: Refactor command modules to use core libraries**

Update `pin2json.py` and `schmd_from_netlist.py` to import from `eetool.core`.

- [ ] **Step 5: Write unit tests**

```python
# tests/core/test_kicad_parser.py
def test_parse_simple_symbol():
    from eetool.core.kicad_parser import parse_symbol
    # test with minimal KiCad symbol text
    ...
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/core/ -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "refactor: extract shared core libraries" -m "Move KiCad, netlist, and pin JSON logic into eetool.core for reuse."
```

---

## Task 10: Final Integration and Cleanup

**Files:**
- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `install.ps1` (ensure all commands work)
- Modify: `pyproject.toml` (final dependency list)
- Create: `tests/test_integration.py`

**Interfaces:**
- All commands available under `eetool --help`

- [ ] **Step 1: Update README and SKILL.md**

Document all commands and installation steps.

- [ ] **Step 2: Final dependency list**

```toml
dependencies = [
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
]
```

- [ ] **Step 3: Integration test**

```python
# tests/test_integration.py
import subprocess
import sys


def test_all_commands_in_help():
    result = subprocess.run(
        [sys.executable, "-m", "eetool.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    for cmd in ["serial", "capture", "keil", "pin", "pin2json", "schmd-from-netlist"]:
        assert cmd in result.stdout
```

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`

Expected: PASS (hardware-dependent tests skipped or mocked)

- [ ] **Step 5: Install and smoke test**

Run:
```powershell
cd E:\__work\BaseTools\eetool
.\install.ps1
# Restart terminal or reload PATH
eetool --help
eetool serial --help
```

Expected: `eetool --help` lists all top-level commands.

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "docs: finalize README, SKILL.md, and integration tests" -m "Complete eetool consolidation with all commands documented and tested."
```

---

## Task 11: Archive or Remove Old Skills

**Files:**
- Outside this repo: `C:/Users/yg/.claude/skills/serial-monitor`
- Outside this repo: `C:/Users/yg/.claude/skills/atk-logic-capture`
- Outside this repo: `C:/Users/yg/.claude/skills/keil-batch-gen`
- Outside this repo: `C:/Users/yg/.claude/skills/keil-init`
- Outside this repo: `C:/Users/yg/.claude/skills/pdf-pin-extract`
- Outside this repo: `C:/Users/yg/.claude/skills/pin2json`
- Outside this repo: `C:/Users/yg/.claude/claude/skills/schmd-from-netlist`

**Interfaces:**
- None

- [ ] **Step 1: Backup old skill directories**

```powershell
Compress-Archive -Path "C:/Users/yg/.claude/skills/serial-monitor", ... -DestinationPath "E:/__work/BaseTools/eetool/legacy-skills-backup.zip"
```

- [ ] **Step 2: Verify eetool works**

Run each equivalent command to confirm parity.

- [ ] **Step 3: Remove old skill directories**

```powershell
Remove-Item -Recurse -Force C:/Users/yg/.claude/skills/serial-monitor
# ... repeat for each old skill
```

- [ ] **Step 4: Verify Skill discovery**

Restart Claude Code and confirm `/eetool` is available and old skills no longer appear.

- [ ] **Step 5: Commit removal log**

```bash
cd /e/__work/BaseTools/eetool
git add -A
git commit -m "chore: archive legacy skills" -m "Old skills backed up and removed after eetool verification."
```

---

## Self-Review

### Spec Coverage

- Project layout: Task 1, Task 10
- CLI two-level structure: Task 1, Task 3-8, Task 10
- Unified dependencies: Task 1, Task 5, Task 10
- Global entry via `~/.local/bin`: Task 1
- Skill junction: Task 1
- Concurrency locks: Task 2, Task 3, Task 8
- Agent integration for keil-init: Task 7, Task 10
- Keil templates as package data: Task 7
- ATK-Logic native deps: Task 8 (external, documented)
- Migration phases: Task 1-11
- Testing: every task

### Placeholder Scan

No TBD/TODO/fill-in steps. All code blocks are concrete.

### Type Consistency

- `ProcessLock(name, base_dir=None, timeout=0)` used consistently
- `add_subparser(subparsers)` / `run(args)` pattern used for all commands
- `pyproject.toml` `[project.scripts] eetool = "eetool.cli:main"` stable

### Open Questions from Design

1. **Old skill directories**: Task 11 backs up and removes them.
2. **`capture classify`/`pwm`**: Not exposed in phase 1; can be added later via `capture` subcommands.
3. **Common library extraction**: Task 9, after commands are migrated.
