import argparse
import glob
import json
import os
import re
import sys


def norm(s):
    return re.sub(r"[^A-Za-z0-9]", "", s or "").upper()


def lcp(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def find_shared_docs(start):
    d = os.path.abspath(start)
    while True:
        cand = os.path.join(d, "__shared_docs")
        if os.path.isdir(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def dir_has_source_files(d):
    try:
        entries = os.listdir(d)
    except OSError:
        return False
    for entry in entries:
        p = os.path.join(d, entry)
        if os.path.isfile(p) and entry.endswith((".c", ".h")):
            return True
        if os.path.isdir(p):
            try:
                for f in os.listdir(p):
                    if f.endswith((".c", ".h")):
                        return True
            except OSError:
                pass
    return False


def find_source_root(start):
    d = os.path.abspath(start)
    while True:
        if dir_has_source_files(d):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def parse_netlist(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    comp = {}
    for blk in re.findall(r"\[\s*\n(.*?)\n\]", text, re.S):
        ls = [x.strip() for x in blk.splitlines() if x.strip()]
        if len(ls) >= 3:
            comp[ls[0]] = (ls[1], ls[2])
    nets = {}
    for blk in re.findall(r"\(\s*\n(.*?)\n\)", text, re.S):
        ls = [x.strip() for x in blk.splitlines() if x.strip()]
        if not ls:
            continue
        nodes = []
        for nd in ls[1:]:
            m = re.match(r"^(.+)-([0-9A-Za-z]+)$", nd)
            if m:
                nodes.append((m.group(1), m.group(2)))
        nets[ls[0]] = nodes
    return comp, nets


def load_chip_jsons(shared):
    out = []
    for jp in glob.glob(os.path.join(shared, "**", "*.json"), recursive=True):
        try:
            j = json.load(open(jp, encoding="utf-8"))
        except Exception:
            continue
        if "chip_name" in j and "pins" in j:
            out.append((jp, j))
    return out


def pick_mcu(comp, chips):
    names = [norm(j.get("chip_name", "")) for _, j in chips]
    best = None
    for desig, (fp, val) in comp.items():
        core = norm(val.split("-")[0].split()[0] if val else "")
        score = max((lcp(core, n) for n in names), default=0)
        if score >= 6 and (best is None or score > best[0]):
            best = (score, desig, fp, val, core)
    if not best:
        return None
    return best[1], best[2], best[3], best[4]


def pick_chip(core, chips):
    best = None
    for jp, j in chips:
        s = lcp(core, norm(j.get("chip_name", "")))
        if best is None or s > best[0]:
            best = (s, jp, j)
    return best[1], best[2]


def pick_package(fp, val, j):
    pkgs = j.get("packages", [])
    npkgs = {p: norm(p) for p in pkgs}
    tokens = [norm(fp)] + [norm(t) for t in re.split(r"[-\s]", val or "") if t]
    for tok in tokens:
        if not tok:
            continue
        for p, np_ in npkgs.items():
            if tok == np_:
                return p
        for p, np_ in npkgs.items():
            if tok and (tok in np_ or np_ in tok):
                return p
    return pkgs[0] if pkgs else None


def chip_pinmap(j, package):
    m = {}
    for p in j.get("pins", []):
        n = p.get("packages", {}).get(package)
        if isinstance(n, int):
            m[n] = {
                "name": p.get("name", ""),
                "type": p.get("type", ""),
                "main": p.get("main_function", ""),
            }
    return m


def is_signal_name(v):
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9_+]*$", v or "")) and not re.match(r"^TP\d", v or "")


GPIO_DEFINE_RE = re.compile(
    r"^\s*#\s*define\s+(\w+)\s+.*?\b(GPIO[A-Z])->\w+\.P(\d+)\b",
    re.MULTILINE,
)


def scan_source_identifiers(source_root):
    ids = {}
    exclude_dirs = {"__shared_docs", ".git", "__pycache__", "node_modules"}
    for root, dirs, files in os.walk(source_root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            if not fname.endswith((".c", ".h")):
                continue
            path = os.path.join(root, fname)
            rel = os.path.relpath(path, source_root).replace("\\", "/")
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                continue
            for m in GPIO_DEFINE_RE.finditer(text):
                name = m.group(1)
                port = m.group(2)[-1]
                pin = int(m.group(3))
                line = text[:m.start()].count("\n") + 1
                if name.upper() == f"P{port}{pin}":
                    continue
                ids.setdefault((port, pin), []).append((name, rel, line))
    return ids


def parse_chip_pin_name(name):
    m = re.match(r"^P([A-D])(\d+)$", name or "")
    if not m:
        return None
    return (m.group(1), int(m.group(2)))


def name_consistent(board, macros):
    nb = norm(board)
    for mname in macros:
        nm = norm(mname)
        if not nb or not nm:
            continue
        if nb in nm or nm in nb:
            return True
        if lcp(nb, nm) >= 3:
            return True
    return False


# ── infer helpers ──────────────────────────────────────────────────────────

_POWER = re.compile(r"^(GND|PGND|AGND|DGND|[+-]?\d+V\d*|V(DD|SS|CC|BAT|BUS|IN|OUT|REF)\w*)$", re.I)


def is_power(net):
    return bool(_POWER.match(net or ""))


def build_comp_pins(nets):
    cp = {}
    for name, nodes in nets.items():
        for d, pin in nodes:
            cp.setdefault(d, []).append((pin, name))
    return cp


def expand_topology(mcu, pin, net0, nets, comp, comp_pins, maxhop=4, busmax=8):
    lines = [f"  L0 本网络 {net0}  成员: "
             + ", ".join(f"{d}-{p}" for d, p in nets.get(net0, []))]
    visited = {net0}
    seen_edge = set()
    frontier = [net0]
    for hop in range(1, maxhop + 1):
        nxt = []
        for src in frontier:
            for d, _p in nets.get(src, []):
                if d == mcu:
                    continue
                val = comp.get(d, ("?", "?"))[1]
                for pp, nn in comp_pins.get(d, []):
                    if nn == src or (d, pp) in seen_edge:
                        continue
                    seen_edge.add((d, pp))
                    stop = ""
                    if is_power(nn):
                        stop = "  (电源/地, 截断)"
                    elif len(nets.get(nn, [])) > busmax:
                        stop = f"  (大网络 {len(nets[nn])} 节点, 截断)"
                    lines.append(f"  {'  ' * hop}L{hop} {d}-{pp} [{val}] {src} → {nn}{stop}")
                    if nn not in visited and not stop:
                        visited.add(nn)
                        nxt.append(nn)
        frontier = nxt
    return lines


# ── command implementations ────────────────────────────────────────────────

def _resolve_netlist(args_netlist):
    netlist = args_netlist
    if not netlist:
        cands = glob.glob("*.NET") + glob.glob("*.net")
        if not cands:
            print("未找到 .NET 网表, 请显式指定", file=sys.stderr)
            return None
        netlist = cands[0]
    return os.path.abspath(netlist)


def _load_context(netlist_path, shared_docs):
    netlist_dir = os.path.dirname(netlist_path)
    shared = shared_docs or find_shared_docs(netlist_dir)
    if not shared:
        print("未找到 __shared_docs 目录", file=sys.stderr)
        return None, None, None
    chips = load_chip_jsons(shared)
    if not chips:
        print(f"{shared} 下未发现芯片引脚 JSON", file=sys.stderr)
        return None, None, None
    comp, nets = parse_netlist(netlist_path)
    return comp, nets, chips


def _pick_target(args, comp, chips):
    if args.designator:
        desig = args.designator
        fp, val = comp.get(desig, ("", ""))
        core = norm(val.split("-")[0].split()[0] if val else desig)
    else:
        picked = pick_mcu(comp, chips)
        if not picked:
            print("无法自动识别 MCU, 请用 --designator 指定", file=sys.stderr)
            return None
        desig, fp, val, core = picked
    jp, j = pick_chip(core, chips)
    package = args.package or pick_package(fp, val, j)
    return desig, fp, val, core, jp, j, package


def cmd_map(args):
    netlist = _resolve_netlist(args.netlist)
    if not netlist:
        return 1
    comp, nets, chips = _load_context(netlist, args.shared_docs)
    if comp is None:
        return 1

    picked = _pick_target(args, comp, chips)
    if picked is None:
        return 1
    desig, fp, val, core, jp, j, package = picked
    pinmap = chip_pinmap(j, package)
    total = max(pinmap) if pinmap else 0

    pin2net = {}
    for name, nodes in nets.items():
        for d, pin in nodes:
            if d == desig and pin.isdigit():
                pin2net[int(pin)] = name

    source_root = args.source_dir
    if source_root:
        source_root = os.path.abspath(source_root)
    else:
        source_root = find_source_root(os.path.dirname(netlist))
    source_ids = scan_source_identifiers(source_root) if source_root else {}
    has_source = bool(source_ids)

    rows = []
    for pin in range(1, total + 1):
        ci = pinmap.get(pin, {})
        chipfn = ci.get("name", "")
        src_names = []
        src_id = ""
        if has_source:
            parsed = parse_chip_pin_name(chipfn)
            if parsed:
                matches = source_ids.get(parsed)
                if matches:
                    seen = set()
                    parts = []
                    for name, rel, line in matches:
                        key = (name, rel, line)
                        if key in seen:
                            continue
                        seen.add(key)
                        if name not in src_names:
                            src_names.append(name)
                        parts.append(f"{name} ({rel}:{line})")
                    src_id = "<br>".join(parts)

        net = pin2net.get(pin)
        if net is None:
            board, src = "NC", "悬空无连接 → 标记 NC"
        elif not net.startswith("Net"):
            board, src = net, "网表网络标签"
            if src_names and not name_consistent(board, src_names):
                src += f" · ⓘ源码作 {src_names[0]}"
        else:
            tp = next((comp[d][1] for d, _ in nets[net]
                       if comp.get(d, ("", ""))[0].startswith("TP")
                       and is_signal_name(comp[d][1])), None)
            if tp:
                board, src = tp, f"测试点值字段({net})"
            elif ci.get("type") == "S":
                board, src = chipfn, f"JSON电源功能({net})"
            elif src_names:
                board, src = src_names[0], f"源码标识({net})"
            else:
                board, src = net, "⚠ 自动命名, 必须拓扑推断"

        rows.append((pin, chipfn, board, src, src_id))

    out = args.out or os.path.join(os.path.dirname(netlist), f"SCH-{j.get('chip_name', desig)}.md")
    buf = []
    buf.append(f"# {j.get('chip_name')} ({desig}) 板上信号名 — 网表 + JSON 闭环提取\n")
    src_note = ""
    if source_root:
        src_note = f"  |  源码根: `{os.path.relpath(source_root, os.path.dirname(netlist))}`"
    buf.append(f"> 网表: `{os.path.basename(netlist)}`  |  封装: `{package}`  "
               f"|  芯片JSON: `{os.path.relpath(jp, os.path.dirname(netlist))}`{src_note}\n")
    buf.append("\n## 原理图\n")
    if has_source:
        buf.append("| 引脚号 | 芯片功能 | 板上信号名 | 来源 | 源码标识 |")
        buf.append("|:------:|----------|-----------|------|----------|")
        for pin, chipfn, board, src, src_id in rows:
            buf.append(f"| {pin} | {chipfn} | {board} | {src} | {src_id} |")
    else:
        buf.append("| 引脚号 | 芯片功能 | 板上信号名 | 来源 |")
        buf.append("|:------:|----------|-----------|------|")
        for pin, chipfn, board, src, _ in rows:
            buf.append(f"| {pin} | {chipfn} | {board} | {src} |")

    text = "\n".join(buf) + "\n"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(text)
    return 0


def cmd_infer(args):
    netlist = _resolve_netlist(args.netlist)
    if not netlist:
        return 1
    comp, nets, chips = _load_context(netlist, args.shared_docs)
    if comp is None:
        return 1

    picked = _pick_target(args, comp, chips)
    if picked is None:
        return 1
    desig, fp, val, core, jp, j, package = picked
    pinmap = chip_pinmap(j, package)
    comp_pins = build_comp_pins(nets)
    total = max(pinmap) if pinmap else 0

    pin2net = {}
    for name, nodes in nets.items():
        for d, pin in nodes:
            if d == desig and pin.isdigit():
                pin2net[int(pin)] = name

    cards = []
    for pin in range(1, total + 1):
        ci = pinmap.get(pin, {})
        chipfn = ci.get("name", "")
        net = pin2net.get(pin)

        if net is None:
            continue
        if not net.startswith("Net"):
            continue

        tp = next((comp[d][1] for d, _ in nets[net]
                   if comp.get(d, ("", ""))[0].startswith("TP")
                   and is_signal_name(comp[d][1])), None)
        if tp or ci.get("type") == "S":
            continue

        lines = expand_topology(desig, pin, net, nets, comp, comp_pins)
        cards.append((pin, chipfn, "待定(自动名)", lines))

    buf = []
    buf.append(f"# {j.get('chip_name')} ({desig}) 待定引脚邻接拓扑 — 供功能推断\n")
    buf.append(f"> 网表: `{os.path.basename(netlist)}` | 封装: `{package}`\n")
    if not cards:
        buf.append("\n**无待定引脚**:所有有连接的脚都已被网络标签/测试点/电源JSON 命名,"
                   "悬空脚仅 NC。无需推断。\n")
    for pin, chipfn, kind, lines in cards:
        buf.append(f"\n## pin{pin} ({chipfn}) — {kind}")
        buf.extend(lines)

    text = "\n".join(buf) + "\n"
    out = args.out or os.path.join(os.path.dirname(netlist), f"{desig}_pin_infer.md")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(text)
    return 0


# ── CLI ────────────────────────────────────────────────────────────────────

def add_subparser(subparsers):
    parser = subparsers.add_parser("schmd-from-netlist", help="Schematic netlist tools")
    sub = parser.add_subparsers(dest="schmd_command", required=True)

    map_cmd = sub.add_parser("map", help="Map MCU pins to board signal names")
    map_cmd.add_argument("netlist", nargs="?", help="Path to .NET netlist")
    map_cmd.add_argument("--designator")
    map_cmd.add_argument("--package")
    map_cmd.add_argument("--shared-docs")
    map_cmd.add_argument("--source-dir")
    map_cmd.add_argument("--out")

    infer_cmd = sub.add_parser("infer", help="Infer topology for unnamed pins")
    infer_cmd.add_argument("netlist", nargs="?", help="Path to .NET netlist")
    infer_cmd.add_argument("--designator")
    infer_cmd.add_argument("--package")
    infer_cmd.add_argument("--shared-docs")
    infer_cmd.add_argument("--out")


def run(args):
    if args.schmd_command == "map":
        return cmd_map(args)
    if args.schmd_command == "infer":
        return cmd_infer(args)
    return 1
