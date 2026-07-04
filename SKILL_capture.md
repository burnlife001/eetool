---
name: eetool-capture
description: ATK-Logic logic-analyzer wrapper. Triggers on: eetool capture, 逻辑分析仪, ATK-Logic, atk_cli, capture start, capture preflight, capture pwm, --output atkdl.
---

# eetool-capture (ATK-Logic wrapper)

Detailed reference for `eetool capture <subcmd>`. The thin entry point lives in
`SKILL.md` — read that first for routing. This file is the deep dive.

> Original wrappers merged into this skill: `atk-cli-pure` (in
> `~/.claude/skills/__myskills/electro/`).

## Capture workflow

- `eetool capture start` does **not** ask for confirmation by default.
- If `set.ini` must be changed or `--duration` exceeds 10 s, the CLI warns and may restart the GUI automatically.
- Preflight runs automatically on the first capture of a GUI session (DLL-persisted `g_preflight_ok`).
- The save flow uses the GUI Save-As picker for the first capture; subsequent captures save in-place.
- `isCtrlSPressed` is a DLL flag that tells the CLI the picker has already been handled once.

> ⚠ **`--output` only effective on the FIRST capture after GUI start.**
> After the Save-As picker is filled once, the DLL flags `isCtrlSPressed = True`.
> All later saves reuse the previously-saved path regardless of what CLI sends —
> requested `--output` is silently dropped, GUI overwrites the previous file.
> Observed root cause: `isCtrlSPressed` only resets on GUI restart or
> `eetool capture preflight --fix` (which restarts the GUI sub-process).
>
> **Safe workflows for back-to-back captures:**
> 1. Don't pass `--output`. GUI auto-names each capture `capture_<YYYYMMDD_HHMMSS>.atkdl` (always honored).
> 2. Run `eetool capture preflight --fix` between captures when you need controlled names.
> 3. Manually rename the GUI-saved file before the next capture.

## Capture parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `--ch` | Comma-separated channel IDs | (use GUI current) | `--ch 0,1,2,3` |
| `--duration` | Capture duration | `3s` | `--duration 5s` |
| `--sample-rate-hz` | Sample rate in Hz | (use `set.ini`) | `--sample-rate-hz 24000000` |
| `--threshold` | Logic threshold voltage | (use `set.ini`) | `--threshold 1.5` |
| `--sync` | Force sync `set.ini` even if no params changed | false | `--sync` |
| `--rle` | Enable FPGA RLE compression | false | `--rle` |
| `--output` ⚠ first-only | Output filename only (saved to `DATA_DIR`) | auto timestamp | `--output out.atkdl` |

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
| 9 | `--output` ignored after first save (silently drops filename, overwrites previous file) | Run `eetool capture preflight --fix` between captures to reset `isCtrlSPressed`, OR drop `--output` and rely on auto-timestamped `capture_<timestamp>.atkdl`. See "Capture workflow" callout. |

## Capture failure recovery

If capture freezes at 1%:
1. Close ATK-Logic (gracefully if possible).
2. Run `eetool capture preflight --fix` to clean markers and restart.
3. Retry with `--duration 2s` first.

## Test recipes for `--output` filename behavior

Run these 5-step recipes after any change to `atk_cli.py` or the proxy DLL.
They pin the behavior described in the "Capture workflow" ⚠ callout and
known-issue #9 to **observable file-system state**. Each assertion is a
single `test` command — no counting, no negation chains.

### State machine being tested

```
           GUI start           T1              T2          T3a (preflight --fix)         T3b              T4
            │                   │               │                   │                        │                │
isCtrlS ──  False  ─────────►  True  ───────►  True  ─────────►   False  ──────────────►  True  ────────►  True
            │                   │               │                   │                        │                │
            │             saves FOO_T1     drops FOO_T2        restarts GUI sub-proc    saves FOO_T3   saves capture_<TS>
            │             .atkdl           (overwrites         (flag reset)             .atkdl         .atkdl
            │                                FOO_T1)
```

