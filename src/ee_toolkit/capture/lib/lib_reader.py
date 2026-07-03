"""
ATK-Logic file format reader.

Supports:
  - .atkdl (zip): JSON-like INI metadata + per-channel binary data
  - .bin: raw binary with 64-byte header
  - .csv: text export

Reads edge events (RLE) rather than per-sample data.
"""

from __future__ import annotations

from .. import _bootstrap

import io
import re
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class CaptureInfo:
    channels: list[dict]
    sample_rate_hz: int
    total_samples: int
    duration_ns: int
    capture_time: str | None
    file_format: str


@dataclass
class EdgeEvent:
    t_ns: int
    level: int
    dur_ns: int


# ---------------------------------------------------------------------------
# Time parsing
# ---------------------------------------------------------------------------
_TIME_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(ns|us|ms|s)?$", re.IGNORECASE)


def parse_time(s: str) -> int:
    m = _TIME_RE.match(s.strip())
    if not m:
        raise ValueError(f"Invalid time format: {s!r}")
    val = float(m.group(1))
    unit = (m.group(2) or "ns").lower()
    multipliers = {"ns": 1, "us": 1_000, "ms": 1_000_000, "s": 1_000_000_000}
    return int(val * multipliers[unit])


# ---------------------------------------------------------------------------
# .atkdl reader
# ---------------------------------------------------------------------------

