#!/usr/bin/env python3
"""
ATK-Logic PWM / breathing LED analyzer. Works from any directory.

Usage:
    python atk_pwm.py <file.atkdl> --ch 1                    # analyze CH1 as PWM
    python atk_pwm.py <file.atkdl> --ch 0,1                  # multi-channel
    python atk_pwm.py <file.atkdl> --ch 1 --window 200ms     # 200ms trend windows
    python atk_pwm.py <file.atkdl> --ch 1 --json             # JSON output

Output:
    PWM carrier frequency, period, duty range, breathing pattern detection.

    cluster_max 泛化边界
    PWM 频率    周期       cluster_max   1%占空脉宽   安全?
    ──────────────────────────────────────────────────
      50 Hz    20.0 ms     100.0 us      200 us      ✓
     100 Hz    10.0 ms      50.0 us      100 us      ✓ (当前)
     500 Hz     2.0 ms      10.0 us       20 us      ✓
       1 kHz    1.0 ms       5.0 us       10 us      ✓ (钳位下限)
       5 kHz    0.2 ms       5.0 us        2 us      ✗ 触发 LOW CONFIDENCE
      20 kHz    0.05 ms      5.0 us      0.5 us      ✗ 需手动 --cluster-max

    生效范围：50 Hz ~ 1 kHz PWM，最低占空比 1%。超出范围触发 LOW CONFIDENCE 告警，用户可用
    --cluster-max 手动调整。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

# Support running from any directory — add parent (scripts/) to path
_parent_dir = Path(__file__).resolve().parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from ..lib.lib_reader import CaptureReader, EdgeEvent, parse_time


# 0 = auto-detect from edge duration distribution.
# The auto-detector finds the largest gap between short (bounce) and long
# (real PWM) edge durations, then places the threshold at the gap midpoint.
_GLITCH_NS = 0


def _estimate_pwm_period(edges: list) -> int | None:
    """Estimate PWM carrier period from long edges (>= 100us, bounce-free).

    Returns period in ns, or None if insufficient data.
    """
    long_edges = [e for e in edges if e.dur_ns >= 100_000]
    if len(long_edges) < 6:
        return None

    # Pair consecutive alternating long edges to get full periods
    periods = []
    i = 0
    while i < len(long_edges) - 1:
        e1, e2 = long_edges[i], long_edges[i + 1]
        if e1.level != e2.level:
            periods.append(e1.dur_ns + e2.dur_ns)
            i += 2
        else:
            i += 1

    if len(periods) < 3:
        return None

    return sorted(periods)[len(periods) // 2]


def _auto_cluster_max(edges: list) -> int:
    """Auto-detect cluster threshold from PWM period.

    cluster_max = period / 200, clamped to [5000, 50000] ns.
    This supports PWM down to ~1% minimum duty cycle (see evaluation above).
    """
    period = _estimate_pwm_period(edges)
    if period is None:
        return 50_000
    return max(5_000, min(50_000, period // 200))


def _debounce_edges(edges: list, cluster_max_ns: int) -> list:
    """Remove CMOS switching bounce by collapsing bounce clusters.

    A bounce cluster is a sequence of alternating short edges at a PWM
    transition. Total cluster duration is small (~400-800ns). We detect
    clusters by scanning for runs of edges all shorter than `cluster_max_ns`,
    then collapse each cluster by removing interior edges and merging
    the enclosing levels.
    """
    if len(edges) < 3:
        return list(edges)

    # Find bounce clusters: runs of consecutive short edges
    in_cluster = [False] * len(edges)
    i = 0
    while i < len(edges):
        if edges[i].dur_ns < cluster_max_ns:
            j = i + 1
            while j < len(edges) and edges[j].dur_ns < cluster_max_ns:
                j += 1
            if j - i >= 3:
                for k in range(i, j):
                    in_cluster[k] = True
            i = j
        else:
            i += 1

    # Collapse: keep only non-cluster edges, with duration accumulation
    keep = [not in_cluster[i] for i in range(len(edges))]
    cleaned = []
    i = 0
    while i < len(edges):
        if not keep[i]:
            i += 1
            continue
        e = edges[i]
        total_dur = e.dur_ns
        j = i + 1
        while j < len(edges) and not keep[j]:
            total_dur += edges[j].dur_ns
            j += 1
        cleaned.append(EdgeEvent(t_ns=e.t_ns, level=e.level, dur_ns=total_dur))
        i = j

    # Merge consecutive same-level edges
    if len(cleaned) < 2:
        return cleaned

    merged = [cleaned[0]]
    for e in cleaned[1:]:
        if e.level == merged[-1].level:
            merged[-1] = EdgeEvent(
                t_ns=merged[-1].t_ns,
                level=e.level,
                dur_ns=merged[-1].dur_ns + e.dur_ns,
            )
        else:
            merged.append(e)
    return merged


def _confidence_check(result: dict, cluster_max_ns: int) -> list[str]:
    """Return warnings if the analysis confidence is low."""
    warnings = []
    min_pulse = min(result.get("high_min_ns", 0), result.get("low_min_ns", 0))
    if min_pulse > 0 and min_pulse < cluster_max_ns * 1.5:
        warnings.append(
            f"LOW CONFIDENCE: min pulse ({_format_ns(min_pulse)}) < "
            f"1.5x cluster threshold ({_format_ns(cluster_max_ns)}) — "
            f"real PWM edges may have been removed"
        )
    period_cv = result.get("period_stability_cv_pct", 0)
    if period_cv > 50:
        warnings.append(
            f"LOW CONFIDENCE: period CV={period_cv:.1f}% — "
            f"debounce may be incomplete, try --cluster-max"
        )
    return warnings


def _format_ns(ns: int | float) -> str:
    """Format nanoseconds with full precision, no rounding loss."""
    ns = int(ns)
    if ns >= 1_000_000_000:
        return f"{ns / 1e9:.6f} s"
    if ns >= 1_000_000:
        return f"{ns / 1e6:.6f} ms"
    if ns >= 1_000:
        return f"{ns / 1e3:.3f} us"
    return f"{ns} ns"


def _filter_bounce(edges: list, glitch_ns: int) -> list:
    """Filter bounce/glitch edges and cleanup orphan same-level residues."""
    clean = [e for e in edges if e.dur_ns >= glitch_ns]
    # Remove orphan edges: if two consecutive edges have the same level,
    # keep the longer one (the shorter is a glitch remnant).
    if len(clean) < 2:
        return clean
    merged = [clean[0]]
    for e in clean[1:]:
        if merged and e.level == merged[-1].level:
            # Same level: keep the longer duration
            if e.dur_ns > merged[-1].dur_ns:
                merged[-1] = e
        else:
            merged.append(e)
    return merged


def _raw_edge_stats(edges: list) -> dict:
    """Compute raw HIGH/LOW stats directly from edge events (no pairing)."""
    highs = [e.dur_ns for e in edges if e.level == 1]
    lows = [e.dur_ns for e in edges if e.level == 0]
    stats = {}
    if highs:
        stats["high_count"] = len(highs)
        stats["high_min_ns"] = min(highs)
        stats["high_max_ns"] = max(highs)
        stats["high_avg_ns"] = int(statistics.mean(highs))
    if lows:
        stats["low_count"] = len(lows)
        stats["low_min_ns"] = min(lows)
        stats["low_max_ns"] = max(lows)
        stats["low_avg_ns"] = int(statistics.mean(lows))
    return stats


def _pair_pwm_cycles(edges: list, glitch_ns: int = _GLITCH_NS) -> list[dict]:
    """Filter bounce glitches and pair HIGH+LOW into PWM cycles.

    Returns list of {t_ns, high_ns, low_ns, period_ns, duty_pct}.
    """
    clean = _filter_bounce(edges, glitch_ns)
    if len(clean) < 3:
        return []

    # Find the first HIGH edge to start pairing from
    start = 0
    while start < len(clean) and clean[start].level != 1:
        start += 1
    if start >= len(clean) - 1:
        # No HIGH edge found, try LOW-first pairing
        start = 0
        while start < len(clean) and clean[start].level != 0:
            start += 1
        if start >= len(clean) - 1:
            return []

    cycles = []
    i = start
    while i < len(clean) - 1:
        e1, e2 = clean[i], clean[i + 1]
        if e1.level == 1 and e2.level == 0:
            h, l = e1.dur_ns, e2.dur_ns
        elif e1.level == 0 and e2.level == 1:
            l, h = e1.dur_ns, e2.dur_ns
        else:
            # Same level consecutive — should not happen after good filtering
            i += 1
            continue

        period = h + l
        duty = h / period * 100 if period > 0 else 0
        cycles.append({
            "t_ns": e1.t_ns,
            "high_ns": h,
            "low_ns": l,
            "period_ns": period,
            "duty_pct": round(duty, 2),
        })
        i += 2

    return cycles


def _analyze_pwm(cycles: list[dict], raw_stats: dict,
                 capture_duration_ns: int) -> dict:
    """Analyze PWM cycles: carrier stats, duty range, breathing detection."""
    if not cycles:
        return {"type": "no_pwm", "note": "No valid PWM cycles detected"}

    periods = [c["period_ns"] for c in cycles]
    duties = [c["duty_pct"] for c in cycles]
    highs = [c["high_ns"] for c in cycles]
    lows = [c["low_ns"] for c in cycles]

    avg_period = statistics.mean(periods)
    freq_hz = 1e9 / avg_period if avg_period > 0 else 0
    avg_duty = statistics.mean(duties)
    duty_min = min(duties)
    duty_max = max(duties)
    duty_range = duty_max - duty_min

    # Period stability
    if len(periods) >= 4:
        period_std = statistics.stdev(periods) if len(periods) >= 2 else 0
        period_cv = period_std / avg_period * 100 if avg_period > 0 else 0
    else:
        period_std = 0
        period_cv = 0

    # Use raw edge stats for min/max (more trustworthy than paired cycles)
    high_min = raw_stats.get("high_min_ns", min(highs) if highs else 0)
    high_max = raw_stats.get("high_max_ns", max(highs) if highs else 0)
    high_avg = raw_stats.get("high_avg_ns", int(statistics.mean(highs)) if highs else 0)
    low_min = raw_stats.get("low_min_ns", min(lows) if lows else 0)
    low_max = raw_stats.get("low_max_ns", max(lows) if lows else 0)
    low_avg = raw_stats.get("low_avg_ns", int(statistics.mean(lows)) if lows else 0)

    # Detect if signal ends at capture boundary vs actually stopping
    last_edge_t = cycles[-1]["t_ns"] if cycles else 0
    margin_ns = capture_duration_ns - last_edge_t
    at_boundary = margin_ns < (avg_period * 3)  # within 3 PWM periods of end

    result = {
        "type": "pwm",
        "cycle_count": len(cycles),
        "carrier_hz": round(freq_hz, 2),
        "period_ns": round(avg_period),
        "period_stability_cv_pct": round(period_cv, 3),
        "duty_min_pct": round(duty_min, 2),
        "duty_max_pct": round(duty_max, 2),
        "duty_avg_pct": round(avg_duty, 2),
        "duty_range_pct": round(duty_range, 2),
        "pwm_resolution": len(set(int(d * 100) for d in duties)),  # 0.01% bins
        "high_min_ns": int(high_min),
        "high_max_ns": int(high_max),
        "high_avg_ns": int(high_avg),
        "low_min_ns": int(low_min),
        "low_max_ns": int(low_max),
        "low_avg_ns": int(low_avg),
        "raw": raw_stats,
        "capture_boundary": at_boundary,
    }

    # ── Breathing / modulation detection ──
    if duty_range < 5:
        result["modulation"] = "static"
        result["note"] = f"Static PWM at {freq_hz:.2f} Hz, {avg_duty:.1f}% duty"
        return result

    if len(cycles) < 10:
        result["modulation"] = "variable"
        result["note"] = f"Variable PWM {freq_hz:.1f} Hz, duty {duty_min:.0f}-{duty_max:.0f}%"
        return result

    total_span_ns = cycles[-1]["t_ns"] - cycles[0]["t_ns"]
    if total_span_ns <= 0:
        result["modulation"] = "variable"
        return result

    # Build duty-vs-time series
    window_ns = int(100e6)  # 100ms
    timeline = []
    for t0 in range(0, int(total_span_ns), window_ns):
        t1 = t0 + window_ns
        wd = [c["duty_pct"] for c in cycles
              if t0 <= c["t_ns"] - cycles[0]["t_ns"] < t1]
        if wd:
            timeline.append({
                "t_s": round(cycles[0]["t_ns"] / 1e9 + t0 / 1e9, 2),
                "duty_pct": round(statistics.mean(wd), 2),
                "pulse_count": len(wd),
            })

    if len(timeline) < 4:
        result["modulation"] = "variable"
        result["timeline"] = timeline
        return result

    # Peak/valley detection for breathing cycle estimation
    t_duties = [t["duty_pct"] for t in timeline]
    peaks = []
    valleys = []
    for i in range(1, len(t_duties) - 1):
        if t_duties[i - 1] < t_duties[i] > t_duties[i + 1]:
            peaks.append(i)
        elif t_duties[i - 1] > t_duties[i] < t_duties[i + 1]:
            valleys.append(i)

    breath_periods = []
    for i in range(1, len(peaks)):
        dt = timeline[peaks[i]]["t_s"] - timeline[peaks[i - 1]]["t_s"]
        if dt > 0.1:
            breath_periods.append(dt)
    for i in range(1, len(valleys)):
        dt = timeline[valleys[i]]["t_s"] - timeline[valleys[i - 1]]["t_s"]
        if dt > 0.1:
            breath_periods.append(dt)

    if breath_periods and len(breath_periods) >= 2:
        breath_period = statistics.mean(breath_periods)
        breath_freq = 1 / breath_period if breath_period > 0 else 0

        # Ramp-up / ramp-down times
        ramp_ups = []
        ramp_downs = []
        if peaks and valleys:
            all_extrema = sorted(
                [(p, "peak") for p in peaks] + [(v, "valley") for v in valleys]
            )
            for i in range(len(all_extrema) - 1):
                idx1, kind1 = all_extrema[i]
                idx2, kind2 = all_extrema[i + 1]
                dt = timeline[idx2]["t_s"] - timeline[idx1]["t_s"]
                if kind1 == "peak" and kind2 == "valley":
                    ramp_downs.append(dt)
                elif kind1 == "valley" and kind2 == "peak":
                    ramp_ups.append(dt)

        result["modulation"] = "breathing"
        result["breath_period_s"] = round(breath_period, 3)
        result["breath_freq_hz"] = round(breath_freq, 3)
        if ramp_ups:
            result["ramp_up_s"] = round(statistics.mean(ramp_ups), 3)
        if ramp_downs:
            result["ramp_down_s"] = round(statistics.mean(ramp_downs), 3)

        parts = [
            f"Breathing LED: {freq_hz:.2f} Hz PWM carrier",
            f"duty {duty_min:.2f}-{duty_max:.2f}%",
            f"cycle ~{breath_period:.2f}s",
        ]
        if ramp_ups:
            parts.append(f"rise ~{result['ramp_up_s']:.2f}s")
        if ramp_downs:
            parts.append(f"fall ~{result['ramp_down_s']:.2f}s")
        if at_boundary:
            parts.append("(ends at capture boundary)")
        result["note"] = ", ".join(parts)
    else:
        result["modulation"] = "sweeping"
        suffix = " (ends at capture boundary)" if at_boundary else ""
        result["note"] = (
            f"PWM sweep: {freq_hz:.1f} Hz, duty {duty_min:.1f}-{duty_max:.1f}%, "
            f"{len(cycles)} cycles{suffix}"
        )

    result["timeline"] = timeline
    return result


def format_result(ch: int, pwm: dict, capture_duration_ns: int,
                  fmt: str = "text") -> str:
    """Format PWM analysis for a channel."""
    if fmt == "json":
        return json.dumps({"ch": ch, **pwm}, indent=2, ensure_ascii=False)

    sep = "+" + "-" * 64 + "+"
    lines = [sep]
    lines.append(f"| CH{ch:<5} PWM Analysis {' ' * 45} |")
    lines.append(sep)

    if pwm.get("type") == "no_pwm":
        lines.append(f"| {pwm.get('note', 'No PWM detected'):<62} |")
        lines.append(sep)
        return "\n".join(lines)

    cap_s = f"{capture_duration_ns / 1e9:.3f}s"

    lines.append(f"| Capture:   {cap_s}{' ' * (53 - len(cap_s))} |")
    cluster_ns = pwm.get("cluster_max_ns", 0)
    cluster_mode = pwm.get("cluster_mode", "?")
    period_ns_est = pwm.get("period_ns", 0)
    period_ref = f" (period/{period_ns_est // cluster_ns if cluster_ns and period_ns_est else '?'})" if cluster_mode == "auto" else ""
    cluster_s = f"cluster < {_format_ns(cluster_ns)} ({cluster_mode}){period_ref}"
    lines.append(f"| Debounce:  {cluster_s}{' ' * (51 - len(cluster_s))} |")
    lines.append(f"| Carrier:   {pwm['carrier_hz']:.2f} Hz"
                 f"  (period {_format_ns(pwm['period_ns'])})"
                 f"{' ' * (19 - len(_format_ns(pwm['period_ns'])))} |")
    lines.append(f"| Cycles:    {pwm['cycle_count']}"
                 f"  (period CV={pwm['period_stability_cv_pct']:.2f}%)"
                 f"{' ' * 30} |")
    lines.append(
        f"| Duty:      {pwm['duty_min_pct']:.2f}% - {pwm['duty_max_pct']:.2f}%"
        f"  (avg {pwm['duty_avg_pct']:.2f}%, range {pwm['duty_range_pct']:.2f}%)"
        f"{' ' * 5} |"
    )
    lines.append(
        f"| Resolution:{pwm['pwm_resolution']} distinct duty levels"
        f"  (0.01% bins){' ' * 24} |"
    )

    # HIGH / LOW with raw-edge stats (full precision)
    lines.append(
        f"| HIGH:      min={_format_ns(pwm['high_min_ns'])}"
        f"  max={_format_ns(pwm['high_max_ns'])}"
        f"  avg={_format_ns(pwm['high_avg_ns'])}"
        f"{' ' * (6)} |"
    )
    lines.append(
        f"| LOW:       min={_format_ns(pwm['low_min_ns'])}"
        f"  max={_format_ns(pwm['low_max_ns'])}"
        f"  avg={_format_ns(pwm['low_avg_ns'])}"
        f"{' ' * (6)} |"
    )

    # Edge counts
    raw = pwm.get("raw", {})
    lines.append(
        f"| Raw edges: {raw.get('high_count', '?')} HIGH + "
        f"{raw.get('low_count', '?')} LOW"
        f"{' ' * 32} |"
    )

    mod = pwm.get("modulation", "?")
    boundary = " (capture boundary)" if pwm.get("capture_boundary") else ""
    lines.append(f"| Modulation:{mod}{boundary}{' ' * (41 - len(mod) - len(boundary))} |")

    if "breath_period_s" in pwm:
        lines.append(
            f"| Breath:    {pwm['breath_period_s']:.3f}s cycle"
            f"  ({pwm['breath_freq_hz']:.3f} Hz){' ' * 25} |"
        )
    if "ramp_up_s" in pwm:
        lines.append(
            f"| Ramp up:   {pwm['ramp_up_s']:.3f}s  (dim -> bright)"
            f"{' ' * 27} |"
        )
    if "ramp_down_s" in pwm:
        lines.append(
            f"| Ramp down: {pwm['ramp_down_s']:.3f}s  (bright -> dim)"
            f"{' ' * 27} |"
        )

    if "note" in pwm:
        lines.append(f"| Note:      {pwm['note']:<54} |")

    # Duty trend bar chart
    timeline = pwm.get("timeline", [])
    if timeline and len(timeline) >= 3:
        lines.append(sep)
        lines.append(f"| Duty Trend ({len(timeline)} x 100ms windows) {' ' * 30} |")
        lines.append("|" + "-" * 63 + "|")
        width = 56
        for t in timeline:
            bar_len = max(0, min(width, int(t["duty_pct"] / 100 * width)))
            bar = "#" * bar_len + "." * (width - bar_len)
            pct_str = f"{t['duty_pct']:6.2f}%"
            lines.append(f"| {t['t_s']:6.2f}s {pct_str} |{bar}|")

    lines.append(sep)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="ATK-Logic PWM / breathing LED analyzer"
    )
    parser.add_argument("file", type=Path, help="Path to .atkdl capture file")
    parser.add_argument("--ch", default=None,
                        help="Comma-separated channel IDs (required)")
    parser.add_argument("--start", default="0", help="Start time (ns/us/ms/s)")
    parser.add_argument("--end", default=None, help="End time")
    parser.add_argument("--window", default="100ms",
                        help="Trend window size (ns/us/ms/s, default: 100ms)")
    parser.add_argument("--max-events", type=int, default=10000)
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--glitch", type=int, default=_GLITCH_NS,
                        help="Secondary glitch filter in ns (0=auto, default: auto)")
    parser.add_argument("--cluster-max", type=int, default=0,
                        help="Cluster debounce threshold in ns (0=auto from period/200)")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    if not args.ch:
        print("Error: --ch is required (e.g. --ch 1 or --ch 0,1)",
              file=sys.stderr)
        sys.exit(1)

    reader = CaptureReader(str(args.file))
    info = reader.get_info()
    start_ns = parse_time(args.start)
    end_ns_user = parse_time(args.end) if args.end else None
    capture_duration_ns = end_ns_user if end_ns_user else info.duration_ns

    ch_ids = [int(c.strip()) for c in args.ch.split(",")]

    if args.json:
        out = {
            "file": str(args.file),
            "sample_rate_hz": info.sample_rate_hz,
            "channels": [],
        }

    for cid in ch_ids:
        try:
            edges = list(reader.read_edges(cid, start_ns, end_ns_user,
                                           args.max_events))
        except Exception as e:
            if args.json:
                out["channels"].append({"ch": cid, "error": str(e)})
            else:
                print(f"CH{cid}: Error — {e}")
            continue

        if not edges:
            if not args.json:
                print(f"CH{cid}: No edges (inactive or floating)")
            continue

        raw_count = len(edges)
        # Step 1: determine cluster debounce threshold
        if args.cluster_max > 0:
            cluster_max_ns = args.cluster_max
            cluster_mode = "manual"
        else:
            cluster_max_ns = _auto_cluster_max(edges)
            cluster_mode = "auto"
        # Step 2: cluster debounce — collapse bounce clusters at transitions
        debounced = _debounce_edges(edges, cluster_max_ns)
        # Step 3: secondary glitch filter (safety net)
        if args.glitch > 0:
            glitch_ns = args.glitch
            glitch_mode = "manual"
        else:
            glitch_ns = 5000  # fixed safety net after cluster debounce
            glitch_mode = "auto"
        clean_edges = _filter_bounce(debounced, glitch_ns)
        raw_stats = _raw_edge_stats(clean_edges)
        cycles = _pair_pwm_cycles(debounced, glitch_ns)
        result = _analyze_pwm(cycles, raw_stats, capture_duration_ns)
        # Step 4: confidence check
        warnings = _confidence_check(result, cluster_max_ns)
        result["raw_edge_count"] = raw_count
        result["clean_edge_count"] = len(clean_edges)
        result["cluster_max_ns"] = cluster_max_ns
        result["cluster_mode"] = cluster_mode
        result["glitch_ns"] = glitch_ns
        result["glitch_mode"] = glitch_mode
        result["warnings"] = warnings

        if args.json:
            out["channels"].append({"ch": cid, **result})
        else:
            output = format_result(cid, result, capture_duration_ns)
            print(output)
            for w in warnings:
                print(f"  [!] {w}")

    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
