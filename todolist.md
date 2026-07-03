# ee-toolkit TODO List

Generated from alignment check vs `~/.claude/skills/__myskills/electro/`.

## Summary

| # | Priority | Status | Task |
|---|----------|--------|------|
| 1 | 🔴 High | pending | Fix `ee capture` wrapper subcommand mismatch |
| 2 | ⚪ Defer | pending | Push `--duration` into `set.ini` during capture |
| 3 | 🟡 Medium | pending | Complete `ee keil init` pipeline (CLAUDE.md + pre-commit) |
| 4 | 🟢 Low | pending | Add `ee hardware-diff` (port `hardware-diff-by-codes` SOP) |

Recommended order: 1 → 3 → 2 → 4.

---

## 1. Fix `ee capture` wrapper subcommand mismatch

**Priority:** 🔴 High
**Affected:** `src/ee_toolkit/commands/capture.py:78`

### Bug
`commands/capture.py:78` forwards `args.capture_command` verbatim to
`python -m ee_toolkit.capture.atk_cli`. When user runs:

```bash
ee capture start --ch 0,3
```

…it actually invokes:

```bash
python -m ee_toolkit.capture.atk_cli start --ch 0,3
```

…but `atk_cli.main` requires the verb to be `capture` first, so the `start`
subcommand is unreachable through the wrapper. Workaround today is direct
invocation:

```bash
python -m ee_toolkit.capture.atk_cli capture start --ch 0,3
```

### Fix approach
Insert the `capture` verb into the forwarded argv before `args.capture_command`.
The wrapper should be a transparent pass-through:

```python
cmd = [
    sys.executable, "-m", CLI_MODULE,
    "capture",                    # <-- inserted verb
    args.capture_command,
    *args.extra_args,
]
```

