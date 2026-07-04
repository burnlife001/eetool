---
name: eetool
description: Unified electronics/embedded toolkit — serial, capture, Keil, PDF pin extraction, pin2json, schmd-from-netlist, hardware diff. Triggers on: eetool, eetool toolkit, eetool serial, eetool capture, eetool keil, eetool pin, eetool pin2json, eetool schmd, electronics toolkit, 逻辑分析仪, 串口, Keil 工程, 硬件对比.
---

# eetool

A single CLI consolidating eight legacy skills. All subcommands live under
`eetool ...` after running `.\install.ps1`.

## Available subcommands

| Command | When to use |
|---------|-------------|
| `eetool serial listen/send/list` | Read or write COM ports with cross-process locking |
| `eetool pin2json <file-or-Cxxxxx>` | Convert KiCad symbol or JLC part to pin JSON |
| `eetool pin extract*` | Extract + verify pin tables from datasheet PDFs |
| `eetool schmd-from-netlist map/infer` | Build schematic pinmap / infer signal topology from a Protel netlist |
| `eetool keil init / setup / gen-build / gen-flash / gen-build-flash` | Generate batch PowerShell scripts and project scaffolding for a Keil MDK project |
| `eetool capture <subcmd> [args...]` | ATK-Logic logic-analyzer wrapper (delegates to atk_cli) |
| `eetool doctor` | Check Python version, dependencies, and serial ports |
| `eetool hardware-diff` *(no CLI; see SOP below)* | Compare two MCU firmware projects to determine whether they target the same PCB |

Run `eetool --help` for the authoritative list and subcommand options.

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

## Notes

- Hardware-dependent commands (serial, capture) acquire a `ProcessLock`
  so concurrent invocations serialize access to the device.
- The capture subcommand spawns `python -m eetool.capture.atk_cli`,
  which needs the ATK-Logic GUI at `D:/Programs/ATK-Logic` and the proxy
  DLL tree. Install those before first use.
- Keil commands emit `__build.ps1` / `__download.ps1` /
  `__build_and_download.ps1` next to the `.uvprojx` file from
  package-data templates.
- `eetool keil setup <dir>` runs the full 8-step keil-init pipeline: build
  scripts + `.claude/CLAUDE.md` restricted zones + pre-commit hook +
  `settings.json` + install to `.git/hooks/pre-commit`. Use
  `--framework FreeRTOS` to mark an RTOS as restricted-zone B.

---

# Hardware Diff SOP

> Original skill: `hardware-diff-by-codes` (in `~/.claude/skills/__myskills/electro/`).
> Not implemented as a CLI — it is an 8-step manual analysis procedure.
> Run each step in order; do not skip.

## Principle

**Same PCB → same GPIO register final values (pin + mode + AF selection + ODR) across all peripheral init functions.**

A firmware difference in function logic, timing parameters, or optional driver code does NOT mean a hardware difference. Only pin assignment changes (different GPIO port/pin), direction changes (input↔output), AF number changes (different peripheral wired), or additional peripheral bus initialization indicate PCB changes.

## Standard Operating Procedure

Execute these steps in strict order. Do not skip. Do not classify prematurely.

---

### Step 0 — Determine MCU family and register model

Before any register analysis, identify the MCU family from project headers, startup files, or linker scripts (e.g. `stm32f1xx.h` → F1, `stm32f4xx.h` → F4, `mm32xxxx.h` → MM32).

- **F1 / MM32 (CRL/CRH model)**: use Steps 1–8 as written below.
- **F0/F4/L4/G4 (MODER/OTYPER/OSPEEDR/PUPDR model)**: same logical procedure, but decode `MODER[1:0]` (00=input, 01=output, 10=AF, 11=analog), `OTYPER` (0=PP, 1=OD), `OSPEEDR`, `PUPDR` (00=none, 01=pull-up, 10=pull-down), `AFR[0:1]` (4-bit per pin, AF0–AF15) instead of CRL/CRH nibbles. Apply this mapping in Step 4 — the decoding tables below are F1-specific; for F4-family use these MODER rules instead.
- **Other / unrecognized family**: flag "unsupported MCU family" and require manual analysis.