class AtkdlReader:
    """Reader for ATK-Logic .atkdl (zip) files."""

    BLOCK_MAX_SIZE = 1024 * 1024  # 1 MiB per block
    NODE_DATA_SIZE = 64

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._zip: zipfile.ZipFile | None = None
        self._meta: dict = {}
        self._channel_names: list[str] = []
        self._channel_offsets: list[int] = []
        self._channel_max_samples: list[int] = []
        self._channel_tog_values: list[list[tuple[int, int]]] = []
        self._sample_rate_khz: int = 0
        self._sampling_depth: int = 0
        self._trigger_depth: int = 0
        self._multiply_ns: int = 0  # ns per sample
        self._open()

    def _open(self) -> None:
        self._zip = zipfile.ZipFile(self.path, "r")

        # Global metadata
        global_ini = self._read_text("channel.ini")
        for line in global_ini.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                self._meta[k.strip()] = v.strip()

        self._sample_rate_khz = int(self._meta.get("SamplingFrequency", 0))
        self._sampling_depth = int(self._meta.get("SamplingDepth", 0))
        self._trigger_depth = int(self._meta.get("TriggerSamplingDepth", 0))
        if self._sample_rate_khz > 0:
            self._multiply_ns = 1_000_000 // self._sample_rate_khz

        # Per-channel metadata
        channel_dirs = sorted(
            {n.split("/")[0] for n in self._zip.namelist() if "/" in n},
            key=lambda x: int(x),
        )
        for ch_dir in channel_dirs:
            ch_ini = self._read_text(f"{ch_dir}/channel.ini")
            lines = ch_ini.splitlines()
            if len(lines) < 3:
                continue
            name = lines[0].strip()
            offset = int(lines[1].strip())
            max_sample = int(lines[2].strip())

            # tog/value pairs (one per Node)
            tog_values = []
            for line in lines[3:]:
                line = line.strip()
                if "," in line:
                    parts = line.split(",", 1)
                    if len(parts) == 2:
                        tog_values.append((int(parts[0]), int(parts[1])))

            self._channel_names.append(name)
            self._channel_offsets.append(offset)
            self._channel_max_samples.append(max_sample)
            self._channel_tog_values.append(tog_values)

    def _read_text(self, name: str) -> str:
        if self._zip is None:
            raise RuntimeError("Zip not open")
        data = self._zip.read(name)
        # Try UTF-8 first, fall back to GBK for older files
        for enc in ("utf-8", "gbk"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    def _read_channel_raw(self, channel: int) -> Iterator[bytes]:
        """Yield raw 1-MiB blocks for a channel in order."""
        if self._zip is None:
            raise RuntimeError("Zip not open")

        tog_values = self._channel_tog_values[channel]
        ch_dir = str(channel)

        for node_idx, (tog, value) in enumerate(tog_values):
            for block_idx in range(self.NODE_DATA_SIZE):
                bin_name = f"{ch_dir}/{node_idx}-{block_idx}.bin"
                if bin_name in self._zip.namelist():
                    yield self._zip.read(bin_name)
                else:
                    # Compressed block: all same value
                    bit = 1 if (value & (1 << block_idx)) else 0
                    yield bytes([bit * 0xFF] * self.BLOCK_MAX_SIZE)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_info(self) -> CaptureInfo:
        channels = [
            {"id": i, "name": name}
            for i, name in enumerate(self._channel_names)
        ]
        sr_hz = self._sample_rate_khz * 1000
        duration_ns = self._sampling_depth * self._multiply_ns
        return CaptureInfo(
            channels=channels,
            sample_rate_hz=sr_hz,
            total_samples=self._sampling_depth,
            duration_ns=duration_ns,
            capture_time=None,
            file_format="source",
        )

    def read_edges(
        self,
        channel: int,
        start_ns: int = 0,
        end_ns: int | None = None,
        max_events: int = 10_000,
    ) -> list[EdgeEvent]:
        """Return edge-change events for a channel in [start_ns, end_ns]."""
        if channel < 0 or channel >= len(self._channel_names):
            raise ValueError(f"Invalid channel {channel}")

        if end_ns is None:
            end_ns = self._sampling_depth * self._multiply_ns

        start_sample = start_ns // self._multiply_ns
        end_sample = min(end_ns // self._multiply_ns, self._channel_max_samples[channel])
        offset = self._channel_offsets[channel]
        start_sample += offset
        end_sample += offset

        if start_sample >= end_sample:
            return []

        events: list[EdgeEvent] = []
        current_level: int | None = None
        seg_start_ns: int | None = None
        sample = start_sample

        for block in self._read_channel_raw(channel):
            if sample >= end_sample:
                break
            block_start_sample = sample
            block_end_sample = block_start_sample + len(block) * 8

            # Skip entire block if before start
            if block_end_sample <= start_sample:
                sample = block_end_sample
                continue

            # Determine slice within this block
            slice_start = max(0, start_sample - block_start_sample)
            slice_end = min(len(block) * 8, end_sample - block_start_sample)

            byte_start = slice_start // 8
            byte_end = (slice_end + 7) // 8
            sub = block[byte_start:byte_end]

            # Iterate bits MSB-first within each byte
            for bi, byte in enumerate(sub):
                abs_byte_start = block_start_sample + (byte_start + bi) * 8
                for bit in range(7, -1, -1):
                    s = abs_byte_start + (7 - bit)
                    if s < start_sample or s >= end_sample:
                        continue
                    level = (byte >> bit) & 1
                    t_ns = (s - offset) * self._multiply_ns

                    if current_level is None:
                        current_level = level
                        seg_start_ns = t_ns
                    elif level != current_level:
                        assert seg_start_ns is not None
                        events.append(
                            EdgeEvent(
                                t_ns=seg_start_ns,
                                level=current_level,
                                dur_ns=t_ns - seg_start_ns,
                            )
                        )
                        current_level = level
                        seg_start_ns = t_ns
                        if len(events) >= max_events:
                            return events

            sample = block_end_sample

        # Final segment
        if current_level is not None and seg_start_ns is not None:
            final_t_ns = (end_sample - offset) * self._multiply_ns
            events.append(
                EdgeEvent(
                    t_ns=seg_start_ns,
                    level=current_level,
                    dur_ns=final_t_ns - seg_start_ns,
                )
            )

        return events


# ---------------------------------------------------------------------------
# .bin reader
# ---------------------------------------------------------------------------

class BinReader:
    """Reader for ATK-Logic .bin raw binary files.

    Header (64 bytes):
      - 4 bytes: magic / version
      - 4 bytes: channel count
      - 4 bytes: sample rate (Hz)
      - 4 bytes: sampling depth
      - 48 bytes: reserved
    Followed by interleaved or per-channel raw bit data.
    """

    HEADER_SIZE = 64

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._data = self.path.read_bytes()
        if len(self._data) < self.HEADER_SIZE:
            raise ValueError("File too small for .bin header")
        header = self._data[: self.HEADER_SIZE]
        self._version = struct.unpack_from("<I", header, 0)[0]
        self._channel_count = struct.unpack_from("<I", header, 4)[0]
        self._sample_rate_hz = struct.unpack_from("<I", header, 8)[0]
        self._sampling_depth = struct.unpack_from("<I", header, 12)[0]
        self._multiply_ns = (
            1_000_000_000 // self._sample_rate_hz if self._sample_rate_hz else 0
        )

    def get_info(self) -> CaptureInfo:
        channels = [
            {"id": i, "name": f"Channel {i}"}
            for i in range(self._channel_count)
        ]
        duration_ns = self._sampling_depth * self._multiply_ns
        return CaptureInfo(
            channels=channels,
            sample_rate_hz=self._sample_rate_hz,
            total_samples=self._sampling_depth,
            duration_ns=duration_ns,
            capture_time=None,
            file_format="bin",
        )

    def read_edges(
        self,
        channel: int,
        start_ns: int = 0,
        end_ns: int | None = None,
        max_events: int = 10_000,
    ) -> list[EdgeEvent]:
        if channel < 0 or channel >= self._channel_count:
            raise ValueError(f"Invalid channel {channel}")

        if end_ns is None:
            end_ns = self._sampling_depth * self._multiply_ns

        start_sample = start_ns // self._multiply_ns
        end_sample = min(end_ns // self._multiply_ns, self._sampling_depth)

        data = self._data[self.HEADER_SIZE :]
        # Simple per-channel packed format: each channel is ceil(depth/8) bytes
        bytes_per_ch = (self._sampling_depth + 7) // 8
        ch_data = data[channel * bytes_per_ch : (channel + 1) * bytes_per_ch]

        events: list[EdgeEvent] = []
        current_level: int | None = None
        seg_start_ns: int | None = None

        for bi, byte in enumerate(ch_data):
            abs_byte_start = bi * 8
            for bit in range(7, -1, -1):
                s = abs_byte_start + (7 - bit)
                if s < start_sample or s >= end_sample:
                    continue
                level = (byte >> bit) & 1
                t_ns = s * self._multiply_ns

                if current_level is None:
                    current_level = level
                    seg_start_ns = t_ns
                elif level != current_level:
                    assert seg_start_ns is not None
                    events.append(
                        EdgeEvent(
                            t_ns=seg_start_ns,
                            level=current_level,
                            dur_ns=t_ns - seg_start_ns,
                        )
                    )
                    current_level = level
                    seg_start_ns = t_ns
                    if len(events) >= max_events:
                        return events

        if current_level is not None and seg_start_ns is not None:
            final_t_ns = end_sample * self._multiply_ns
            events.append(
                EdgeEvent(
                    t_ns=seg_start_ns,
                    level=current_level,
                    dur_ns=final_t_ns - seg_start_ns,
                )
            )

        return events


# ---------------------------------------------------------------------------
# Unified reader
# ---------------------------------------------------------------------------

class CaptureReader:
    """Unified reader that auto-detects file format."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        suffix = self.path.suffix.lower()
        if suffix == ".atkdl":
            self._reader: AtkdlReader | BinReader = AtkdlReader(self.path)
        elif suffix == ".bin":
            self._reader = BinReader(self.path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def get_info(self) -> CaptureInfo:
        return self._reader.get_info()

    def read_edges(
        self,
        channel: int,
        start_ns: int = 0,
        end_ns: int | None = None,
        max_events: int = 10_000,
    ) -> list[EdgeEvent]:
        return self._reader.read_edges(channel, start_ns, end_ns, max_events)