The "True → False → True" arc on `isCtrlS` is what makes `--output`
honored only on T1 and T3b.

### Recipes

```bash
DATA_DIR="E:/__electric/atk-logic-data"    # adapt to your config.ini
cd "$DATA_DIR"

# Clean slate — recipes use unique prefix FOO_ to avoid colliding with captures
rm -f FOO_T1.atkdl FOO_T2.atkdl FOO_T3.atkdl

# Make sure you start with a fresh GUI session: close ATK-Logic, then
# `eetool capture preflight --fix` to bring it back with isCtrlS=False.

# T1   first capture after GUI start — --output MUST be honored
eetool capture start --ch 0,1,2,3 --duration 1s --output FOO_T1.atkdl

# T2   second capture, no preflight — --output MUST be silently dropped
eetool capture start --ch 0,1,2,3 --duration 1s --output FOO_T2.atkdl

# T3a  preflight --fix — resets isCtrlS to False
eetool capture preflight --fix

# T3b  capture after preflight — --output MUST be honored again
eetool capture start --ch 0,1,2,3 --duration 1s --output FOO_T3.atkdl

# T4   no --output — auto-name MUST always be honored
eetool capture start --ch 0,1,2,3 --duration 1s
```

### Acceptance matrix (run all four checks after the recipes finish)

| ID    | File-system assertion         | Shell check                  | Required exit / output | What it verifies |
|-------|-------------------------------|------------------------------|------------------------|------------------|
| **A** | `FOO_T1.atkdl` exists         | `test -f FOO_T1.atkdl`       | exit 0                 | `--output` honored on first capture |
| **B** | `FOO_T2.atkdl` is **absent**  | `test ! -f FOO_T2.atkdl`     | exit 0                 | `--output` silently dropped on second capture (known-issue #9 reproduces) |
| **C** | `FOO_T3.atkdl` exists         | `test -f FOO_T3.atkdl`       | exit 0                 | `preflight --fix` re-honors `--output` |
| **D** | At least one `capture_*.atkdl` exists | `ls capture_*.atkdl 2>/dev/null \| wc -l` | output `≥ 1`  | Auto-name path is state-independent |

Pass = all 4 checks return their required outcome.

**Run all four checks in one shot:**

```bash
cd "$DATA_DIR"
fails=0
test -f FOO_T1.atkdl                        || { echo "A FAIL"; fails=$((fails+1)); }
test ! -f FOO_T2.atkdl                      || { echo "B FAIL"; fails=$((fails+1)); }
test -f FOO_T3.atkdl                        || { echo "C FAIL"; fails=$((fails+1)); }
[ "$(ls capture_*.atkdl 2>/dev/null | wc -l)" -ge 1 ] \
                                            || { echo "D FAIL"; fails=$((fails+1)); }
[ $fails -eq 0 ] && echo "ALL PASS — SKILL.md callout still accurate" \
                  || echo "$fails check(s) failed — see table below"
```

### What to do when a check fails

| Failed check | Means                                                  | Edit SKILL.md |
|--------------|--------------------------------------------------------|---------------|
| **A**        | Bug is **fixed** — `--output` always honored           | Delete the ⚠ callout in *Capture workflow*; mark known-issue #9 as **resolved** |
| **B**        | Bug is **fixed** — `--output` always honored           | Delete the ⚠ callout in *Capture workflow*; mark known-issue #9 as **resolved** |
| **C**        | `preflight --fix` no longer resets the picker          | In known-issue #9 *Fix* column, drop the `preflight --fix` workaround |
| **D**        | Auto-name fallback is broken                           | File a new known-issue; capture workflow's third workaround ("don't pass `--output`") is no longer reliable |

A passing A+B+C+D run certifies the SKILL.md text matches runtime — no edit needed.

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