**If the two projects use different MCU families → different hardware. Stop here.**

### Step 1 — Confirm MCU and clock

Check both projects use the same MCU model and same system clock source/frequency.

- Scan `main()` for `SystemReInit()` or `SYSCLK_Init()` calls
- Check `RCC->` register writes
- **Different MCU = different hardware. Stop here.**

### Step 2 — Collect all GPIO-affecting code

From `main()` downward, collect every function that touches these registers across **all source files**:

| Register class | Example writes | What it controls |
|---------------|----------------|------------------|
| RCC AHBENR/APB1ENR/APB2ENR | `RCC->AHBENR \|= RCC_AHBENR_GPIOA` | Peripheral bus clock enable |
| GPIO CRL / CRH | `GPIOA->CRL &= ~0xF0; \|= 0x50` | Pin mode + direction |
| GPIO AFRL / AFRH | `GPIOA->AFRL \|= 0x02` | Alternate function number |
| GPIO ODR / ODR_F / BSRR / BRR | `GPIOA->BSRR \|= pin` | Output data / pull direction |
| GPIO IDR / IDR_F | `if (GPIOA->IDR_F.P0)` | Input reads (evidence of pin usage) |

**Collection scope:**
- Follow `#include` chains — init functions may live in different directories
- Include HAL library calls (`GPIO_Init()`) — decode their net effect on registers
- Include direct register writes in `.c` files, not just headers
- **`#ifdef` awareness**: when a GPIO/RCC write is guarded by `#ifdef X` / `#if defined(X)`, record macro X. Compare the two projects' build defines (`-D` flags, `main.h`, `board.h`). If X evaluates differently, simulate only the **compiled** branch for each project (not both branches), then compare those final states. If the same `#ifdef` evaluates identically in both, proceed normally.

### Step 3 — Simulate final register state

**Critical: Compute the final value after all init code executes in order.** Do not compare individual `|=` statements — they accumulate.

For each GPIO register in each project, simulate from reset state:

```
Start state:
  CRL / CRH  → 0x4444_4444  (all pins = floating input)
  AFRL / AFRH → 0x0000_0000  (all AF = 0)
  ODR        → 0x0000_0000  (all bits = 0)

For each statement in execution order:
  reg |= val   →  final |= val
  reg &= ~val  →  final &= ~val
  reg = val    →  final = val   (overwrites all 16 pins)
  reg->ODR_F.Px = v  →  set/clear bit x in ODR final
  reg->BSRR |= pin   →  set corresponding ODR bit
  reg->BRR  |= pin   →  clear corresponding ODR bit
```

**Only compare final values between projects.** Intermediate step differences are irrelevant to hardware.

#### Filtering: `= 0` whole-register noise

Some projects start with `GPIOx->CRL = 0` (all pins → analog input) as defensive init. If:
1. The `= 0` is the **first** write to that register, AND
2. No subsequent `|=` / `&= ~` in any init function touches a given nibble, AND
3. No functional code reads/writes that pin (check IDR/ODR usage),

...then that nibble is **"unused"**. If the other project leaves the same nibble at reset (`0x4`), the difference is **ignored** — not a hardware diff.

#### Filtering: AF register only matters if pin is AF mode

Only apply AFRL/AFRH comparison to pins where the CRL/CRH nibble has CNF[3:2] = `1x` (AF mode). For non-AF pins, the AF register value is don't-care.

### Step 4 — Decode nibbles and AF numbers

#### 4a. CRL / CRH nibble → pin mapping

