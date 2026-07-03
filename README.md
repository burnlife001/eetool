# ee-toolkit

Unified Python CLI for electronics/embedded workflows. Consolidates seven
legacy Claude skills into a single `ee` entry point:

| Skill                  | Replaced by                |
|------------------------|----------------------------|
| `serial-monitor`       | `ee serial`                |
| `pin2json`             | `ee pin2json`              |
| `pdf-pin-extract`      | `ee pin`                   |
| `schmd-from-netlist`   | `ee schmd-from-netlist`    |
| `keil-batch-gen`       | `ee keil gen-*`            |
| `keil-init`            | `ee keil init`             |
| `atk-logic-capture`    | `ee capture`               |

## Requirements

- Python ≥ 3.10
- Windows (for Keil / ATK-Logic; commands are mockable on any OS)

## Install

```powershell
git clone <repo> ee-toolkit
cd ee-toolkit
.\install.ps1
```

`install.ps1` creates `.venv/`, installs the package in editable mode, links
`ee.exe` into `~/.local/bin/`, and creates a skill junction at
`C:/Users/yg/.claude/skills/ee-toolkit`.

## Usage

```bash
ee --help           # list commands
ee serial listen    # tail a serial port
ee pin2json LM321   # KiCad symbol or JLC part to pin JSON
ee pin extract      # extract pin tables from a PDF datasheet
ee schmd-from-netlist map --project ...   # build schematic from netlist
ee keil init        # generate __build.ps1/__download.ps1 for a Keil project
ee capture info x.atkdl   # inspect ATK-Logic capture file
```

## Commands

| Command                       | Purpose                                              |
|-------------------------------|------------------------------------------------------|
| `ee serial listen/send/list`  | Cross-process-locked COM port tools                  |
| `ee pin2json <file-or-Cxxxxx>`| Convert KiCad symbol or JLC part to pin JSON         |
| `ee pin extract*`             | PDF pin-table extraction + Markdown verification     |
| `ee schmd-from-netlist map|infer` | Build or infer schematic from netlist           |
| `ee keil init|gen-build|gen-flash|gen-build-flash` | Keil batch wrappers         |
| `ee capture <subcmd> [args]`  | ATK-Logic logic-analyzer wrapper (GUI subprocess)    |

## Development

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # editable + pytest
.venv/Scripts/pytest tests/ -v          # 64+ unit tests
```

## Architecture

```
src/ee_toolkit/
  cli.py                # top-level argparse + dispatch
  commands/             # one module per top-level command
  core/
    locks.py            # ProcessLock (filelock wrapper)
    kicad_parser.py     # .kicad_sym parsing (used by pin2json)
    netlist_parser.py   # Protel/DXP netlist parsing (used by schmd)
  capture/              # migrated atk-logic-capture scripts
  data/keil/            # PowerShell templates shipped as package data
```

Hardware-bound commands (`ee serial`, `ee capture`) acquire a
`ProcessLock` so concurrent invocations don't fight over the COM port /
GUI / USB device. Test suite uses mocks for hardware and is safe to run in
CI on any platform.