Special-case so that user-typed `ee capture start ...` becomes
`atk_cli capture start ...` (matches `atk_cli`'s existing parser).

Update `ALLOWED_SUBCOMMANDS` to reflect the actual `atk_cli` subcommands:
`start`, `info`, `export`, `decode`, `list-decoders`, `config`, `classify`,
`pwm`, `preflight`.

### Verify
```bash
ee capture info tests/fixtures/sample.atkdl   # reaches cmd_info
ee capture --help                              # shows allowed list
ee capture bogus                               # exits 2 with error
```

---

## 2. Push `--duration` into `set.ini` during capture

**Priority:** ⚪ Defer (cosmetic — doesn't break capture, only timing)
**Affected:** `src/ee_toolkit/capture/atk_cli.py` (`cmd_capture`) +
`src/ee_toolkit/capture/lib/lib_config_sync.py`

### Bug
`cmd_capture` syncs `channels`, `setHz`, `threshold` to `set.ini` via
`sync_set_ini`, but **does not push `--duration`**. Symptom: requesting
`--duration 5s` captures for 50s because the GUI retains the last duration
in `set.ini`.

### Fix approach
Add `duration` to the desired params dict in `cmd_capture`. Either:

- (a) Extend `sync_set_ini` to accept `duration` and write it into
  `settingData`.
- (b) Write the duration directly into `settingData` via the existing
  `_patch_json_field` helper in `lib_config_sync.py`.

Pick (a) for consistency with existing channel/rate/threshold handling.

### Verify
```bash
ee capture start --ch 0 --duration 5s
# actual capture duration ≈ 5s (currently sees 50s due to stale set.ini)
```

---

## 3. Complete `ee keil init` pipeline (CLAUDE.md + pre-commit)

**Priority:** 🟡 Medium
**Affected:** `src/ee_toolkit/commands/keil.py:95` (`init_project`)

### Gap
Current `ee keil init` only generates the 3 PowerShell templates.
Original `keil-init` SKILL.md (in `__myskills/electro/keil-init/`) specifies a
full 8-step pipeline. Missing:

1. Parse `.uvprojx` for chip model, OutputName, UV4 path (partially done
   via `parse_output_name` + `find_uv4` — extend to also read `<Device>`
   and `<pCCUsed>` tags).
2. Detect vendor HAL dirs: `Device/`, `Drivers/`, `Library/`, `Libraries/`,
   `**/startup_*.s`.
3. Detect RTOS/framework core dirs (only when present — e.g. `FreeRTOS/`,
   `RT-Thread/`, `QP/`).
4. Write `.claude/CLAUDE.md` with restricted zones A (vendor/toolchain) +
   B (framework core if applicable) + allowed scope table.
5. Write `.claude/hooks/pre-commit` with `RESTRICTED` regex blocking
   vendor/framework paths.
6. Write `.claude/settings.json` registering the hook.
7. Install hook: `cp .claude/hooks/pre-commit .git/hooks/pre-commit`.
8. Test validation: `git add <restricted file>` should be rejected.
9. Initial commit.

### Approach
Two sub-commands for clarity:
- `ee keil init` — keep current behaviour (PowerShell templates only).
- `ee keil setup` — new; runs steps 1–8.

Or merge into one. Decision pending during planning.

### Verify
```bash
mkdir -p /tmp/keil-test && cd /tmp/keil-test
git init
cp <test>.uvprojx .
ee keil init           # templates rendered
ee keil setup          # CLAUDE.md + pre-commit + settings.json exist
ls .claude/            # CLAUDE.md, hooks/pre-commit, settings.json
ls .git/hooks/pre-commit
echo "// test" >> Device/foo.h
git add Device/foo.h
git commit -m "should be blocked"   # expect non-zero exit
```

---

## 4. Add `ee hardware-diff` (port `hardware-diff-by-codes` SOP)

**Priority:** 🟢 Low
**New files:** `src/ee_toolkit/commands/hardware_diff.py` (option B)

### Gap
Original skill `hardware-diff-by-codes` (8-step MCU register-comparison SOP
in `__myskills/electro/hardware-diff-by-codes/`) was **not** consolidated.
No `ee hardware-diff` command exists.

### Two options

**A. Pure skill** (zero code):
Copy `__myskills/electro/hardware-diff-by-codes/SKILL.md` to the project's
own skill location and register it in `SKILL.md`. Easiest, preserves the
manual analysis approach.

**B. CLI tool**:
`ee hardware-diff <proj-a-dir> <proj-b-dir>` that:
1. Auto-scans `.c`/`.h` files for GPIO/RCC register writes.
2. Simulates final state per Step 3 of the original SOP.
3. Emits the markdown report template from Step 8.

Requires a small parser for CRL/CRH/AFRL/AFRH (F1/MM32) +
MODER/OTYPER/OSPEEDR/PUPDR/AFR (F4/L4/G4) register semantics.

### Recommendation
Option A first (5-min port). Option B is a larger project (~half-day) and
depends on user demand.

### Verify (Option A)
Trigger skill on a test firmware pair (e.g. two MM32F0140 variants) and
confirm the 8-step procedure runs to completion and produces a comparison
report.

### Verify (Option B)
```bash
ee hardware-diff ./proj-A ./proj-B --out report.md
cat report.md    # matches Step 8 template structure
```

---

## Reference: alignment matrix (audit baseline)

| Original skill (`__myskills/electro`) | `ee ...` command | Status |
|---|---|---|
| `atk-logic-capture`    | `ee capture`                | ✅ aligned |
| `hardware-diff-by-codes` | _(none)_                  | ❌ TODO #4 |
| `keil-batch-gen`       | `ee keil gen-*`             | ✅ aligned |
| `keil-init`            | `ee keil init`              | ⚠️ TODO #3 |
| `pdf-pin-extract`      | `ee pin`                    | ✅ aligned |
| `pin2json`             | `ee pin2json`               | ✅ aligned |
| `schmd-from-netlist`   | `ee schmd-from-netlist`     | ✅ aligned |
| `serial-monitor`       | `ee serial`                 | ✅ aligned |
| _(new)_                | `ee doctor`                 | 🆕 project-internal |