import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ── UTF-8 output on Windows ─────────────────────────────────────────────────
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr.encoding != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  Shared utilities
# ═══════════════════════════════════════════════════════════════════════════

def normalize(text):
    """Remove stray soft-hyphen / zero-width artifacts from PDF text extraction."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    for ch in ["\xad", "­", "​", "", "‐", "‑"]:
        text = text.replace(ch, "")
    return text


def clean_cell_compact(text):
    """Pin assignment: newlines -> spaces."""
    text = normalize(text)
    text = text.replace("\r\n", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_cell_slash(text):
    """Pin assignment multiplex/additional columns: join with '/'."""
    text = normalize(text)
    parts = [p for p in re.split(r"\s+", text) if p]
    return "/".join(parts)


def clean_cell_join(text):
    """Multiplexing table cells: remove all line breaks, join to one line."""
    text = normalize(text)
    text = text.replace("\r\n", "").replace("\n", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_package_name(name):
    """Normalize package column names."""
    name = normalize(name)
    for ch in ["–", "—", "−", "‐", "‑", "—", "―"]:
        name = name.replace(ch, "-")
    name = re.sub(r"[^A-Za-z0-9\s\-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"\s*-\s*", "-", name)
    name = re.sub(r"\s+(\d)", r"\1", name)
    return name


# ═══════════════════════════════════════════════════════════════════════════
#  Page search
# ═══════════════════════════════════════════════════════════════════════════

PIN_KEYWORDS = [
    "pin assignment", "pin definition", "pin description",
    "table 4-1", "table 3-1",
    "引脚定义", "管脚分配", "引脚分配", "表 4-1",
]

MUX_KEYWORDS = [
    "multiplexing", "alternate function", "af0", "af1",
    "table 4-2", "复用功能",
    "引脚复用", "复用功能", "交替功能", "port multiplexing",
]


def search_pages(pdf_path):
    """Scan PDF for pin-assignment and multiplexing pages."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    total = len(pdf)

    pin_hits = set()
    mux_hits = set()
    pin_name_pages = set()

    PIN_NAME_RE = re.compile(r"\bP[A-H]\d+\b")
    TABLE_HEADER_KW = ["main function", "multiplex function", "additional function", "i/o level"]

    for i in range(total):
        text = pdf[i].get_textpage().get_text_range()
        text_lower = text.lower()

        if any(kw in text_lower for kw in PIN_KEYWORDS):
            pin_hits.add(i + 1)
        if any(kw in text_lower for kw in MUX_KEYWORDS):
            mux_hits.add(i + 1)
        if PIN_NAME_RE.search(text) and any(kw in text_lower for kw in TABLE_HEADER_KW):
            pin_name_pages.add(i + 1)

    pin_pages = _resolve_table_range(pin_hits, pin_name_pages, total)

    if pin_pages and pin_pages[-1] < total:
        next_text = pdf[pin_pages[-1]].get_textpage().get_text_range().lower()
        if any(kw in next_text for kw in ["i/o", "vdd", "vss", "i = input", "tc:"]):
            pin_pages.append(pin_pages[-1] + 1)

    af_pages = set()
    for i in range(total):
        text = pdf[i].get_textpage().get_text_range()
        if re.search(r"\bAF[0-9]+\b", text):
            af_pages.add(i + 1)
    af_pin_pages = {
        p for p in af_pages
        if PIN_NAME_RE.search(pdf[p - 1].get_textpage().get_text_range())
    }
    if af_pin_pages:
        mux_pages = _largest_contiguous(af_pin_pages)
    else:
        mux_pages = _largest_contiguous(mux_hits | (af_pages & pin_name_pages))

    return pin_pages, mux_pages


def _resolve_table_range(keyword_hits, data_pages, total_pages, max_gap=1):
    if not keyword_hits:
        return _largest_contiguous(data_pages)
    candidates = sorted(keyword_hits, reverse=True)
    for start_pg in candidates:
        lo = start_pg
        while lo > 1 and (lo - 1) in data_pages:
            lo -= 1
        hi = start_pg
        while hi < total_pages and (hi + 1) in data_pages:
            hi += 1
        span = list(range(lo, hi + 1))
        if len(span) >= 2:
            return span
    return _largest_contiguous(keyword_hits)