```
Register  [31:28] [27:24] [23:20] [19:16] [15:12] [11:8]  [7:4]  [3:0]
CRL         PA7     PA6     PA5     PA4     PA3     PA2     PA1    PA0
CRH        PA15    PA14    PA13    PA12    PA11    PA10     PA9    PA8
```

Replace PA with PB/PC/PD for other ports.

#### 4b. CR nibble → CNF + MODE decoding

```
Nibble = 0b CNF1 CNF0 MODE1 MODE0

MODE ([1:0]):
  00 = Input
  01 = Output 10MHz
  10 = Output 2MHz
  11 = Output 50MHz

CNF ([3:2]) — Input mode (MODE=00):
  00 = Analog
  01 = Floating
  10 = Pull-up / Pull-down  ← must check ODR bit
  11 = Reserved (invalid)

CNF ([3:2]) — Output/AF mode (MODE>00):
  00 = General Purpose Push-Pull
  01 = General Purpose Open-Drain
  10 = Alternate Function Push-Pull
  11 = Alternate Function Open-Drain
```

#### 4c. AFRL / AFRH nibble → pin mapping (same as CR)

```
AFRL  [31:28] [27:24] [23:20] [19:16] [15:12] [11:8]  [7:4]  [3:0]
        PA7     PA6     PA5     PA4     PA3     PA2     PA1    PA0
AFRH  [31:28] [27:24] [23:20] [19:16] [15:12] [11:8]  [7:4]  [3:0]
       PA15    PA14    PA13    PA12    PA11    PA10     PA9    PA8
```

AF nibble value = AF number (0–7 typically). A pin with CR nibble `0x9` (AF PP) + AF nibble `0x1` = UART1 TX; same CR nibble + AF nibble `0x2` = TIM1 CH1 → **different peripheral → different hardware**.

### Step 5 — Classify each pin difference

For each pin position (all ports, PA0..PD15), compare the final state tuple **(CR nibble, AF nibble, ODR bit)** between Project A and Project B.

```
Final state matches?
  ├── YES → SAME. Move to next pin.
  └── NO  → Classify:

  1. Is the nibble "unused" (reset/filtered =0 noise) in either project?
     └── YES → IGNORE. Not a real pin assignment.

  2. Is either nibble value Reserved (CNF=11, MODE=00)?
     └── YES → INVALID. Flag for manual review. Stop classifying this pin.

  3. MODE field: did direction change (Input=00 ↔ Output>00)?
     ├── YES → DIRECTION CHANGE.
     │         Pin function redefined (e.g. input key → output LED).
     │         Flag for MANUAL REVIEW. Do NOT auto-classify.
     └── NO  → Same direction. Continue.

  4. Both are input-mode (MODE=00):
     ├── Pull-up/down (CNF=10): compare ODR bit
     │   ├── ODR differs → MODE CHANGE, firmware (pull-up vs pull-down)
     │   └── ODR same → SAME
     ├── Analog→Floating, Floating→Analog → MODE CHANGE, firmware
     └── Analog→Pull-up, Floating→Pull-up → MODE CHANGE, firmware
         (all same-direction input-only changes)

  5. Both are output/AF-mode (MODE>00):
     ├── Pin number different → PIN CHANGE → hardware different
     ├── Pin same, MODE speed changed (10→50MHz) → MODE CHANGE, firmware
     ├── Pin same, CNF PP↔OD → MODE CHANGE, firmware
     ├── Pin same, GP↔AF → MODE CHANGE, firmware
     │   (e.g. PP out → AF PP = same pin, different function, not new hardware)
     ├── Pin same, CNF=AF PP in both, but AF nibble differs:
     │   └── AF NUMBER CHANGE → hardware different
     │       (trace connects the same pin to a different on-chip peripheral)
     └── Pin same, CNF=AF OD in both, but AF nibble differs:
         └── AF NUMBER CHANGE → hardware different
```

#### Decision summary table

