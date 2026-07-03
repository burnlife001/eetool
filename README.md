# ee-toolkit

Unified Python CLI for electronics/embedded workflows. Consolidates six
legacy Claude skills into a single `ee` entry point, plus a built-in
`ee doctor` diagnostics tool:

| Skill                  | Replaced by                |
|------------------------|----------------------------|
| `serial-monitor`       | `ee serial`                |
| `pin2json`             | `ee pin2json`              |
| `pdf-pin-extract`      | `ee pin`                   |
| `schmd-from-netlist`   | `ee schmd-from-netlist`    |
| `keil-batch-gen`       | `ee keil gen-*`            |
| `keil-init`            | `ee keil init`             |
| `atk-logic-capture`    | `ee capture`               |

> `hardware-diff-by-codes` (MCU register-comparison SOP) is **not** yet
> consolidated — use the original skill at `~/.claude/skills/__myskills/electro/hardware-diff-by-codes/`.

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

```
ee [--version]
   {serial, pin2json, pin, schmd-from-netlist, keil, capture, doctor}
```

| Command | Purpose |
|---|---|
| `ee serial`              | Cross-process-locked COM port tools                       |
| `ee pin2json`            | Convert KiCad symbol or JLC part to pin JSON              |
| `ee pin`                 | PDF pin-table extraction + Markdown verification          |
| `ee schmd-from-netlist`  | Build or infer schematic pinmap from a Protel netlist     |
| `ee keil`                | Keil MDK project init + PowerShell build/flash scripts    |
| `ee capture`             | ATK-Logic logic-analyzer wrapper (GUI subprocess)         |
| `ee doctor`              | Diagnose Python version, runtime deps, serial ports       |

### `ee serial` — COM port tools

```
ee serial {listen, send, list}
```

```bash
ee serial list                                    # enumerate all COM ports (CH340 marked)
ee serial listen --port COM7 --baud 115200        # tail serial traffic, Ctrl+C to stop
ee serial listen --port COM7 --hex --log out.txt  # hex mode + log to file
ee serial listen --port COM7 --timeout 30         # auto-disconnect after 30s idle
ee serial send k1 --port COM7                     # send "k1\r\n" to MCU, then listen
```

| Subcommand | Options |
|---|---|
| `listen`  | `--port`, `--baud` (default 115200), `--hex`, `--timeout`, `--log` |
| `send`    | `cmd` ∈ {`k1`, `k2`, `k3`, `k4`}, `--port`, `--baud` |
| `list`    | — |

### `ee pin2json` — KiCad / JLCPCB to pin JSON

```bash
ee pin2json C9405                                # JLCPCB part → stdout JSON
ee pin2json My_LM321.kicad_sym                   # local symbol file → stdout JSON
ee pin2json C9405 -o LM321.json                  # also write to file
ee pin2json C9405 | jq '.pins[] | {num:.number, name:.name}'
```

| Arg / Option | Meaning |
|---|---|
| `input` (positional) | JLCPCB part id (`Cxxxxx`) or path to `.kicad_sym` |
| `-o, --output PATH` | Optional JSON output file (stdout always printed) |

### `ee pin` — PDF pin-table extraction

```
ee pin {extract, extract-search, extract-verify}
```

```bash
ee pin extract-search datasheet.pdf                     # find pin/mux pages
ee pin extract datasheet.pdf --chip-name MM32F0140      # → JSON
ee pin extract datasheet.pdf --chip-name MM32F0140 --package LQFP48   # + Markdown
ee pin extract-verify MM32F0140.Pin.md --ports PA,PB,PC,PD --mux-cols 10
```

| Subcommand | Options |
|---|---|
| `extract`         | positional `pdf`, `--pin-pages`, `--mux-pages`, `--ports`, `--mux-cols`, `-o/--output`, `--chip-name`, `--flavor` (`lattice`\|`stream`), `--package` |
| `extract-search`  | positional `pdf` |
| `extract-verify`  | positional `markdown`, `--ports`, `--mux-cols` |

### `ee schmd-from-netlist` — Netlist to pin signal map

```
ee schmd-from-netlist {map, infer}
```

```bash
ee schmd-from-netlist map board.NET                              # auto-detect MCU
ee schmd-from-netlist map board.NET --designator U2 --package LQFP48
ee schmd-from-netlist infer board.NET --out U2_pin_infer.md      # 2-hop BFS topology
```

| Subcommand | Options |
|---|---|
| `map`   | positional `netlist`, `--designator`, `--package`, `--shared-docs`, `--source-dir`, `--out` |
| `infer` | positional `netlist`, `--designator`, `--package`, `--shared-docs`, `--out` |

### `ee keil` — Keil MDK project bootstrap

```
ee keil {init, gen-build, gen-flash, gen-build-flash}
```

```bash
ee keil init ./my-project                              # render all 3 .ps1 next to .uvprojx
ee keil gen-build --project ./my-project/proj.uvprojx  # only __build.ps1
ee keil gen-flash --project ./my-project/proj.uvprojx  # only __download.ps1
ee keil gen-build-flash --project ./my-project/proj.uvprojx   # only __build_and_download.ps1
```

| Subcommand | Options |
|---|---|
| `init`             | positional `dir` (default `.`) — must contain a `.uvprojx` |
| `gen-build`        | `--project PATH` (`.uvprojx`) |
| `gen-flash`        | `--project PATH` (`.uvprojx`) |
| `gen-build-flash`  | `--project PATH` (`.uvprojx`) |

### `ee capture` — ATK-Logic logic-analyzer wrapper

```
ee capture <subcommand> [args...]
```

Subcommands are forwarded verbatim to `ee_toolkit.capture.atk_cli`.
Allowed subcommands: `start`, `info`, `export`, `decode`, `list-decoders`,
`config`, `classify`, `pwm`, `preflight`.

```bash
ee capture start --ch 0,1,2,3 --duration 5s           # capture 4 channels, 5s @ GUI rate
ee capture info wave.atkdl                            # show metadata (rate, duration, channels)
ee capture export wave.atkdl --ch 0 --start 0 --end 2s # dump edges as JSON
ee capture classify wave.atkdl                        # auto-detect signal types per channel
ee capture pwm wave.atkdl --ch 1 --window 200ms       # PWM / breathing LED analyzer
ee capture decode wave.atkdl --decoder uart --rx 0 --option baudrate=115200
ee capture list-decoders --filter uart,i2c
ee capture config show                               # read set.ini channels/rate/threshold
ee capture preflight --fix                           # self-check + auto-repair
```

> Note: `ee capture <sub>` shells out to `python -m ee_toolkit.capture.atk_cli <sub>`.
> For full options of each subcommand, run `ee capture <sub> --help` or
> `python -m ee_toolkit.capture.atk_cli <sub> --help`.

### `ee doctor` — environment diagnostics

```bash
ee doctor               # Python version + required deps + serial ports; PASS/WARN/FAIL
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
