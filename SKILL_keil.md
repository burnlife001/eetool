---
name: eetool-keil
description: Keil MDK project setup and batch-script generator. Triggers on: eetool keil, Keil 工程, uvprojx, __build.ps1, __download.ps1, restricted zones, pre-commit hook.
---

# eetool-keil

Deep dive for `eetool keil ...`. Read `SKILL.md` first for routing.

## Subcommands

| Subcommand | Purpose |
|------------|---------|
| `eetool keil init <dir>` | Parse `.uvprojx`, scaffold output name + build settings. |
| `eetool keil setup <dir>` | Full 8-step pipeline (init + restricted zones + pre-commit hook + settings). |
| `eetool keil gen-build <dir>` | Emit `__build.ps1` next to the `.uvprojx`. |
| `eetool keil gen-flash <dir>` | Emit `__download.ps1` next to the `.uvprojx`. |
| `eetool keil gen-build-flash <dir>` | Emit `__build_and_download.ps1`. |

## 8-step pipeline

`eetool keil setup <dir>` runs:

1. Parse `.uvprojx` (device, compiler, output name).
2. Detect vendor HAL directory.
3. Detect RTOS directory (optional).
4. Generate `.claude/CLAUDE.md` restricted zones.
5. Generate `.git/hooks/pre-commit`.
6. Write `.claude/settings.json`.
7. Install the hook.
8. Verify with `--dry-run`.

Use `--framework FreeRTOS` (or other supported RTOS) to mark an RTOS directory as zone B.

## Restricted zones

| Class | Meaning | Example glob |
|-------|---------|--------------|
| A | Do not modify | `Device/**`, `Drivers/CMSIS/**` |
| B | Modify with review | `Drivers/STM32F1xx_HAL_Driver/**` |

Class B directories (HAL drivers, RTOS kernel sources) can still be edited
when a task requires it, but require explicit human review before commit.

## Scatter file warning

Deleting the project `.sct` scatter file will break the generated
`__download.ps1` flash script. Regenerate via `eetool keil gen-flash` after
any scatter-file change.

## Build result detection

The generated build script scans the project directory for `*.axf`;
presence of a newer `.axf` indicates a successful build.

## Where scripts land

All generated `__build.ps1` / `__download.ps1` / `__build_and_download.ps1`
files are written **next to the `.uvprojx`** — never inside the build output
tree. Templates come from package data (`src/eetool/data/`).