| What differs | Classification | Reason |
|-------------|---------------|--------|
| Nothing | SAME | |
| Unused pin vs reset | IGNORE | Defensive `= 0` noise, pin never used |
| Reserved nibble 0x3/0x7/0xB | INVALID | Flag, do not classify |
| Different pin position | **HARDWARE DIFF** | PCB trace to different MCU pad |
| Different AF number (same AF-mode pin) | **HARDWARE DIFF** | Different on-chip peripheral wired |
| Direction In↔Out | **MANUAL REVIEW** | Function redefinition possible |
| Same pin, same direction, different CNF/MODE | Firmware | Drive tuning, speed, pull strategy |
| Same CNF=10 input, different ODR bit | Firmware | Pull-up vs pull-down choice |

### Step 6 — Check peripheral busses (RCC)

Compare RCC enable register final values:

```
RCC->AHBENR  — GPIO port clocks, DMA, etc.
RCC->APB1ENR — TIM2-7, I2C1-2, USART2-4, SPI2-3, etc.
RCC->APB2ENR — TIM1/14-17, ADC1, SPI1, USART1, etc.
```

- A bus bit enabled in only one project → lookup which peripheral it gates
- If that peripheral's GPIO pins are **also** only configured in that project → **hardware different**
- If pins are configured in both but bus only enabled in one → firmware didn't start the peripheral, same PCB

### Step 7 — Resolve peripheral ambiguities

For I2C/SPI device drivers (SW5001, BQ25890, etc.) that exist in one project but not the other:

| Evidence | Verdict |
|----------|---------|
| Bus pins configured as AF+I2C/SPI in both projects | Same PCB — chip pads exist, may or may not be soldered |
| Bus pins configured in one project, used for GPIO in the other | **Different PCB** — pads repurposed |
| Bus pins untouched (reset) in the other project | **Ambiguous** — could be unpopulated pads on same PCB |
| Bus enabled + chip init called in one, bus disabled in other | Firmware difference — chip soldering is the physical variable |

### Step 8 — Produce report

```markdown
## Hardware Comparison: [Project A] vs [Project B]

### Identity
- MCU: [model]
- Clock: [source] @ [freq]

### Pin-by-pin register comparison

| Port.Pin | CR A | CR B | AF A | AF B | ODR A | ODR B | Classification |
|----------|------|------|------|------|-------|-------|----------------|
| PA0      | 0x4  | 0x4  | 0x0  | 0x0  | 0     | 0     | SAME (unused)  |
| PA1      | 0x1  | 0x5  | 0x0  | 0x0  | 0     | 0     | MODE CHANGE (PP→OD) |
| ...      |      |      |      |      |       |       |                |

### Summary

**Hardware identical:**
- [count] pins — same pin, same mode, same AF, same ODR

**Hardware different:**
- [pin X]: PA3 in A vs PA4 in B — PCB trace moved
- [pin Y]: same PA8, AF1(UART1) in A vs AF2(TIM1) in B — different peripheral

**Firmware only (same PCB):**
- [count] pins — same pin, mode change only (PP→OD, speed, pull direction)

**Requires manual review:**
- [pin K]: direction change input→output
- [pin M]: invalid nibble 0xF

### Verdict
- [ ] Same PCB, different firmware
- [ ] Same PCB, optional chip not soldered in one variant
- [ ] Different PCB revision
- [ ] Requires manual review
```

## Key rules

1. **Simulate final register state; compare finals, not intermediates.** `|=` accumulates. A sequence of 3 writes to PA1 converges to one final nibble — that's what you compare.
2. **Never trust comments. Hex value is sole truth.** `// PA.4+PA.6` next to `|= 0x50` is wrong. Decode: `0x50` nibble [7:4] = PA1. Always.
3. **Same nibble position + same direction + mode change = firmware. Different nibble position = hardware. AF number change on AF pin = hardware.** Direction change (In↔Out) = manual review.
4. **`= 0` defensive init is noise.** Filter it: if no later code touches that pin, it's "unused", not a hardware difference.
5. **Track ODR through BSRR/BRR/ODR_F, not just direct ODR writes.**
6. **AF nibble matters only when CNF = AF mode.** For GP pins, ignore AF value.
7. **External chip driver ≠ chip soldered.** Same PCB may have unpopulated pads.
8. **When uncertain, classify as "ambiguous" or "manual review".** Do not force a conclusion.
9. **`#ifdef` guards determine what compiles.** See Step 2 collection scope — always simulate each project's compiled path, not the raw preprocessor-expanded source.

