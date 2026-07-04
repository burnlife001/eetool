"""Tests for ``eetool.capture.lib.lib_config_sync``.

All tests run against a temporary ``set.ini`` so the user's real
``%APPDATA%/ALIENTEK/ATK-LogicView/set.ini`` is never touched.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from eetool.capture.lib.lib_config_sync import (
    read_set_ini_sampling,
    sync_set_ini,
    update_set_ini_sampling,
)


SAMPLE_SET_INI = """\
[DL16]
channelsSet=[{"id":0,"enable":true},{"id":1,"enable":true},{"id":2,"enable":false}]
settingData={"RLE":false,"setHz":20000000,"setTime":50000,"thresholdLevel":1.5}
stageTriggerData={}
serialTriggerData={}
"""


@pytest.fixture
def set_ini_path(tmp_path: Path) -> Path:
    """Write a minimal set.ini into a temp dir and return its path."""
    p = tmp_path / "set.ini"
    p.write_text(SAMPLE_SET_INI, encoding="utf-8")
    return p


# ---------- update_set_ini_sampling: duration only ----------


def test_update_set_ini_duration_writes_set_time(set_ini_path: Path):
    """Regression: GUI reads setTime on startup; CLI must keep it in sync."""
    assert update_set_ini_sampling(duration_s=5.0, set_ini_path=set_ini_path)
    data = read_set_ini_sampling(set_ini_path)
    assert data["setTime_ms"] == 5000  # ms
    # Other fields untouched
    assert data["setHz"] == 20000000
    assert data["thresholdLevel"] == 1.5


def test_update_set_ini_duration_rounds_to_millisecond(set_ini_path: Path):
    update_set_ini_sampling(duration_s=1.234, set_ini_path=set_ini_path)
    data = read_set_ini_sampling(set_ini_path)
    assert data["setTime_ms"] == 1234


def test_update_set_ini_duration_preserves_other_setting_data(set_ini_path: Path):
    """setTime update must not erase RLE or other settingData fields."""
    update_set_ini_sampling(duration_s=2.0, set_ini_path=set_ini_path)
    text = set_ini_path.read_text(encoding="utf-8")
    m = re.search(r"settingData=(\{.*?\})", text)
    assert m, "settingData line missing"
    obj = json.loads(m.group(1))
    assert obj["RLE"] is False
    assert obj["setHz"] == 20000000
    assert obj["setTime"] == 2000
    assert obj["thresholdLevel"] == 1.5


def test_update_set_ini_no_change_returns_false(set_ini_path: Path):
    """If setTime already matches, the writer reports no-op and leaves file alone."""
    # 50000 ms = 50.0 s already in fixture; request same value.
    assert update_set_ini_sampling(duration_s=50.0, set_ini_path=set_ini_path) is False


def test_update_set_ini_all_none_returns_false(set_ini_path: Path):
    assert update_set_ini_sampling(set_ini_path=set_ini_path) is False


def test_update_set_ini_combined_hz_threshold_duration(set_ini_path: Path):
    """All three sampling params can be written in one call."""
    assert update_set_ini_sampling(
        set_hz=10_000_000, threshold=2.5, duration_s=7.5, set_ini_path=set_ini_path
    )
    data = read_set_ini_sampling(set_ini_path)
    assert data["setHz"] == 10_000_000
    assert data["thresholdLevel"] == 2.5
    assert data["setTime_ms"] == 7500


def test_update_set_ini_missing_file_returns_false(tmp_path: Path):
    """Missing set.ini: graceful no-op, no exception."""
    p = tmp_path / "does_not_exist.ini"
    assert update_set_ini_sampling(duration_s=1.0, set_ini_path=p) is False


# ---------- sync_set_ini: duration_s end-to-end ----------


def test_sync_set_ini_pushes_duration_to_set_time(set_ini_path: Path):
    """The whole point of the bug fix: ``--duration 5s`` must end up as
    ``setTime=5000`` in settingData, not be silently dropped."""
    result = sync_set_ini(duration_s=5.0, set_ini_path=set_ini_path)
    assert result["synced"] is True
    assert any("setTime=5000ms" in c for c in result["changes"])
    data = read_set_ini_sampling(set_ini_path)
    assert data["setTime_ms"] == 5000


def test_sync_set_ini_dry_run_does_not_modify(set_ini_path: Path):
    text_before = set_ini_path.read_text(encoding="utf-8")
    result = sync_set_ini(duration_s=2.0, set_ini_path=set_ini_path, dry_run=True)
    assert result["synced"] is False
    assert "setTime_ms" not in result["changes"][0] or "dry-run" in result["changes"][0]
    # File untouched
    assert set_ini_path.read_text(encoding="utf-8") == text_before


def test_sync_set_ini_backs_up_on_change(set_ini_path: Path):
    sync_set_ini(duration_s=5.0, set_ini_path=set_ini_path)
    backups = list(set_ini_path.parent.glob("set.ini.*.bak"))
    assert backups, "expected a backup .bak file to be created"


def test_sync_set_ini_no_change_no_backup(set_ini_path: Path):
    """When the desired duration matches set.ini (50.0 s → 50000 ms), don't
    create spurious backups."""
    sync_set_ini(duration_s=50.0, set_ini_path=set_ini_path)
    backups = list(set_ini_path.parent.glob("set.ini.*.bak"))
    assert not backups