def _largest_contiguous(hits):
    if not hits:
        return []
    sorted_hits = sorted(hits)
    blocks = []
    current = [sorted_hits[0]]
    for p in sorted_hits[1:]:
        if p == current[-1] + 1:
            current.append(p)
        else:
            blocks.append(current)
            current = [p]
    blocks.append(current)
    blocks.sort(key=lambda b: (len(b), b[-1]), reverse=True)
    return blocks[0]


def detect_ports(pdf_path, mux_pages):
    """Discover port names from mux page headers or pin names."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    ports = []
    seen = set()
    for pg in mux_pages:
        text = pdf[pg - 1].get_textpage().get_text_range()
        for m in re.finditer(r"(P[A-H])\s+port\s+multiplexing", text):
            port = m.group(1)
            if port not in seen:
                ports.append(port)
                seen.add(port)
    for pg in mux_pages:
        text = pdf[pg - 1].get_textpage().get_text_range()
        page_ports = re.findall(r"\b(P[A-H])\d+\b", text)
        for port in page_ports:
            if port not in seen:
                ports.append(port)
                seen.add(port)
    return ports if ports else None


def detect_mux_cols(pdf_path, mux_pages):
    """Count AF columns from a mux table header."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    for pg in mux_pages:
        text = pdf[pg - 1].get_textpage().get_text_range()
        af_matches = re.findall(r"AF(\d+)", text)
        if af_matches:
            max_af = max(int(m) for m in af_matches)
            col_names = ["Pin"] + [f"AF{i}" for i in range(max_af + 1)]
            return len(col_names), col_names, max_af
    return 9, ["Pin"] + [f"AF{i}" for i in range(8)], 8


# ═══════════════════════════════════════════════════════════════════════════
#  Extraction
# ═══════════════════════════════════════════════════════════════════════════

def _looks_like_pin_assignment(df):
    header_text = " ".join(str(v).lower() for v in df.iloc[0] if v)
    return "name" in header_text or "main" in header_text or "multiplex" in header_text


def _looks_like_mux_table(df):
    header_text = " ".join(str(v).lower() for v in df.iloc[0] if v)
    return "af0" in header_text


def extract_pin_assignment(pdf_path, pin_pages, flavor):
    import camelot
    import pandas as pd

    page_range = f"{pin_pages[0]}-{pin_pages[-1]}"
    tables = camelot.read_pdf(pdf_path, pages=page_range, flavor=flavor)

    pin_tables = [t for t in tables if _looks_like_pin_assignment(t.df)]
    if not pin_tables:
        pin_tables = tables

    header = [clean_cell_compact(str(v)) for v in pin_tables[0].df.iloc[0]]
    slash_cols = {"Multiplex function", "Additional function"}

    fragments = []
    for t in pin_tables:
        df = t.df.copy()
        if df.shape[1] != len(header):
            continue
        df.columns = header
        df = df.iloc[1:].copy()
        for col in df.columns:
            df[col] = df[col].apply(clean_cell_compact)
        for col in slash_cols.intersection(df.columns):
            df[col] = df[col].apply(lambda x: clean_cell_slash(x) if str(x).strip() else "")
        fragments.append(df)

    if not fragments:
        return pd.DataFrame()

    df = pd.concat(fragments, ignore_index=True)
    df = df[~(df == "").all(axis=1)]
    df = df.reset_index(drop=True)
    return df


def extract_multiplexing(pdf_path, mux_pages, port_names, mux_col_names, flavor):
    import camelot
    import pandas as pd

    page_range = f"{mux_pages[0]}-{mux_pages[-1]}"
    tables = camelot.read_pdf(pdf_path, pages=page_range, flavor=flavor)

    mux_tables = [t for t in tables if _looks_like_mux_table(t.df)]
    if not mux_tables:
        mux_tables = tables

    result = {}
    for name, t in zip(port_names, mux_tables):
        df = t.df.copy()
        if df.shape[1] == len(mux_col_names):
            df.columns = mux_col_names
        else:
            df.columns = [clean_cell_compact(str(c)) for c in df.columns]
        for col in df.columns:
            df[col] = df[col].apply(clean_cell_join)
        header_values = list(df.columns)
        mask = df.apply(lambda row: all(str(c).strip() == h for c, h in zip(row, header_values)), axis=1)
        df = df[~mask]
        df = df[~(df == "").all(axis=1)]
        df = df.reset_index(drop=True)
        result[name] = df
    return result


