# EE Toolkit Consolidation Design

## Status

Draft — awaiting implementation plan.

## Background

The following electronics/embedded-related Claude skills are currently independent directories under `C:\Users\yg\.claude\skills\`:

- `serial-monitor`
- `atk-logic-capture`
- `keil-batch-gen`
- `keil-init`
- `pdf-pin-extract`
- `pin2json`
- `schmd-from-netlist`

They form a de-facto hardware/embedded workflow, but they are:

1. Visually scattered.
2. Invoked inconsistently (`/skill`, direct `python` paths, PowerShell scripts).
3. Dependent on separate Python virtual environments.
4. Unable to share code (KiCad parser, netlist parser, pin JSON loader).

## Goals (Priority Order)

1. **Unified invocation** — one entry point for all commands.
2. **Unified dependencies** — single `.venv` / pip package.
3. **Tidy directory layout** — consolidate into one project.
4. **Code sharing** — extract common libraries.

## Decision

Consolidate into a single pip-installable Python package `ee-toolkit` with a CLI entry `ee`.

## Project Layout

### Repository Separation

- **Project directory (real code)**: `E:\__work\BaseTools\ee-toolkit`
- **Skill directory (junction)**: `C:\Users\yg\.claude\skills\ee-toolkit` → points to project directory

This keeps the skill discovery directory clean while allowing the project to live elsewhere.

### Directory Structure

```text
E:\__work\BaseTools\ee-toolkit
├── pyproject.toml
├── README.md
├── SKILL.md                    # Thin skill wrapper for /ee invocation
├── install.ps1                 # Windows setup: venv + symlink + PATH
├── docs/
│   └── design.md
├── src/
│   └── ee_toolkit/
│       ├── __init__.py
│       ├── cli.py              # argparse main entry
│       ├── core/
│       │   ├── __init__.py
│       │   ├── locks.py        # Cross-process resource locks
│       │   ├── kicad_parser.py # Shared KiCad symbol parser
│       │   ├── netlist_parser.py
│       │   └── pin_json.py
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── serial.py
│       │   ├── capture.py
│       │   ├── keil.py
│       │   ├── pin_extract.py
│       │   ├── pin2json.py
│       │   └── schmd_from_netlist.py
│       ├── capture/            # ATK-Logic migrated as-is
│       │   ├── __init__.py
│       │   ├── _bootstrap.py
│       │   ├── _config.py
│       │   ├── atk_cli.py
│       │   ├── lib/
│       │   ├── analyze/
│       │   └── capture/
│       └── data/
│           └── keil/
│               ├── __build.ps1
│               ├── __download.ps1
│               └── __build_and_download.ps1
```

## CLI Design

Two-level command structure: `ee <domain> <action>`.

| Command | Maps To |
|---------|---------|
| `ee serial listen` | serial-monitor default mode |
| `ee serial send <cmd>` | serial-monitor `--send` |
| `ee serial list` | serial-monitor `--list` |
| `ee capture start` | atk-logic-capture `capture` |
| `ee capture info` | atk-logic-capture `info` |
| `ee capture export` | atk-logic-capture `export` |
| `ee capture decode` | atk-logic-capture `decode` |
| `ee capture list-decoders` | atk-logic-capture `list-decoders` |
| `ee capture config` | atk-logic-capture `config` |
| `ee keil init <dir>` | keil-init |
| `ee keil gen-build` | keil-batch-gen build script |
| `ee keil gen-flash` | keil-batch-gen download script |
| `ee keil gen-build-flash` | keil-batch-gen build+download script |
| `ee pin extract` | pdf-pin-extract extract_tables.py |
| `ee pin extract-search` | pdf-pin-extract `--search` |
| `ee pin extract-verify` | pdf-pin-extract verify_output.py |
| `ee pin2json <part/file>` | pin2json |
| `ee schmd-from-netlist map` | schmd-from-netlist signalmap |
| `ee schmd-from-netlist infer` | schmd-from-netlist pin_infer |

Implementation: each `commands/*.py` exposes `add_subparser(subparsers)` and `run(args)`.

## Dependencies

```toml
[project]
name = "ee-toolkit"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
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
    "filelock",
]

[project.scripts]
ee = "ee_toolkit.cli:main"
```

## Installation

`install.ps1` performs the following:

1. Create `E:\__work\BaseTools\ee-toolkit\.venv`.
2. `pip install -e .`.
3. Detect `~/.local/bin`:
   - If absent, create it.
   - If present, use it.
4. Create symlink `~/.local/bin/ee.exe` → `.venv/Scripts/ee.exe`.
5. If `~/.local/bin` is not in user `PATH`, append it.
6. Create junction `C:\Users\yg\.claude\skills\ee-toolkit` → `E:\__work\BaseTools\ee-toolkit`.

## Concurrency Safety

Use `filelock` for cross-process resource locks.

| Resource | Lock Name | Behavior on Conflict |
|----------|-----------|----------------------|
| COM port `<N>` | `ee-serial-COM<N>.lock` | Refuse with clear PID message |
| ATK-Logic GUI | `ee-capture.lock` | Refuse; only one capture session at a time |
| Keil project `.uvprojx` | `ee-keil-<hash>.lock` | Queue or refuse |
| JLC2KiCadLib temp | `tempfile.mkdtemp(prefix="ee-pin2json-")` | Isolated per run |
| Output files | Timestamped default names or explicit `--output` | Avoid silent overwrite |

## Agent Integration

`keil-init` originally relies on agent-in-the-loop orchestration. This is preserved by keeping the orchestration in `SKILL.md` while moving execution into the CLI.

`ee-toolkit/SKILL.md` instructs Claude to:

1. Inspect the project structure.
2. Run `ee keil init <dir>` to generate scripts and CLAUDE.md draft.
3. Review and adjust restricted zones.
4. Run `ee keil gen-build` to verify.
5. Commit.

Future improvement: `ee keil-init` can output a JSON draft for agent review before applying.

## Special Cases

### Keil PowerShell Templates

Templates live as package data under `src/ee_toolkit/data/keil/`. The CLI reads them, substitutes placeholders (`{{UV4_PATH}}`, `{{PROJECT_NAME}}`, `{{OUTPUT_NAME}}`), and writes the resulting `.ps1` files next to the target `.uvprojx`.

### ATK-Logic Native Dependencies

The following remain external to the pip package:

- `D:/Programs/ATK-Logic/ATK-Logic.exe`
- Proxy DLL `Qt5Network.dll`
- Optional `libsigrokdecode-4.dll`

The CLI runs preflight checks and reports missing prerequisites with setup instructions.

## Migration Plan

| Phase | Scope | Risk |
|-------|-------|------|
| 1 | Skeleton: `pyproject.toml`, `cli.py`, `install.ps1`, junction | Low |
| 2 | `serial` commands | Low |
| 3 | `pin2json` command | Low |
| 4 | `pin extract` commands | Medium (camelot) |
| 5 | `schmd-from-netlist` commands | Medium |
| 6 | `keil` commands | Medium |
| 7 | `capture` commands | High (native deps) |
| 8 | Extract common libraries | Low-Medium |
| 9 | Remove or archive old skill directories | Low |

## Testing

Per-command smoke tests:

```bash
ee --help
ee serial list
ee serial listen --timeout 1
ee pin2json C9405
ee pin extract-search some.pdf
ee schmd-from-netlist map some.NET
ee keil gen-build --project foo.uvprojx
ee capture info some.atkdl
```

Hardware-dependent commands (`serial listen`, `capture start`) are skipped in automated CI and tested manually with real hardware.

## Open Questions

1. Should old skill directories be deleted or kept as stubs redirecting to `ee-toolkit`?
2. Should `ee capture classify` and `ee capture pwm` be exposed as user-facing commands in phase 1?
3. Should the common library extraction happen incrementally or in one dedicated phase?
