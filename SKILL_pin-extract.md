---
name: eetool-pin-extract
description: Pin-table extraction and verification from datasheet PDFs. Triggers on: eetool pin, eetool pin extract, eetool pin extract-search, datasheet PDF, 引脚分配, pin assignment.
---

# eetool-pin-extract

Deep dive for `eetool pin extract*`. Read `SKILL.md` first for routing.

## Dependencies

```bash
pip install camelot-py numpy pandas opencv-python-headless pypdfium2 pillow playa-pdf
```

If `import camelot` fails, reinstall with `pip install -e .` from the
`camelot-py` source tree to restore the editable namespace package.

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
