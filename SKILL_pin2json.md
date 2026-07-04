---
name: eetool-pin2json
description: Convert KiCad symbol or LCSC part to pin JSON. Triggers on: eetool pin2json, C521137, JLC part, .kicad_sym.
---

# eetool-pin2json

Deep dive for `eetool pin2json`. Read `SKILL.md` first for routing.

## Usage

```bash
eetool pin2json C521137               # LCSC/JLC part → pin JSON
eetool pin2json path/to/lib.kicad_sym # KiCad symbol → pin JSON
```

## Input rules

- Argument starting with `C` followed by digits → treated as LCSC/JLC part ID (looks up the symbol).
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

Requires `JLC2KiCadLib` — installed from source:

```bash
pip install -e <JLC2KiCadLib-repo>
```

Pull requests in `JLC2KiCadLib` cache data into the symbol library under
`~/.local/share/JLC2KiCadLib/symbols/`.