def df_to_markdown(df, title):
    lines = [f"## {title}", ""]
    if df.empty:
        lines.append("*No data extracted.*")
        lines.append("")
        return "\n".join(lines)
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "|" + "|".join([" --- " for _ in df.columns]) + "|"
    lines.append(header)
    lines.append(sep)
    for _, row in df.iterrows():
        cells = [str(v) if str(v).strip() else " " for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def _col_starting(row, prefix):
    prefix_lower = prefix.lower()
    for col in row.index:
        if str(col).lower().strip().startswith(prefix_lower):
            return str(row.get(col, "")).strip()
    return ""


def build_json(pin_df, mux, chip_name, pdf_basename, max_af):
    non_pkg_prefixes = (
        "name", "type", "i/o level", "main function",
        "multiplex function", "additional function",
    )
    raw_packages = [
        c for c in pin_df.columns
        if not any(c.lower().strip().startswith(p) for p in non_pkg_prefixes)
    ]
    packages = [clean_package_name(p) for p in raw_packages]
    raw_to_clean = dict(zip(raw_packages, packages))

    mux_lookup = {}
    for port, df in mux.items():
        for _, row in df.iterrows():
            pin = str(row.get("Pin", "")).strip()
            if not pin:
                continue
            mux_lookup[pin] = {
                col: (str(v).strip() if str(v).strip() else None)
                for col, v in row.items() if col != "Pin"
            }

    pins = []
    for _, row in pin_df.iterrows():
        raw_name = str(row.get("Name", "")).strip()
        m = re.match(r"(P[A-H]\d+)", raw_name)
        base_name = m.group(1) if m else raw_name

        pkg_nums = {}
        for raw_pkg in raw_packages:
            raw = str(row.get(raw_pkg, "")).strip()
            num = re.search(r"\d+", raw)
            pkg_nums[raw_to_clean[raw_pkg]] = int(num.group(0)) if num else None

        mux_str = _col_starting(row, "multiplex function")
        add_str = _col_starting(row, "additional function")

        pins.append({
            "name": raw_name,
            "type": _col_starting(row, "type"),
            "io_level": _col_starting(row, "i/o level"),
            "main_function": _col_starting(row, "main function"),
            "multiplex_functions": [f.strip() for f in mux_str.split("/") if f.strip()] if mux_str else [],
            "additional_functions": [f.strip() for f in add_str.split("/") if f.strip()] if add_str else [],
            "packages": pkg_nums,
            "alternate_functions": mux_lookup.get(base_name, {}),
        })

    return {
        "chip_name": chip_name,
        "source_pdf": pdf_basename,
        "packages": packages,
        "ports": [p for p in sorted(mux.keys())],
        "pins": pins,
        "metadata": {
            "extraction_date": datetime.now().isoformat(),
            "extractor_version": "1.2.0",
        },
    }


def write_package_markdown(data, package, out_path):
    pins = []
    for p in data["pins"]:
        raw = p["packages"].get(package)
        if raw is None:
            continue
        try:
            pin_num = int(raw)
        except (TypeError, ValueError):
            continue
        pins.append({**p, "package_pin": pin_num})
    pins.sort(key=lambda x: x["package_pin"])

    if not pins:
        lines = [
            f"# {data['chip_name']} Pin Assignment and Multiplexing — {package}",
            "",
            "*No pins found for this package.*",
        ]
        Path(out_path).write_text("\n".join(lines), encoding="utf-8", newline="\n")
        return

    af_cols = sorted(
        {k for p in pins for k in p.get("alternate_functions", {}).keys()},
        key=lambda s: int(re.search(r"\d+", s).group(0)) if re.search(r"\d+", s) else 0
    )
    header = ["Pin", "Name", "Type", "IO Level", "Main Function",
              "Multiplex Functions", "Additional Functions"] + af_cols
    sep = "|" + "|".join([" --- " for _ in header]) + "|"
    lines = [
        f"# {data['chip_name']} Pin Assignment and Multiplexing — {package}",
        "",
        "| " + " | ".join(header) + " |",
        sep,
    ]
    for p in pins:
        af = p.get("alternate_functions", {})
        row = [
            str(p["package_pin"]),
            p["name"],
            p["type"],
            p["io_level"] or "—",
            p["main_function"],
            ", ".join(p["multiplex_functions"]) or "—",
            ", ".join(p["additional_functions"]) or "—",
        ] + [af.get(col) or "—" for col in af_cols]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    Path(out_path).write_text("\n".join(lines), encoding="utf-8", newline="\n")


# ═══════════════════════════════════════════════════════════════════════════
#  Markdown verification
# ═══════════════════════════════════════════════════════════════════════════

PASS = 0
WARN = 1
FAIL = 2
RESULT = {0: "PASS", 1: "WARN", 2: "FAIL"}


def parse_md_tables(text):
    lines = text.split("\n")
    tables = []
    current_h2 = None
    i = 0
    while i < len(lines):
        if lines[i].startswith("## "):
            current_h2 = lines[i][3:].strip()
            i += 1
            continue
        if lines[i].startswith("# "):
            current_h2 = None
            i += 1
            continue

        stripped = lines[i].strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            i += 1
            continue

        if i + 1 >= len(lines):
            i += 1
            continue
        sep = lines[i + 1].strip()
        if not re.match(r"^\|[\s\-:]+\|", sep):
            i += 1
            continue

        header_cells = [c.strip() for c in stripped[1:-1].split("|")]
        col_count = len(header_cells)
        header_line = i + 1
        i += 2

        rows = []
        while i < len(lines):
            row_line = lines[i].strip()
            if not row_line.startswith("|") or not row_line.endswith("|"):
                break
            cells = [c.strip() for c in row_line[1:-1].split("|")]
            if len(cells) < col_count:
                cells.extend([""] * (col_count - len(cells)))
            elif len(cells) > col_count:
                cells = cells[:col_count]
            rows.append(cells)
            i += 1

        tables.append({
            "h2": current_h2,
            "columns": header_cells,
            "rows": rows,
            "line_start": header_line,
        })

    return tables


def check_file(path):
    msgs = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return (0, 0, 1, [f"File not found: {path}"])
    if not content.strip():
        return (0, 0, 1, ["File is empty"])
    line_count = len(content.split("\n"))
    msgs.append(f"File: {path} ({line_count} lines)")
    return (1, 0, 0, msgs)


def check_pin_table(tables, content):
    pin_tables = [t for t in tables if t["h2"] and "pin assignment" in t["h2"].lower()]
    if not pin_tables:
        pin_tables = [t for t in tables if "LQFP" in str(t["columns"]) or "Name" in t["columns"]]
        if not pin_tables and tables:
            pin_tables = [tables[0]]

    if not pin_tables:
        return (0, 0, 1, ["Pin Assignment table not found"])

    t = pin_tables[0]
    msgs = []
    passes = 1
    warns = 0
    fails = 0

    col_count = len(t["columns"])
    row_count = len(t["rows"])
    msgs.append(f"Pin Assignment: {row_count} pins, {col_count} columns")
    msgs.append(f"  Columns: {t['columns']}")

    name_cols = [c for c in t["columns"] if c.lower() == "name"]
    if not name_cols:
        fails += 1
        msgs.append("[FAIL] No 'Name' column found in pin assignment table")

    if row_count < 5:
        fails += 1
        msgs.append(f"[FAIL] Only {row_count} pin rows — likely incomplete extraction")
    elif row_count < 15:
        warns += 1
        msgs.append(f"[WARN] Only {row_count} pin rows — verify against datasheet")

    empty_rows = 0
    header_dup = 0
    for row in t["rows"]:
        if all(c == "" or c == " " for c in row):
            empty_rows += 1
        if row[0].strip() == t["columns"][0]:
            header_dup += 1
    if empty_rows:
        warns += 1
        msgs.append(f"[WARN] {empty_rows} empty row(s) in pin assignment table")
    if header_dup:
        warns += 1
        msgs.append(f"[WARN] {header_dup} row(s) matching header — possible page-break artifact")

    return (passes, warns, fails, msgs)


def check_mux_tables(tables, expected_ports, expected_cols, content):
    mux_tables = [t for t in tables if t["h2"] and "multiplexing" in t["h2"].lower()]
    if not mux_tables:
        mux_tables = [t for t in tables if "AF0" in t["columns"]]

    msgs = []
    passes = 0
    warns = 0
    fails = 0

    if not mux_tables:
        return (0, 0, 1, ["[FAIL] No multiplexing tables found"])

    found_ports = []
    for t in mux_tables:
        h2 = t.get("h2", "(no heading)")
        msgs.append(f"  {h2}: {len(t['rows'])} pins, {len(t['columns'])} cols")
        found_ports.append(h2)

        if expected_cols and len(t["columns"]) != expected_cols:
            warns += 1
            msgs.append(f"    [WARN] Expected {expected_cols} columns, got {len(t['columns'])}")

        if t["columns"][0].lower() != "pin":
            warns += 1
            msgs.append(f"    [WARN] First column is '{t['columns'][0]}', expected 'Pin'")

        empty = sum(1 for r in t["rows"] if all(c == "" or c == " " for c in r))
        if empty:
            warns += 1
            msgs.append(f"    [WARN] {empty} empty row(s)")

    if expected_ports:
        port_set = set(expected_ports)
        found_set = set()
        for h2 in found_ports:
            m = re.match(r"(P[A-H])", h2)
            if m:
                found_set.add(m.group(1))
        missing_ports = port_set - found_set
        extra_ports = found_set - port_set
        if missing_ports:
            fails += 1
            msgs.append(f"[FAIL] Missing multiplexing tables: {sorted(missing_ports)}")
        if extra_ports:
            warns += 1
            msgs.append(f"[WARN] Unexpected extra ports: {sorted(extra_ports)}")
        if not missing_ports and not extra_ports:
            passes += 1
            msgs.append(f"[PASS] All {len(port_set)} expected ports present")

    msgs.insert(0, f"Multiplexing: {len(mux_tables)} table(s)")
    return (passes, warns, fails, msgs)


def check_cross_validation(tables, content):
    pin_tables = [t for t in tables if t["h2"] and "pin assignment" in t["h2"].lower()]
    if not pin_tables:
        pin_tables = [t for t in tables if "Name" in t["columns"]]
    if not pin_tables:
        return (0, 0, 1, ["[FAIL] Cannot cross-validate: missing pin assignment table"])

    mux_tables = [t for t in tables if t["h2"] and "multiplexing" in t["h2"].lower()]
    if not mux_tables:
        mux_tables = [t for t in tables if "AF0" in t["columns"]]

    if not mux_tables:
        return (0, 1, 0, ["[WARN] Cannot cross-validate: no mux tables found"])

    pt = pin_tables[0]
    name_idx = None
    for i, c in enumerate(pt["columns"]):
        if c.lower() == "name":
            name_idx = i
            break

    if name_idx is None:
        return (0, 1, 0, ["[WARN] Cannot cross-validate: 'Name' column not found"])

    PIN_RE = re.compile(r"\b(P[A-H]\d+)\b")
    assign_pins = {}
    for row in pt["rows"]:
        raw = row[name_idx].strip()
        for m in PIN_RE.finditer(raw):
            pname = m.group(1)
            port = pname[:2]
            if port not in assign_pins:
                assign_pins[port] = set()
            assign_pins[port].add(pname)

    if not assign_pins:
        return (0, 1, 0, ["[WARN] No pin names found in assignment table"])

    mux_pins = {}
    for t in mux_tables:
        m = re.match(r"(P[A-H])", t.get("h2", ""))
        if not m:
            continue
        port = m.group(1)
        mux_pins[port] = set()
        for row in t["rows"]:
            pin = row[0].strip()
            if PIN_RE.match(pin):
                mux_pins[port].add(pin)

    msgs = []
    passes = 0
    warns = 0
    fails = 0

    all_assign_ports = set(assign_pins.keys())
    all_mux_ports = set(mux_pins.keys())
    shared = all_assign_ports & all_mux_ports

    missing_lists = []
    for port in sorted(shared):
        assign_set = assign_pins[port]
        mux_set = mux_pins[port]
        missing_in_mux = assign_set - mux_set
        extra_in_mux = mux_set - assign_set
        missing_lists.append(missing_in_mux)

        if missing_in_mux:
            warns += 1
            msgs.append(
                f"[WARN] {port}: {len(missing_in_mux)} pin(s) in assignment "
                f"but missing from mux: {sorted(missing_in_mux)[:5]}"
                + ("..." if len(missing_in_mux) > 5 else "")
            )
        if extra_in_mux:
            warns += 1
            msgs.append(
                f"[WARN] {port}: {len(extra_in_mux)} pin(s) in mux "
                f"but not in assignment: {sorted(extra_in_mux)[:5]}"
                + ("..." if len(extra_in_mux) > 5 else "")
            )

    if not shared:
        warns += 1
        msgs.append("[WARN] No port overlap between assignment and mux tables")
    elif not any(missing_lists):
        passes += 1
        msgs.append(f"[PASS] Cross-validation: {len(shared)} port(s) consistent")

    return (passes, warns, fails, msgs)


def check_artifacts(content):
    msgs = []
    warns = 0
    fails = 0
    passes = 0

    checks = {
        "soft hyphen (\\xad)": "\xad",
        "zero-width space (U+200B)": "​",
        "soft hyphen (U+00AD)": "­",
        "CRLF line endings": "\r\n",
        "bullet char artifact (U+F0B7)": "",
    }

    found_any = False
    for label, char in checks.items():
        count = content.count(char)
        if count > 0:
            warns += 1
            msgs.append(f"[WARN] Found {count} instance(s) of {label}")
            found_any = True

    if not found_any:
        passes += 1
        msgs.append("[PASS] No PDF extraction artifacts detected")

    return (passes, warns, fails, msgs)


def check_stats(tables, content):
    msgs = []
    pin_tables = [t for t in tables if t["h2"] and "pin assignment" in t["h2"].lower()]
    if not pin_tables:
        pin_tables = [t for t in tables if "Name" in t["columns"]]
    mux_tables = [t for t in tables if t["h2"] and "multiplexing" in t["h2"].lower()]
    if not mux_tables:
        mux_tables = [t for t in tables if "AF0" in t["columns"]]

    msgs.append("Summary:")
    if pin_tables:
        pt = pin_tables[0]
        msgs.append(f"  Pin Assignment: {len(pt['rows'])} rows × {len(pt['columns'])} columns")

    if mux_tables:
        total_mux_pins = sum(len(t["rows"]) for t in mux_tables)
        msgs.append(f"  Multiplexing: {len(mux_tables)} port(s), {total_mux_pins} pin entries")

        total_af = 0
        filled_af = 0
        for t in mux_tables:
            for row in t["rows"]:
                for cell in row[1:]:
                    total_af += 1
                    if cell.strip():
                        filled_af += 1
        coverage = (filled_af / total_af * 100) if total_af > 0 else 0
        msgs.append(f"  AF coverage: {filled_af}/{total_af} cells filled ({coverage:.1f}%)")

    return (1, 0, 0, msgs)


# ═══════════════════════════════════════════════════════════════════════════
#  CLI wrapper
# ═══════════════════════════════════════════════════════════════════════════

def add_subparser(subparsers):
    parser = subparsers.add_parser("pin", help="PDF pin extraction tools")
    sub = parser.add_subparsers(dest="pin_command", required=True)

    extract = sub.add_parser("extract", help="Extract pin assignment and multiplexing tables")
    extract.add_argument("pdf", help="Path to the PDF datasheet")
    extract.add_argument("--pin-pages", type=str, default=None)
    extract.add_argument("--mux-pages", type=str, default=None)
    extract.add_argument("--ports", type=str, default=None)
    extract.add_argument("--mux-cols", type=int, default=None)
    extract.add_argument("-o", "--output", type=str, default=None)
    extract.add_argument("--chip-name", type=str, default=None)
    extract.add_argument("--flavor", type=str, default="lattice", choices=["lattice", "stream"])
    extract.add_argument("--package", type=str, default=None)

    search = sub.add_parser("extract-search", help="Search PDF for pin/mux pages")
    search.add_argument("pdf", help="Path to the PDF datasheet")

    verify = sub.add_parser("extract-verify", help="Verify extracted Markdown")
    verify.add_argument("markdown", help="Path to the Markdown file")
    verify.add_argument("--ports", type=str, default=None)
    verify.add_argument("--mux-cols", type=int, default=None)


def _parse_range(s):
    if s is None:
        return None
    parts = s.split("-")
    start, end = int(parts[0]), int(parts[-1])
    return list(range(start, end + 1))


def cmd_search(args):
    pin_pages, mux_pages = search_pages(args.pdf)
    print(f"Pin assignment pages: {pin_pages}")
    print(f"Multiplexing pages:   {mux_pages}")
    return 0


def cmd_extract(args):
    pin_pages, mux_pages = search_pages(args.pdf)
    pin_range = _parse_range(args.pin_pages) or pin_pages
    mux_range = _parse_range(args.mux_pages) or mux_pages

    if not pin_range:
        print("ERROR: Could not determine pin assignment pages. Use --pin-pages.", file=sys.stderr)
        return 1
    if not mux_range:
        print("ERROR: Could not determine multiplexing pages. Use --mux-pages.", file=sys.stderr)
        return 1

    port_names = args.ports.split(",") if args.ports else detect_ports(args.pdf, mux_range)
    if not port_names:
        print("ERROR: Could not detect port names. Use --ports.", file=sys.stderr)
        return 1

    if args.mux_cols:
        mux_col_count = args.mux_cols
        max_af = mux_col_count - 2
        mux_col_names = ["Pin"] + [f"AF{i}" for i in range(max_af + 1)]
    else:
        mux_col_count, mux_col_names, max_af = detect_mux_cols(args.pdf, mux_range)

    chip_name = args.chip_name or "MCU"
    pdf_basename = args.pdf.replace("\\", "/").split("/")[-1]
    json_path = args.output or f"{chip_name}_Pin_Assignment_and_Multiplexing.json"

    pin_df = extract_pin_assignment(args.pdf, pin_range, args.flavor)
    mux = extract_multiplexing(args.pdf, mux_range, port_names, mux_col_names, args.flavor)

    data = build_json(pin_df, mux, chip_name, pdf_basename, max_af)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {json_path}", file=sys.stderr)

    if args.package:
        safe_suffix = re.sub(r"[^A-Za-z0-9_\-]", "_", args.package)
        md_path = str(Path(json_path).with_suffix(f".{safe_suffix}.md"))
        write_package_markdown(data, args.package, md_path)
        print(f"Wrote {md_path}", file=sys.stderr)

    return 0


def cmd_verify(args):
    expected_ports = args.ports.split(",") if args.ports else None
    expected_cols = args.mux_cols

    try:
        with open(args.markdown, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[FAIL] File not found: {args.markdown}")
        return 2

    tables = parse_md_tables(content)

    all_results = []
    banner = f"Verifying: {args.markdown}"
    print(f"\n{'='*70}")
    print(f"  {banner}")
    print(f"{'='*70}")

    sections = [
        ("File", check_file(args.markdown)),
        ("Pin Assignment", check_pin_table(tables, content)),
        ("Multiplexing", check_mux_tables(tables, expected_ports, expected_cols, content)),
        ("Cross-Validation", check_cross_validation(tables, content)),
        ("Artifacts", check_artifacts(content)),
        ("Statistics", check_stats(tables, content)),
    ]

    total_p = total_w = total_f = 0
    for section, (p, w, f, msgs) in sections:
        total_p += p
        total_w += w
        total_f += f
        if f > 0:
            level = FAIL
        elif w > 0:
            level = WARN
        else:
            level = PASS
        print(f"\n── {section} {RESULT[level]}")
        for msg in msgs:
            print(f"   {msg}")

    print(f"\n{'='*70}")
    print(f"  TOTAL: {total_p} pass, {total_w} warning, {total_f} failure")
    if total_f > 0:
        print(f"  VERDICT: FAIL — {total_f} failure(s) need attention")
        print(f"{'='*70}\n")
        return 2
    elif total_w > 0:
        print(f"  VERDICT: WARN — {total_w} warning(s), manual review recommended")
        print(f"{'='*70}\n")
        return 1
    else:
        print(f"  VERDICT: PASS — all checks clean")
        print(f"{'='*70}\n")
        return 0


def run(args):
    if args.pin_command == "extract-search":
        return cmd_search(args)
    if args.pin_command == "extract":
        return cmd_extract(args)
    if args.pin_command == "extract-verify":
        return cmd_verify(args)
    return 1
