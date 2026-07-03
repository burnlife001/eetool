---
name: ee-toolkit
description: Unified electronics/embedded toolkit — serial, capture, Keil, PDF pin extraction, pin2json, schmd-from-netlist. Triggers on: ee-toolkit, ee toolkit, ee serial, ee capture, ee keil, ee pin, ee pin2json, ee schmd, electronics toolkit, 逻辑分析仪, 串口, Keil 工程.
---

# EE Toolkit

A single CLI consolidating seven legacy skills. All subcommands live under
`ee ...` after running `.\install.ps1`.

## Available subcommands

| Command | When to use |
|---------|-------------|
| `ee serial listen/send/list` | Read or write COM ports with cross-process locking |
| `ee pin2json <file-or-Cxxxxx>` | Convert KiCad symbol or JLC part to pin JSON |
| `ee pin extract*` | Extract + verify pin tables from datasheet PDFs |
| `ee schmd-from-netlist map/infer` | Build schematic pinmap / infer signal topology from a Protel netlist |
| `ee keil init / gen-build / gen-flash / gen-build-flash` | Generate batch PowerShell scripts for a Keil MDK project |
| `ee capture <subcmd> [args...]` | ATK-Logic logic-analyzer wrapper (delegates to atk_cli) |

Run `ee --help` for the authoritative list and subcommand options.

## Quick start

```bash
ee --help                                # list commands
ee serial list                           # enumerate COM ports
ee pin2json C521137                      # JLC part → pin JSON
ee pin extract datasheet.pdf --search    # find pin tables in a PDF
ee keil init C:/proj/my-app              # scaffold Keil build scripts
ee capture info wave.atkdl               # inspect an ATK-Logic capture
```

## Notes

- Hardware-dependent commands (serial, capture) acquire a `ProcessLock`
  so concurrent invocations serialize access to the device.
- The capture subcommand spawns `python -m ee_toolkit.capture.atk_cli`,
  which needs the ATK-Logic GUI at `D:/Programs/ATK-Logic` and the proxy
  DLL tree. Install those before first use.
- Keil commands emit `__build.ps1` / `__download.ps1` /
  `__build_and_download.ps1` next to the `.uvprojx` file from
  package-data templates.
