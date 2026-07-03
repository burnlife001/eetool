#!/usr/bin/env python3
"""
ATK-Logic signal classifier. Works from any directory.

Usage:
    python atk_classify.py <file.atkdl>                    # scan all channels
    python atk_classify.py <file.atkdl> --ch 0,1           # specific channels
    python atk_classify.py <file.atkdl> --start 0 --end 2s # time range
    python atk_classify.py <file.atkdl> --json             # JSON output

Output:
    Per-channel: edge count, frequency, period, duty cycle, signal type.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Support running from any directory — add parent (scripts/) to path
_parent_dir = Path(__file__).resolve().parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from ..lib.lib_reader import CaptureReader, parse_time


def _detect_bounce_pairs(edges: list, sample_rate_hz: int) -> dict | None:
    """Detect switching bounce artifact at edge transitions.

    Bounce pattern: at each signal transition, a pair of short pulses
    (< 1µs each) with total duration consistently aligning to a fixed
    sample count. This is a CMOS driver physical artifact, not a data
    feature.

    Returns dict with bounce info, or None if not detected.
    """
    short_edges = [e for e in edges if e.dur_ns < 500]

    if len(short_edges) < 4 or len(short_edges) % 2 != 0:
        return None

    # Group consecutive short edges into pairs (gap < 1 sample period)
    sample_ns = int(1e9 / sample_rate_hz)
    pairs = []
    i = 0
    while i < len(short_edges) - 1:
        e1, e2 = short_edges[i], short_edges[i + 1]
        gap = e2.t_ns - e1.t_ns - e1.dur_ns
        if gap <= sample_ns:
            total_ns = e1.dur_ns + e2.dur_ns
            total_samples = total_ns / sample_ns
            pairs.append((e1.dur_ns, e2.dur_ns, total_ns, total_samples))
            i += 2
        else:
            i += 1

    if len(pairs) < 2:
        return None

    # Check if pair total durations align to integer sample counts
    total_samples_list = [p[3] for p in pairs]
    avg_samples = sum(total_samples_list) / len(total_samples_list)
    # All pair totals must be within 1.5 samples of the average
    aligned = all(abs(s - avg_samples) < 1.5 for s in total_samples_list)

    if not aligned:
        return None

    # Bounce confirmed: all edge transitions have consistent bounce total
    pair_durations_ns = [p[1] for p in pairs]  # second glitch duration
    return {
        "pair_count": len(pairs),
        "avg_total_ns": sum(p[2] for p in pairs) / len(pairs),
        "avg_samples": round(avg_samples),
        "note": f"{len(pairs)} bounce pairs, {avg_samples:.0f}samp/{pairs[0][2]:.0f}ns avg per transition",
    }


def _first_edge_anomaly(real_edges: list) -> dict | None:
    """Check if the first long pulse is anomalous vs the rest.

    Returns dict with anomaly info, or None if no anomaly detected.
    """
    if len(real_edges) < 6:
        return None

    first_dur = real_edges[0].dur_ns
    first_level = real_edges[0].level

    # Compare first edge against same-level edges from index 2 onward
    # (skip index 1 since it may also be affected by startup)
    same_level_durs = []
    for i in range(2, len(real_edges)):
        if real_edges[i].level == first_level:
            same_level_durs.append(real_edges[i].dur_ns)

    if len(same_level_durs) < 3:
        return None

    avg_rest = sum(same_level_durs) / len(same_level_durs)
    if avg_rest == 0:
        return None

    ratio = first_dur / avg_rest

    # Flag if first edge differs by >3x from the steady-state average
    if ratio > 3.0 or ratio < 0.33:
        pct_dev = abs(ratio - 1) * 100
        return {
            "first_dur_ns": first_dur,
            "steady_avg_ns": int(avg_rest),
            "ratio": round(ratio, 1),
            "note": f"Startup transient: 1st pulse={first_dur/1e6:.1f}ms vs steady={avg_rest/1e6:.1f}ms ({pct_dev:.0f}% deviation)",
        }

    return None


def _pulse_stability(durations: list) -> dict | None:
    """Measure pulse duration stability within a level group.

    Returns stability metrics if the group is large enough, else None.
    """
    if len(durations) < 4:
        return None

    avg = sum(durations) / len(durations)
    if avg == 0:
        return None

    # Coefficient of variation: std/avg as percentage
    variance = sum((d - avg) ** 2 for d in durations) / len(durations)
    std = variance ** 0.5
    cv_pct = std / avg * 100

    return {
        "count": len(durations),
        "avg_ns": avg,
        "min_ns": min(durations),
        "max_ns": max(durations),
        "std_ns": std,
        "cv_pct": round(cv_pct, 3),
    }


def classify_signal(edges: list, sample_rate_hz: int) -> dict:
    """Analyze edge events and classify the signal type."""
    n = len(edges)
    if n <= 2:
        level = edges[0].level if edges else "?"
        return {
            "type": "static",
            "level": level,
            "edge_count": n,
            "note": f"Constant {'HIGH' if level == 1 else 'LOW'}, {n} edges",
        }

    glitch_ns = 1000  # edges < 1µs are glitches/transitions

    # ── Detect bounce artifact on ALL edges (before filtering) ──
    bounce_info = _detect_bounce_pairs(edges, sample_rate_hz)

    # Filter out glitch edges for classification
    real_edges = [e for e in edges if e.dur_ns >= glitch_ns]
    if not real_edges or len(real_edges) < 3:
        real_edges = edges  # fallback: too few edges after filtering

    # ── Collect level statistics (from real edges) ──
    high_count = sum(1 for e in real_edges if e.level == 1)
    low_count = len(real_edges) - high_count
    durations_high = [e.dur_ns for e in real_edges if e.level == 1]
    durations_low = [e.dur_ns for e in real_edges if e.level == 0]

    # ── Stability analysis: trim first and last edges ──
    # First may be startup transient, last may be capture truncation.
    # Strip one edge from each end for clean stability measurement.
    first_anomaly = _first_edge_anomaly(real_edges)

    if len(durations_high) >= 3:
        stable_high = durations_high[1:-1]  # trim both ends
    elif len(durations_high) >= 2:
        stable_high = durations_high[1:]     # trim first only
    else:
        stable_high = durations_high

    if len(durations_low) >= 3:
        stable_low = durations_low[1:-1]
    elif len(durations_low) >= 2:
        stable_low = durations_low[1:]
    else:
        stable_low = durations_low

    stability_high = _pulse_stability(stable_high)
    stability_low = _pulse_stability(stable_low)

    # ── Edge-to-edge periods ──
    edge_periods = []
    for i in range(1, len(real_edges)):
        p = real_edges[i].t_ns - real_edges[i - 1].t_ns
        if p > 0:
            edge_periods.append(p)

    rising_times = []
    for i in range(1, len(real_edges)):
        if real_edges[i].level == 1 and real_edges[i - 1].level == 0:
            rising_times.append(real_edges[i].t_ns)

    rising_periods = []
    if len(rising_times) >= 2:
        for i in range(1, len(rising_times)):
            p = rising_times[i] - rising_times[i - 1]
            if p > 0:
                rising_periods.append(p)

    periods_ns = edge_periods if len(edge_periods) >= 2 else rising_periods
    if len(periods_ns) < 2 and len(rising_periods) >= 2:
        periods_ns = rising_periods

    result = {
        "edge_count": n,
        "glitch_count": n - len(real_edges),
        "high_edges": high_count,
        "low_edges": low_count,
    }

    if bounce_info:
        result["bounce"] = bounce_info

    if durations_high:
        result["min_high_ns"] = min(durations_high)
        result["max_high_ns"] = max(durations_high)
        result["avg_high_ns"] = sum(durations_high) // len(durations_high)
    if durations_low:
        result["min_low_ns"] = min(durations_low)
        result["max_low_ns"] = max(durations_low)
        result["avg_low_ns"] = sum(durations_low) // len(durations_low)

    if periods_ns and len(periods_ns) >= 2:
        avg_period = sum(periods_ns) / len(periods_ns)
        min_period = min(periods_ns)
        max_period = max(periods_ns)
        freq_hz = 1e9 / avg_period if avg_period > 0 else 0

        result["period_avg_ns"] = avg_period
        result["period_min_ns"] = min_period
        result["period_max_ns"] = max_period
        result["frequency_hz"] = freq_hz

        # For regularity: trim 10% from each end to exclude partial edges
        sorted_periods = sorted(periods_ns)
        trim_start = len(sorted_periods) // 10
        trim_end = len(sorted_periods) - trim_start
        trimmed = sorted_periods[trim_start:trim_end] if trim_end > trim_start else sorted_periods

        if trimmed:
            trim_min = min(trimmed)
            trim_max = max(trimmed)
            trim_avg = sum(trimmed) / len(trimmed)
            spread_ratio = trim_max / trim_min if trim_min > 0 else 1e9
        else:
            spread_ratio = max_period / min_period if min_period > 0 else 1e9
            trim_avg = avg_period

        # ── Classification: Clock vs square_wave ──
        if spread_ratio < 1.1 and len(periods_ns) >= 3:
            if high_count > 0 and low_count > 0 and abs(high_count - low_count) <= 2:
                full_period_ns = trim_avg * 2
                full_freq = 1e9 / full_period_ns if full_period_ns > 0 else 0
            else:
                full_period_ns = trim_avg
                full_freq = 1e9 / trim_avg if trim_avg > 0 else 0

            result["frequency_hz"] = full_freq
            result["period_avg_ns"] = full_period_ns

            # Determine duty
            duty = 0
            if durations_high and durations_low:
                avg_high = sum(durations_high) / len(durations_high)
                avg_low = sum(durations_low) / len(durations_low)
                duty = avg_high / (avg_high + avg_low) * 100 if (avg_high + avg_low) > 0 else 50

            # ── Reclassify: clock if pulse stability < 0.5% AND bounce detected ──
            is_ultra_stable = False
            if stability_high and stability_low:
                is_ultra_stable = stability_high["cv_pct"] < 0.5 and stability_low["cv_pct"] < 0.5

            if is_ultra_stable and bounce_info:
                # Clock signal: ultra-stable pulses + consistent switching bounce
                result["type"] = "clock"
                result["duty_pct"] = duty
                parts = [f"Clock at {full_freq:.1f} Hz", f"{duty:.1f}% duty"]
                parts.append(f"HIGH CV={stability_high['cv_pct']:.2f}%")
                parts.append(f"LOW CV={stability_low['cv_pct']:.2f}%")
                parts.append(f"bounce={bounce_info['avg_samples']:.0f}samp")
                if first_anomaly:
                    parts.append(f"startup transient {first_anomaly['ratio']:.1f}x")
                result["note"] = ", ".join(parts)
            elif full_freq < 0.5:
                result["type"] = "slow_toggle"
                result["note"] = f"Slow periodic toggle at {full_freq:.3f} Hz (T={full_period_ns/1e6:.1f}ms)"
            elif full_freq < 200:
                result["type"] = "square_wave"
                result["duty_pct"] = duty
                note = f"Square wave at {full_freq:.1f} Hz, {duty:.1f}% duty"
                if first_anomaly:
                    note += f" {first_anomaly['note']}"
                if bounce_info:
                    note += f" ({bounce_info['note']})"
                result["note"] = note
            elif full_freq < 2000:
                result["type"] = "pwm"
                if durations_high:
                    avg_high = sum(durations_high) / len(durations_high)
                    duty = avg_high / full_period_ns * 100
                result["duty_pct"] = duty
                result["note"] = f"PWM at {full_freq:.1f} Hz, {duty:.1f}% duty"
            else:
                result["type"] = "clock"
                result["note"] = f"Clock at {full_freq/1000:.2f} kHz (T={full_period_ns:.1f}ns)"

        elif spread_ratio >= 3:
            # ── Check for PWM with varying duty but stable carrier ──
            # Pair consecutive alternating edges. When duty varies widely
            # (e.g. breathing LED), individual HIGH/LOW durations scatter
            # but the combined HIGH+LOW period stays stable.
            paired_periods = []
            i = 0
            while i < len(real_edges) - 1:
                e1, e2 = real_edges[i], real_edges[i + 1]
                if e1.level != e2.level:
                    paired_periods.append(e1.dur_ns + e2.dur_ns)
                    i += 2
                else:
                    i += 1
            if len(paired_periods) >= 3:
                avg_pair = sum(paired_periods) / len(paired_periods)
                if avg_pair > 0:
                    pair_var = sum((p - avg_pair) ** 2 for p in paired_periods) / len(paired_periods)
                    pair_cv = (pair_var ** 0.5) / avg_pair * 100
                    pair_freq = 1e9 / avg_pair
                    # Stable carrier + frequency in PWM range → PWM
                    if pair_cv < 30 and 0.5 < pair_freq < 2000:
                        duty = 0
                        if durations_high:
                            avg_high = sum(durations_high) / len(durations_high)
                            duty = avg_high / avg_pair * 100
                        result["frequency_hz"] = pair_freq
                        result["period_avg_ns"] = avg_pair
                        result["duty_pct"] = duty
                        result["type"] = "pwm"
                        note = f"PWM at {pair_freq:.1f} Hz, {duty:.1f}% duty"
                        if pair_cv > 15:
                            note += f" (paired period CV={pair_cv:.1f}%)"
                        result["note"] = note
                        return result
            # ── Not PWM, check for serial data ──
            if durations_low or durations_high:
                all_durs = durations_high + durations_low
                real_durs = [d for d in all_durs if d > glitch_ns * 2]
                if not real_durs:
                    real_durs = all_durs
                min_real = min(real_durs)
                if min_real > 0 and min_real < 100_000:
                    baud = int(1e9 / min_real)
                    std_list = [9600, 14400, 19200, 38400, 57600, 115200,
                                230400, 460800, 921600, 1000000, 2000000, 3000000]
                    best = min(std_list, key=lambda s: abs(s - baud))
                    if abs(best - baud) / baud < 0.15:
                        baud = best
                    result["baud_estimate"] = baud
                    result["type"] = "serial_data"
                    result["note"] = (
                        f"Serial data, ~{baud} baud (min bit={min_real}ns)"
                    )
                else:
                    result["type"] = "complex"
                    result["note"] = "Complex pattern, highly variable timing"
            else:
                result["type"] = "complex"
                result["note"] = "Complex signal pattern"
        else:
            result["type"] = "variable_pulse"
            result["note"] = f"Variable pulse train, ~{freq_hz:.0f} Hz avg"
    else:
        result["type"] = "burst"
        result["note"] = f"Single burst/pulse, {n} edges"

    return result


def format_result(ch: int, info: dict, fmt: str = "text") -> str:
    """Format analysis result for a channel."""
    if fmt == "json":
        return json.dumps({"ch": ch, **info}, indent=2, ensure_ascii=False)

    sep = "+" + "-" * 64 + "+"
    lines = []
    lines.append(sep)
    lines.append(f"| CH{ch:<5} {info.get('type', '?'):<56} |")
    if "note" in info:
        lines.append(f"| Note:    {info['note']:<54} |")
    lines.append(f"| Edges:   {info['edge_count']:<5} (high={info.get('high_edges','?')}, low={info.get('low_edges','?')}){' ' * (39 - len(str(info.get('low_edges','?'))))} |")

    if "frequency_hz" in info:
        f = info["frequency_hz"]
        if f >= 1_000_000:
            lines.append(f"|Frequency:   {f/1e6:.3f} MHz")
        elif f >= 1000:
            lines.append(f"|Frequency:   {f/1000:.2f} kHz")
        else:
            lines.append(f"|Frequency:   {f:.1f} Hz")

    if "period_avg_ns" in info:
        p = info["period_avg_ns"]
        if p >= 1_000_000_000:
            lines.append(f"|Period:      {p/1e9:.1f} s")
        elif p >= 1_000_000:
            lines.append(f"|Period:      {p/1e6:.1f} ms")
        elif p >= 1000:
            lines.append(f"|Period:      {p/1000:.1f} µs")
        else:
            lines.append(f"|Period:      {p:.1f} ns")

    if "duty_pct" in info:
        lines.append(f"|Duty cycle:  {info['duty_pct']:.1f}%")

    if "baud_estimate" in info:
        lines.append(f"|Baud est.:   {info['baud_estimate']:.0f}")

    if "bounce" in info:
        b = info["bounce"]
        lines.append(f"|Bounce:      {b['note']}")

    dur_keys = [
        ("min_high_ns", "Min HIGH"),
        ("max_high_ns", "Max HIGH"),
        ("avg_high_ns", "Avg HIGH"),
        ("min_low_ns", "Min LOW"),
        ("max_low_ns", "Max LOW"),
        ("avg_low_ns", "Avg LOW"),
    ]
    parts = []
    for key, label in dur_keys:
        if key in info:
            v = info[key]
            parts.append(f"{label}={v}ns")
    if parts:
        lines.append(f"|Durations:   {', '.join(parts)}")

    lines.append(sep)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="ATK-Logic universal waveform analyzer"
    )
    parser.add_argument("file", type=Path, help="Path to .atkdl capture file")
    parser.add_argument("--ch", default=None, help="Comma-separated channel IDs (default: auto-scan)")
    parser.add_argument("--start", default="0", help="Start time (ns/us/ms/s)")
    parser.add_argument("--end", default=None, help="End time")
    parser.add_argument("--max-events", type=int, default=5000)
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    reader = CaptureReader(str(args.file))
    info = reader.get_info()
    start_ns = parse_time(args.start)
    end_ns = parse_time(args.end) if args.end else None

    if args.json:
        out = {
            "file": str(args.file),
            "sample_rate_hz": info.sample_rate_hz,
            "channels": [],
        }

    # Determine which channels to analyze
    if args.ch:
        ch_ids = [int(c.strip()) for c in args.ch.split(",")]
    else:
        ch_ids = list(range(16))

    for cid in ch_ids:
        try:
            edges = list(reader.read_edges(cid, start_ns, end_ns, args.max_events))
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

        result = classify_signal(edges, info.sample_rate_hz)

        if args.json:
            out["channels"].append({"ch": cid, **result})
        else:
            print(format_result(cid, result))

    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
