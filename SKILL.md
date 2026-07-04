---
name: eetool
description: Unified electronics/embedded toolkit — serial, capture, Keil, PDF pin extraction, pin2json, schmd-from-netlist, hardware diff. Triggers on: eetool, eetool toolkit, eetool serial, eetool capture, eetool keil, eetool pin, eetool pin2json, eetool schmd, electronics toolkit, 逻辑分析仪, 串口, Keil 工程, 硬件对比.
---

# eetool

A single CLI consolidating nine legacy skills. All subcommands live under
`eetool ...` after running `.\install.ps1`.

This file is the **router**. Each subcommand's detailed reference lives in
its own `SKILL_<name>.md` next to this file — open the matching one when
you need parameters, troubleshooting tables, recipes, or schemas.

## Routing table

Pick the row that matches what the user wants to do, then read the linked
file. `@SKILL_<name>.md` is a relative reference to the file in this
directory.

| When you want to ... | Subcommand / context | Read |
|----------------------|----------------------|------|
| Read or write COM ports (with cross-process locking) | `eetool serial listen/send/list` | @SKILL_serial.md |
| Run the ATK-Logic logic-analyzer wrapper (start / preflight / pwm / info) | `eetool capture <subcmd> [args...]` | @SKILL_capture.md |
| Scaffold or generate scripts for a Keil MDK project | `eetool keil init / setup / gen-build / gen-flash / gen-build-flash` | @SKILL_keil.md |
| Extract + verify pin tables from a datasheet PDF | `eetool pin extract*` | @SKILL_pin-extract.md |
| Convert a KiCad symbol or LCSC part to a pin JSON | `eetool pin2json <file-or-Cxxxxx>` | @SKILL_pin2json.md |
| Build a schematic pinmap / infer signal topology from a Protel netlist | `eetool schmd-from-netlist map/infer` | @SKILL_schmd.md |
| Compare two MCU firmware projects for PCB identity (no CLI) | manual 8-step SOP | @SKILL_hardware-diff.md |
| Check Python version, dependencies, and serial ports | `eetool doctor` | `eetool doctor --help` (no skill file — self-documenting) |

> If you need to dig into a specific bug or known-issue inside a function,
> jump straight to that file — `SKILL_capture.md` for ATK-Logic quirks,
> `SKILL_keil.md` for restricted zones / scatter file warnings, etc.

## Quick start

```bash
eetool --help                                # list commands
eetool serial list                           # enumerate COM ports
eetool pin2json C521137                      # JLC part → pin JSON
eetool pin extract datasheet.pdf --search    # find pin tables in a PDF
eetool keil init C:/proj/my-app              # scaffold Keil build scripts
eetool capture info wave.atkdl               # inspect an ATK-Logic capture
eetool doctor                                # environment health check
```

Run `eetool --help` for the authoritative command list and subcommand options.

## Cross-cutting notes

These apply across multiple subcommands — read once, then defer to the
per-function file for command-level detail.

- **ProcessLock**: hardware-dependent commands (`serial`, `capture`)
  acquire a process-level lock so concurrent invocations serialize access
  to the device.
- **ATK-Logic dependency**: the `capture` subcommand spawns
  `python -m eetool.capture.atk_cli`, which needs the ATK-Logic GUI at
  `D:/Programs/ATK-Logic` and the proxy DLL tree. Install those before
  first use — see @SKILL_capture.md for the full bootstrap and binary
  dependencies.
- **Keil scaffolding**: `keil init / setup / gen-*` write
  `__build.ps1` / `__download.ps1` / `__build_and_download.ps1` next to
  the `.uvprojx`, sourcing templates from package data (`src/eetool/data/`).
- **Keil setup pipeline**: `eetool keil setup <dir>` runs the full
  8-step pipeline — build scripts + `.claude/CLAUDE.md` restricted zones
  + pre-commit hook + `settings.json` + install to `.git/hooks/pre-commit`.
  Pass `--framework FreeRTOS` (or other supported RTOS) to mark the RTOS
  directory as restricted-zone B.

## Skill files in this directory

```
SKILL.md               # this router (entry point)
SKILL_serial.md
SKILL_capture.md
SKILL_keil.md
SKILL_pin-extract.md
SKILL_pin2json.md
SKILL_schmd.md
SKILL_hardware-diff.md
```

Treat `SKILL.md` as the index: when a user asks for a specific eetool
feature, route to the matching file rather than re-deriving details here.
