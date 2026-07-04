# eetool

Unified Python CLI for electronics/embedded workflows. Consolidates six
legacy Claude skills into a single `eetool` entry point, plus a built-in
`eetool doctor` diagnostics tool:

| Skill                  | Replaced by                |
|------------------------|----------------------------|
| `serial-monitor`       | `eetool serial`                |
| `pin2json`             | `eetool pin2json`              |
| `pdf-pin-extract`      | `eetool pin`                   |
| `schmd-from-netlist`   | `eetool schmd-from-netlist`    |
| `keil-batch-gen`       | `eetool keil gen-*`            |
| `keil-init`            | `eetool keil init`             |
| `atk-logic-capture`    | `eetool capture`               |

> `hardware-diff-by-codes` (MCU register-comparison SOP) is **not** yet
> consolidated — use the original skill at `~/.claude/skills/__myskills/electro/hardware-diff-by-codes/`.

## Requirements

- Python ≥ 3.10
- Windows (for Keil / ATK-Logic; commands are mockable on any OS)

## Install

```powershell
git clone <repo> eetool
cd eetool
.\install.ps1
```

`install.ps1` creates `.venv/`, installs the package in editable mode, links
`eetool.exe` into `~/.local/bin/`, and creates a skill junction at
`C:/Users/yg/.claude/skills/eetool`.

## Usage

```bash
eetool --help           # list commands
eetool serial listen    # tail a serial port
eetool pin2json LM321   # KiCad symbol or JLC part to pin JSON
eetool pin extract      # extract pin tables from a PDF datasheet
eetool schmd-from-netlist map --project ...   # build schematic from netlist
eetool keil init        # generate __build.ps1/__download.ps1 for a Keil project
eetool capture info x.atkdl   # inspect ATK-Logic capture file
```

## Commands

```
eetool [--version]
   {serial, pin2json, pin, schmd-from-netlist, keil, capture, doctor}
```

| Command | Purpose |
|---|---|
| `eetool serial`              | Cross-process-locked COM port tools                       |
| `eetool pin2json`            | Convert KiCad symbol or JLC part to pin JSON              |
| `eetool pin`                 | PDF pin-table extraction + Markdown verification          |
| `eetool schmd-from-netlist`  | Build or infer schematic pinmap from a Protel netlist     |
| `eetool keil`                | Keil MDK project init + PowerShell build/flash scripts    |
| `eetool capture`             | ATK-Logic logic-analyzer wrapper (GUI subprocess)         |
| `eetool doctor`              | Diagnose Python version, runtime deps, serial ports       |

### `eetool serial` — COM port tools

```
eetool serial {listen, send, list}
```

```bash
eetool serial list                                    # enumerate all COM ports (CH340 marked)
eetool serial listen --port COM7 --baud 115200        # tail serial traffic, Ctrl+C to stop
eetool serial listen --port COM7 --hex --log out.txt  # hex mode + log to file
eetool serial listen --port COM7 --timeout 30         # auto-disconnect after 30s idle
eetool serial send k1 --port COM7                     # send "k1\r\n" to MCU, then listen
```

| Subcommand | Options |
|---|---|
| `listen`  | `--port`, `--baud` (default 115200), `--hex`, `--timeout`, `--log` |
| `send`    | `cmd` ∈ {`k1`, `k2`, `k3`, `k4`}, `--port`, `--baud` |
| `list`    | — |

### `eetool pin2json` — KiCad / JLCPCB to pin JSON

```bash
eetool pin2json C9405                                # JLCPCB part → stdout JSON
eetool pin2json My_LM321.kicad_sym                   # local symbol file → stdout JSON
eetool pin2json C9405 -o LM321.json                  # also write to file
eetool pin2json C9405 | jq '.pins[] | {num:.number, name:.name}'
```

| Arg / Option | Meaning |
|---|---|
| `input` (positional) | JLCPCB part id (`Cxxxxx`) or path to `.kicad_sym` |
| `-o, --output PATH` | Optional JSON output file (stdout always printed) |

### `eetool pin` — PDF pin-table extraction

```
eetool pin {extract, extract-search, extract-verify}
```

```bash
eetool pin extract-search datasheet.pdf                     # find pin/mux pages
eetool pin extract datasheet.pdf --chip-name MM32F0140      # → JSON
eetool pin extract datasheet.pdf --chip-name MM32F0140 --package LQFP48   # + Markdown
eetool pin extract-verify MM32F0140.Pin.md --ports PA,PB,PC,PD --mux-cols 10
```