---

# ATK-Logic Capture (detailed reference)

## Capture workflow

- `eetool capture start` does **not** ask for confirmation by default.
- If `set.ini` must be changed or `--duration` exceeds 10 s, the CLI warns and may restart the GUI automatically.
- Preflight runs automatically on the first capture of a GUI session (DLL-persisted `g_preflight_ok`).
- The save flow uses the GUI Save-As picker for the first capture; subsequent captures save in-place.
- `isCtrlSPressed` is a DLL flag that tells the CLI the picker has already been handled once.

## Capture parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `--ch` | Comma-separated channel IDs | (use GUI current) | `--ch 0,1,2,3` |
| `--duration` | Capture duration | `3s` | `--duration 5s` |
| `--sample-rate-hz` | Sample rate in Hz | (use `set.ini`) | `--sample-rate-hz 24000000` |
| `--threshold` | Logic threshold voltage | (use `set.ini`) | `--threshold 1.5` |
| `--sync` | Force sync `set.ini` even if no params changed | false | `--sync` |
| `--rle` | Enable FPGA RLE compression | false | `--rle` |
| `--output` | Output filename only (saved to `DATA_DIR`) | auto timestamp | `--output out.atkdl` |

## TCP API reference

The proxy DLL exposes a TCP server on `127.0.0.1:9876`. Each command is a JSON line terminated with `\n`.

| Command | Request | Response |
|---------|---------|----------|
| `start_capture` | `{"cmd":"start","chs":[0,1],"duration_s":2,...}` | `{"status":"ok","save_prompt":"open","filename":"..."}` |
| `stop_capture` | `{"cmd":"stop"}` | `{"status":"ok"}` |
| `get_progress` | `{"cmd":"get_progress"}` | `{"status":"ok","progress":50}` |
| `is_capturing` | `{"cmd":"is_capturing"}` | `{"status":"ok","value":"0/1"}` |
| `export` | `{"cmd":"export","file":"...","chs":[0]}` | `{"status":"ok","data":{}}` |
| `decode` | `{"cmd":"decode","file":"...","decoder":"uart"}` | `{"status":"ok","data":{}}` |
| `get_info` | `{"cmd":"get_info","file":"..."}` | `{"status":"ok","info":{}}` |
| `ping` | `{"cmd":"ping"}` | `{"status":"ok"}` |

## Known issues and fixes

| # | Issue | Fix |
|---|-------|-----|
| 1 | GUI stuck at 1% | Gracefully close ATK-Logic, remove unsaved markers, retry. |
| 2 | Stale temp markers | `atk_preflight` cleans `APPDATA_ATK/temp/memory` before GUI start. |
| 3 | Memory markers trigger recovery dialog | Delete `APPDATA_ATK/temp/lock` and `memory/` dir. |
| 4 | `set.ini` permission denied | Run from an account with write access to `%APPDATA%/ALIENTEK`. |
| 5 | TCP connection refused | Verify proxy DLL deployed and GUI running. |
| 6 | Save picker not filled | Ensure `uiautomation` is installed and GUI is not minimized. |
| 7 | Wrong capture duration | Pass `--duration` explicitly; GUI reads `setTime` from `set.ini`. |
| 8 | Proxy DLL size mismatch | Rebuild with `proxy_dll/build.ps1` (MSVC). |

## Capture failure recovery

