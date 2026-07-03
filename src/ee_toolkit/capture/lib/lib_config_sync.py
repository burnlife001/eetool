"""
ATK-Logic Capture — set.ini read/write for capture parameters.

config.ini is the source of truth for paths only ([atk-logic] section).
Capture parameters (channels, setHz, thresholdLevel) are set explicitly
by the caller — no config.ini [capture] section exists.

Usage:
    from lib.lib_config_sync import sync_set_ini, get_set_ini_params

    # Read current set.ini params (via adapter)
    params = get_set_ini_params()
    # → {'channels': [0, 1], 'setHz': 20000000, 'thresholdLevel': 1.5}

    # Write desired params to set.ini (backs up first if changes needed)
    sync_set_ini(channels=[0, 1, 2, 3], set_hz=20000000, threshold=1.5)
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .. import _config
from .._config import APPDATA_ATK, get_gui_dir


# ── set.ini INI parsing ─────────────────────────────────────────────────────

def _ini_section(text: str, section: str) -> dict[str, str]:
    """Parse a single INI section into a dict of key → value (case-insensitive keys)."""
    result: dict[str, str] = {}
    pattern = re.compile(
        r"^\s*\[" + re.escape(section) + r"\]\s*$", re.IGNORECASE
    )
    in_section = False
    for line in text.splitlines():
        if pattern.match(line):
            in_section = True
            continue
        if in_section:
            if line.strip().startswith("[") and line.strip().endswith("]"):
                break  # next section
            if "=" in line:
                key, _, val = line.partition("=")
                result[key.strip().lower()] = val.strip()
    return result


# ── reading set.ini (with adapter) ──────────────────────────────────────────

def read_set_ini_channels(set_ini_path: Path | None = None) -> list[int]:
    """Read set.ini channelsSet, return list of enabled channel IDs.

    Adapter: channelsSet (JSON array of channel objects) → flat list of ints.
    """
    path = set_ini_path or APPDATA_ATK / "set.ini"
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    section = _ini_section(text, "DL16")

    raw = section.get("channelsset", "")
    if not raw:
        return []

    try:
        channels = json.loads(raw)
    except json.JSONDecodeError:
        return []

    return [ch["id"] for ch in channels if ch.get("enable")]


def read_set_ini_sampling(set_ini_path: Path | None = None) -> dict:
    """Read set.ini settingData, return normalised sampling params.

    Adapter: settingData (JSON object with many keys) → flat dict with
    setHz and thresholdLevel.
    """
    path = set_ini_path or APPDATA_ATK / "set.ini"
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    section = _ini_section(text, "DL16")

    raw = section.get("settingdata", "")
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    result: dict = {}
    if "setHz" in data:
        result["setHz"] = data["setHz"]
    if "thresholdLevel" in data:
        result["thresholdLevel"] = data["thresholdLevel"]
    return result


def get_set_ini_params(set_ini_path: Path | None = None) -> dict:
    """Read set.ini and return normalised capture params.

    Returns dict with keys: channels (list[int]), setHz (int), thresholdLevel (float).
    Partial return if some keys are missing.
    """
    result: dict = {}
    ch = read_set_ini_channels(set_ini_path)
    if ch:
        result["channels"] = ch
    sampling = read_set_ini_sampling(set_ini_path)
    result.update(sampling)
    return result


# ── comparison ──────────────────────────────────────────────────────────────

def params_differ(desired: dict, actual: dict) -> dict:
    """Return a dict of only the keys whose values differ.

    Returns empty dict when everything matches.
    """
    diff: dict = {}
    for key in desired:
        if key not in actual or desired[key] != actual[key]:
            diff[key] = desired[key]
    return diff


# ── backup ──────────────────────────────────────────────────────────────────

def backup_set_ini(set_ini_path: Path | None = None) -> Path | None:
    """Create a timestamped backup of set.ini. Returns backup path or None."""
    path = set_ini_path or APPDATA_ATK / "set.ini"
    if not path.exists():
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(f".ini.{ts}.bak")
    shutil.copy2(path, backup)
    return backup


# ── update set.ini ──────────────────────────────────────────────────────────

def _patch_json_field(text: str, key: str, patch_fn) -> str:
    """Locate `key=<JSON>` in INI text, parse JSON, apply patch_fn, and
    replace the JSON value in-place. Returns new text (unchanged if key not found)."""
    tag = f"{key}="
    pos = text.find(tag)
    if pos < 0:
        return text

    start = pos + len(tag)
    end = start
    depth = 0
    while end < len(text):
        ch = text[end]
        if ch in ("[", "{"):
            depth += 1
        elif ch in ("]", "}"):
            depth -= 1
            if depth == 0:
                end += 1
                break
        end += 1

    try:
        obj = json.loads(text[start:end])
    except json.JSONDecodeError:
        return text

    patched = patch_fn(obj)
    new_json = json.dumps(patched, separators=(",", ":"), ensure_ascii=False)
    return text[:start] + new_json + text[end:]


def update_set_ini_channels(
    channels: list[int], set_ini_path: Path | None = None
) -> bool:
    """Enable exactly the channels in `channels`, disable all others in set.ini."""
    path = set_ini_path or APPDATA_ATK / "set.ini"
    if not path.exists():
        print(f"  [sync] set.ini not found at {path}")
        return False

    text = path.read_text(encoding="utf-8")

    def _patch(ch_list):
        for entry in ch_list:
            entry["enable"] = entry.get("id") in channels
        return ch_list

    new_text = _patch_json_field(text, "channelsSet", _patch)
    if new_text == text:
        return False  # unchanged

    path.write_text(new_text, encoding="utf-8")
    print(f"  [sync] channelsSet updated → enabled={channels}")
    return True


def update_set_ini_sampling(
    set_hz: int | None = None,
    threshold: float | None = None,
    set_ini_path: Path | None = None,
) -> bool:
    """Update setHz and/or thresholdLevel in set.ini settingData."""
    if set_hz is None and threshold is None:
        return False

    path = set_ini_path or APPDATA_ATK / "set.ini"
    if not path.exists():
        print(f"  [sync] set.ini not found at {path}")
        return False

    text = path.read_text(encoding="utf-8")

    def _patch(data):
        if set_hz is not None:
            data["setHz"] = set_hz
        if threshold is not None:
            data["thresholdLevel"] = threshold
        return data

    new_text = _patch_json_field(text, "settingData", _patch)
    if new_text == text:
        return False  # unchanged

    path.write_text(new_text, encoding="utf-8")
    parts = []
    if set_hz is not None:
        parts.append(f"setHz={set_hz}")
    if threshold is not None:
        parts.append(f"thresholdLevel={threshold}")
    print(f"  [sync] settingData updated → {', '.join(parts)}")
    return True


# ── main entry point ────────────────────────────────────────────────────────

def sync_set_ini(
    channels: list[int] | None = None,
    set_hz: int | None = None,
    threshold: float | None = None,
    set_ini_path: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Write capture parameters to set.ini (backs up first if changes needed).

    All params are explicit — there is no config.ini [capture] section.
    Only provided params are checked and updated; omitted params are left as-is.

    Args:
        channels: Enabled channel IDs (e.g. [0, 1, 2, 3]).
        set_hz: Sample rate in Hz (e.g. 20_000_000).
        threshold: Threshold voltage (e.g. 1.5).
        set_ini_path: Path to set.ini (default: APPDATA_ATK/set.ini).
        dry_run: If True, report differences but do not modify set.ini.

    Returns:
        dict with keys: 'synced' (bool), 'backup' (Path|None),
        'changes' (list[str]), 'desired' (dict), 'actual' (dict).
    """
    path = set_ini_path or APPDATA_ATK / "set.ini"

    # Build desired dict from explicit args only
    desired: dict = {}
    if channels is not None:
        desired["channels"] = channels
    if set_hz is not None:
        desired["setHz"] = set_hz
    if threshold is not None:
        desired["thresholdLevel"] = threshold

    if not desired:
        print("  [sync] no params provided, nothing to sync")
        return {
            "synced": False, "backup": None, "changes": [],
            "desired": desired, "actual": {},
        }

    # Read current set.ini values
    actual = get_set_ini_params(path)

    print(f"  [sync] desired:  {desired}")
    print(f"  [sync] actual:   {actual}")

    # Compare
    diff = params_differ(desired, actual)
    if not diff:
        print(f"  [sync] already in sync, no changes needed")
        return {
            "synced": True, "backup": None, "changes": [],
            "desired": desired, "actual": actual,
        }

    print(f"  [sync] differences: {diff}")

    if dry_run:
        return {
            "synced": False, "backup": None,
            "changes": [f"{k} → {v} (dry-run)" for k, v in diff.items()],
            "desired": desired, "actual": actual,
        }

    # Backup
    backup_path = backup_set_ini(path)
    if backup_path:
        print(f"  [sync] backed up → {backup_path}")

    # Update
    changes: list[str] = []

    if "channels" in diff:
        ok = update_set_ini_channels(desired["channels"], path)
        if ok:
            changes.append(f"channels → {desired['channels']}")

    sampling_changed = any(k in diff for k in ("setHz", "thresholdLevel"))
    if sampling_changed:
        ok = update_set_ini_sampling(
            set_hz=desired.get("setHz"),
            threshold=desired.get("thresholdLevel"),
            set_ini_path=path,
        )
        if ok:
            parts = []
            if "setHz" in diff:
                parts.append(f"setHz={desired['setHz']}")
            if "thresholdLevel" in diff:
                parts.append(f"thresholdLevel={desired['thresholdLevel']}")
            changes.append(", ".join(parts))

    print(f"  [sync] done — {len(changes)} field(s) updated")

    return {
        "synced": True,
        "backup": backup_path,
        "changes": changes,
        "desired": desired,
        "actual": actual,
    }
