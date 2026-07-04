---
name: eetool-schmd
description: Schematic pinmap / signal-topology inference from a Protel/DXP netlist. Triggers on: eetool schmd-from-netlist, netlist, schematic pinmap, signal topology, 信号拓扑.
---

# eetool-schmd (schematic-from-netlist)

Deep dive for `eetool schmd-from-netlist ...`. Read `SKILL.md` first for routing.

## Subcommands

| Subcommand | Purpose |
|------------|---------|
| `eetool schmd-from-netlist map <netlist.txt>` | Build schematic pinmap from a Protel netlist. |
| `eetool schmd-from-netlist infer <netlist.txt>` | Infer signal topology (per-net, cross-net). |

## 6-level naming priority

1. Net Label
2. Pin Name (source component)
3. Signal Hint (JSON alias in `__shared_docs/<signal>.json`)
4. Default Signal Name
5. Net ID
6. Fallback (`NC`)

The earlier the level, the higher the priority — a Net Label always wins
over a Net ID, etc.

## User warnings

- Ensure SCH and PCB are synchronized before running.
- Mark NC pins explicitly (`NC` net label or pin name).
- Do **not** attach multiple net labels to the same net.

## Netlist format (Protel/DXP bracket)

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

Each `[ ... ]` block is one component. The first line is the designator,
succeeding lines are pin-to-net mappings.

## Source alias hint rules

`__shared_docs/<signal>.json` files are matched by signal-name substring;
the first matching alias is used as the Level-3 hint. Place one alias file
per signal under a `__shared_docs/` directory next to the netlist.

## Limitations

1. Only Protel/DXP-style bracket netlists are supported.
2. Multi-sheet hierarchical designs may require manual review.
3. Bus notation (`DATA[0..7]`) is not expanded automatically.