If capture freezes at 1%:
1. Close ATK-Logic (gracefully if possible).
2. Run `eetool capture preflight --fix` to clean markers and restart.
3. Retry with `--duration 2s` first.

## Path configuration

| File | Purpose |
|------|---------|
| `src/eetool/capture/config.ini` | Runtime config: `GUI_DIR`, `DATA_DIR` |
| `src/eetool/capture/_config.py` | Fallback paths and constants |
| `%APPDATA%/ALIENTEK/ATK-LogicView/set.ini` | GUI capture params (channels, sample rate, threshold, duration) |

## ATK-Logic shortcuts

| Key | Action |
|-----|--------|
| F1 | Start capture |
| F2 | Stop capture |
| Ctrl+S | Save capture / mark first-save done |

## PWM analysis output

`eetool capture pwm <file.atkdl> --ch N` reports:
- `frequency_hz`, `duty_cycle_%`, `period_ns`
- `high_ns`, `low_ns`, `pulse_count`
- Confidence warnings for noisy / irregular waveforms

## Script manifest

```
src/eetool/capture/
├── atk_cli.py              # Main capture CLI
├── capture/atk_preflight.py # Self-check + auto-fix
├── analyze/atk_classify.py  # Auto signal classifier
├── analyze/atk_pwm.py       # PWM / breathing LED analyzer
├── uia_save.py              # Save-As picker automation
├── lib/
│   ├── lib_reader.py        # .atkdl / .bin reader
│   ├── lib_proto.py         # Native decoders (uart, i2c, spi)
│   ├── lib_decoder.py       # libsigrokdecode bridge
│   └── lib_config_sync.py   # set.ini read/write
└── _bootstrap.py            # DLL search-path setup
```

## Binary dependencies

`_bootstrap.py` adds `src/eetool/capture/lib/bin` to the Windows DLL search path because Python 3.8+ requires explicit `os.add_dll_directory()` for side-by-side native DLLs.

Required native DLLs for protocol decoders:

```
lib_decoder.py
  → libsigrokdecode-4.dll
    → libglib-2.0-0.dll
      → libiconv-2.dll
      → libintl-8.dll
      → libpcre2-8-0.dll
    → libffi-8.dll
    → libirmp-0.dll
  → libstdc++-6.dll
  → libgcc_s_seh-1.dll
  → libwinpthread-1.dll
  → zlib1.dll
```

`libsigrokdecode` has no official Windows wheels, so the DLLs are bundled in `lib/bin/`.

---

# PDF pin extraction (`eetool pin extract*`)

## Dependencies

```bash
pip install camelot-py numpy pandas opencv-python-headless pypdfium2 pillow playa-pdf
```

If `import camelot` fails, reinstall with `pip install -e .` from the `camelot-py` source tree to restore the editable namespace package.

## 3-stage workflow

1. **Search** — `eetool pin extract-search datasheet.pdf` locates pin tables by keyword.
2. **Extract** — `eetool pin extract datasheet.pdf --flavor ...` parses tables.
3. **Clean** — `clean_cell_*` helpers normalize text, strip units, split multi-value cells.

## Keyword search table

| Table type | Chinese keywords | English keywords |
|------------|------------------|------------------|
| Pin Assignment | 引脚分配, 引脚定义 | Pin Assignment, Pin Definition |
| Multiplexing | 复用功能, 多路复用 | Alternate Functions, Multiplexing |

## Validation checklist and exit codes

| Check | Exit code |
|-------|-----------|
| Port column incomplete | 1 |
| MUX column incomplete | 2 |
| Cross-validation failed | 3 |
| Artifact check failed | 4 |
| Statistics check failed | 5 |

## JSON output schema

```json
{
  "pins": [
    {
      "number": "1",
      "name": "VDD",
      "type": "power",
      "port": "A",
      "mux": ["USART1_TX", "TIM2_CH1"]
    }
  ],
  "flavor": "lattice",
  "package": "TSSOP20"
}
```