| Subcommand | Options |
|---|---|
| `extract`         | positional `pdf`, `--pin-pages`, `--mux-pages`, `--ports`, `--mux-cols`, `-o/--output`, `--chip-name`, `--flavor` (`lattice`\|`stream`), `--package` |
| `extract-search`  | positional `pdf` |
| `extract-verify`  | positional `markdown`, `--ports`, `--mux-cols` |

### `eetool schmd-from-netlist` — Netlist to pin signal map

```
eetool schmd-from-netlist {map, infer}
```

```bash
eetool schmd-from-netlist map board.NET                              # auto-detect MCU
eetool schmd-from-netlist map board.NET --designator U2 --package LQFP48
eetool schmd-from-netlist infer board.NET --out U2_pin_infer.md      # 2-hop BFS topology
```

| Subcommand | Options |
|---|---|
| `map`   | positional `netlist`, `--designator`, `--package`, `--shared-docs`, `--source-dir`, `--out` |
| `infer` | positional `netlist`, `--designator`, `--package`, `--shared-docs`, `--out` |

### `eetool keil` — Keil MDK project bootstrap

```
eetool keil {init, gen-build, gen-flash, gen-build-flash}
```

```bash
eetool keil init ./my-project                              # render all 3 .ps1 next to .uvprojx
eetool keil gen-build --project ./my-project/proj.uvprojx  # only __build.ps1
eetool keil gen-flash --project ./my-project/proj.uvprojx  # only __download.ps1
eetool keil gen-build-flash --project ./my-project/proj.uvprojx   # only __build_and_download.ps1
```

| Subcommand | Options |
|---|---|
| `init`             | positional `dir` (default `.`) — must contain a `.uvprojx` |
| `gen-build`        | `--project PATH` (`.uvprojx`) |
| `gen-flash`        | `--project PATH` (`.uvprojx`) |
| `gen-build-flash`  | `--project PATH` (`.uvprojx`) |

### `eetool capture` — ATK-Logic logic-analyzer wrapper

```
eetool capture <subcommand> [args...]
```

Subcommands are forwarded verbatim to `eetool.capture.atk_cli`.
Allowed subcommands: `start`, `info`, `export`, `decode`, `list-decoders`,
`config`, `classify`, `pwm`, `preflight`.

```bash
eetool capture start --ch 0,1,2,3 --duration 5s           # capture 4 channels, 5s @ GUI rate
eetool capture info wave.atkdl                            # show metadata (rate, duration, channels)
eetool capture export wave.atkdl --ch 0 --start 0 --end 2s # dump edges as JSON
eetool capture classify wave.atkdl                        # auto-detect signal types per channel
eetool capture pwm wave.atkdl --ch 1 --window 200ms       # PWM / breathing LED analyzer
eetool capture decode wave.atkdl --decoder uart --rx 0 --option baudrate=115200
eetool capture list-decoders --filter uart,i2c
eetool capture config show                               # read set.ini channels/rate/threshold
eetool capture preflight --fix                           # self-check + auto-repair
```

> Note: `eetool capture <sub>` shells out to `python -m eetool.capture.atk_cli <sub>`.
> For full options of each subcommand, run `eetool capture <sub> --help` or
> `python -m eetool.capture.atk_cli <sub> --help`.

### `eetool doctor` — environment diagnostics

```bash
eetool doctor               # Python version + required deps + serial ports; PASS/WARN/FAIL
```

| Output | Meaning |
|---|---|
| `PASS` | check OK |
| `WARN` | non-blocking issue (e.g. no serial ports) |
| `FAIL` | blocker (Python < 3.10 or missing required dep) — exit code 1 |

## Development

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # editable + pytest
.venv/Scripts/pytest tests/ -v          # 64+ unit tests
```

## Architecture

```
src/eetool/
  cli.py                # top-level argparse + dispatch
  commands/             # one module per top-level command
  core/
    locks.py            # ProcessLock (filelock wrapper)
    kicad_parser.py     # .kicad_sym parsing (used by pin2json)
    netlist_parser.py   # Protel/DXP netlist parsing (used by schmd)
  capture/              # migrated atk-logic-capture scripts
  data/keil/            # PowerShell templates shipped as package data
```

Hardware-bound commands (`eetool serial`, `eetool capture`) acquire a
`ProcessLock` so concurrent invocations don't fight over the COM port /
GUI / USB device. Test suite uses mocks for hardware and is safe to run in
CI on any platform.