## Vendor notes

| Vendor | Notes |
|--------|-------|
| MM32 | `MM32Fxxx` CRL/CRH register model |
| STM32 | F1 = CRL/CRH; F0/F4/L4/G4 = MODER/AFR |
| GD32 | Generally STM32-compatible pinouts |
| AT32 | Verify alternate-function mapping against reference manual |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No tables found | Wrong `--flavor` | Try `lattice`, `st`, or `mm32` |
| Empty cells | OCR / vector extraction issue | Use `--pages` to narrow, check PDF resolution |
| `camelot` import error | Namespace package broken | `pip install -e .` from camelot source |
| Exit code 1 | Port column missing | Review extracted markdown, add `--search` hints |

---

# Schematic from netlist (`eetool schmd-from-netlist`)

## 6-level naming priority

1. Net Label
2. Pin Name (source component)
3. Signal Hint (JSON alias in `__shared_docs/<signal>.json`)
4. Default Signal Name
5. Net ID
6. Fallback (`NC`)

## User warnings

- Ensure SCH and PCB are synchronized before running.
- Mark NC pins explicitly (`NC` net label or pin name).
- Do **not** attach multiple net labels to the same net.

## Netlist format

Protel/DXP bracket format:

```
[
  U1
  PA0 1 2 3 NC
]
[
  R1
  1 2
]
```

## Source alias hint rules

`__shared_docs/<signal>.json` files are matched by signal name substring; the first matching alias is used as the Level-3 hint.

## Limitations

1. Only Protel/DXP-style bracket netlists are supported.
2. Multi-sheet hierarchical designs may require manual review.
3. Bus notation (`DATA[0..7]`) is not expanded automatically.

---

# Keil project setup (`eetool keil setup`)

## 8-step pipeline

1. Parse `.uvprojx` (device, compiler, output name).
2. Detect vendor HAL directory.
3. Detect RTOS directory (optional).
4. Generate `.claude/CLAUDE.md` restricted zones.
5. Generate `.git/hooks/pre-commit`.
6. Write `.claude/settings.json`.
7. Install the hook.
8. Verify with `--dry-run`.

## Restricted zones

| Class | Meaning | Example glob |
|-------|---------|--------------|
| A | Do not modify | `Device/**`, `Drivers/CMSIS/**` |
| B | Modify with review | `Drivers/STM32F1xx_HAL_Driver/**` |

Use `--framework FreeRTOS` to mark an RTOS directory as zone B.

---

# Serial (`eetool serial`)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Port busy | Another process holds COM | Close other serial tools; `ProcessLock` serializes within eetool |
| Permission denied | Insufficient rights | Run terminal as user with device access |
| Garbled output | Baud/parity/stopbits mismatch | Match MCU config with `--baudrate --bytesize --parity --stopbits` |
| No data received | Timeout too short | Increase `--timeout` or leave unset |

Settings are persisted to `~/.local/share/eetool/serial.ini`.

---

# Pin2JSON (`eetool pin2json`)

## Input rules

- Argument starting with `C` followed by digits → treated as LCSC/JLC part ID.
- Anything else → treated as a path to a `.kicad_sym` file.

## JSON schema

```json
{
  "symbol": "LM321MFX",
  "source": "C521137",
  "pin_count": 3,
  "pins": {"1": "VCC", "2": "IN+", "3": "OUT"}
}
```

## Dependency

Requires `JLC2KiCadLib` (installed with `pip install -e .`).

---

# Keil batch scripts (`eetool keil gen-build*`)

## Scatter file warning

Deleting the project `.sct` scatter file will break the generated `__download.ps1` flash script. Regenerate via `eetool keil gen-flash` after any scatter-file change.

## Build result detection

The generated build script scans the project directory for `*.axf`; presence of a newer `.axf` indicates a successful build.
