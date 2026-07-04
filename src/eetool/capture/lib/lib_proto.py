"""
Native Python protocol decoders for ATK-Logic CLI.

Works directly on EdgeEvent lists from CaptureReader — no external DLL required.
Decoders: UART, I2C, SPI.

Each decoder accepts edge events + sample_rate_hz + options, and returns a
list of ProtoFrame. All decoders are pure Python, zero dependencies beyond stdlib.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field


@dataclass
class ProtoFrame:
    t_ns: int
    type: str              # "data" | "start" | "stop" | "ack" | "nack" | "address"
    data: dict             # protocol-specific payload, e.g. {"byte": 65, "text": "A"}
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Edge helper: fast level-at-time query via binary search on RLE edges
# ---------------------------------------------------------------------------

class _EdgeHelper:
    """Wraps a sorted list of EdgeEvent for O(log n) level-at-time queries."""

    def __init__(self, edges: list):
        self._edges = edges
        self._starts = [e.t_ns for e in edges]

    def level_at(self, t_ns: int) -> int:
        if not self._edges:
            return 0
        idx = bisect.bisect_right(self._starts, t_ns) - 1
        if idx < 0:
            idx = 0
        return self._edges[idx].level

    def rising_edges(self, t_start: int = 0, t_end: int | None = None) -> list[int]:
        """Return times of rising edges (0→1 transitions) in [t_start, t_end)."""
        result = []
        for i in range(1, len(self._edges)):
            prev, cur = self._edges[i - 1], self._edges[i]
            if prev.level == 0 and cur.level == 1:
                if cur.t_ns < t_start:
                    continue
                if t_end is not None and cur.t_ns >= t_end:
                    break
                result.append(cur.t_ns)
        return result

    def falling_edges(self, t_start: int = 0, t_end: int | None = None) -> list[int]:
        """Return times of falling edges (1→0 transitions) in [t_start, t_end)."""
        result = []
        for i in range(1, len(self._edges)):
            prev, cur = self._edges[i - 1], self._edges[i]
            if prev.level == 1 and cur.level == 0:
                if cur.t_ns < t_start:
                    continue
                if t_end is not None and cur.t_ns >= t_end:
                    break
                result.append(cur.t_ns)
        return result

    @property
    def edges(self) -> list:
        return self._edges


# ---------------------------------------------------------------------------
# UART decoder
# ---------------------------------------------------------------------------

class UartDecoder:
    """Asynchronous serial decoder.

    Required options:
        baudrate  — symbol rate (default 115200)

    Optional options:
        data_bits — 5–9 (default 8)
        parity    — none / even / odd / mark / space (default none)
        stop_bits — 1 / 1.5 / 2 (default 1)
        bit_order — lsb_first / msb_first (default lsb_first)
        polarity  — 0 = idle high (default), 1 = idle low
    """

    NATIVE_ID = "uart"

    @staticmethod
    def decoder_info():
        return {
            "id": "uart",
            "name": "UART (native)",
            "desc": "Asynchronous serial — start/data/parity/stop frame decoder",
            "channels": [],
            "opt_channels": [
                {"id": "rx", "name": "RX", "desc": "Receive data"},
                {"id": "tx", "name": "TX", "desc": "Transmit data"},
            ],
            "options": [
                {"id": "baudrate", "desc": "Symbol rate (default 115200)"},
                {"id": "data_bits", "desc": "Data bits: 5-9 (default 8)"},
                {"id": "parity", "desc": "none/even/odd/mark/space (default none)"},
                {"id": "stop_bits", "desc": "Stop bits: 1/1.5/2 (default 1)"},
                {"id": "bit_order", "desc": "lsb_first/msb_first (default lsb_first)"},
            ],
        }

    def __init__(
        self,
        edges: list,
        sample_rate_hz: int,
        options: dict | None = None,
    ):
        self._rx = _EdgeHelper(edges)
        self._sample_rate_hz = sample_rate_hz
        opts = options or {}

        self.baudrate = int(opts.get("baudrate", 115200))
        self.data_bits = int(opts.get("data_bits", 8))
        self.stop_bits_val = float(opts.get("stop_bits", 1))
        self.parity = opts.get("parity", "none").lower()
        self.bit_order = opts.get("bit_order", "lsb_first").lower()
        self.polarity = int(opts.get("polarity", 0))  # 0 = idle high

        self._bit_ns = 1_000_000_000 // self.baudrate
        self._sample_offset_ns = self._bit_ns // 2  # sample at bit center

        self._idle_level = 1 if self.polarity == 0 else 0
        self._active_level = 1 - self._idle_level

    def decode(self, drop_errors: bool = True) -> list[ProtoFrame]:
        frames: list[ProtoFrame] = []
        edges = self._rx.edges
        if len(edges) < 2:
            return frames

        # Find start bits: idle→active transition = start of frame
        i = 0
        while i < len(edges) - 1:
            prev, cur = edges[i], edges[i + 1]
            i += 1
            if prev.level != self._idle_level or cur.level != self._active_level:
                continue

            start_ns = cur.t_ns
            frame = self._decode_one_frame(start_ns)
            if drop_errors and any(f.errors for f in frame):
                pass
            else:
                frames.extend(frame)

            # Skip past this frame: advance i to frame_end so the next
            # iteration starts looking AFTER the stop bit.
            frame_end = start_ns + self._frame_ns()
            while i < len(edges) and edges[i].t_ns < frame_end:
                i += 1
            # After skipping, if we landed on an active edge, back up one
            # edge so the idle→active pair is visible to the next iteration.
            if i < len(edges) and edges[i].level == self._active_level:
                i -= 1

        return frames

    def _frame_ns(self) -> int:
        """Total frame duration in ns: 1 start + data + parity + stop."""
        bits = 1 + self.data_bits + (0 if self.parity == "none" else 1) + self.stop_bits_val
        return int(bits * self._bit_ns)

    def _decode_one_frame(self, start_ns: int) -> list[ProtoFrame]:
        """Decode a single UART frame starting at start_ns."""
        frames: list[ProtoFrame] = []

        frames.append(ProtoFrame(
            t_ns=start_ns,
            type="start",
            data={"text": "Start"},
        ))

        # Sample data bits at bit centers
        bit_values = []
        for bi in range(self.data_bits):
            sample_ns = start_ns + self._bit_ns + bi * self._bit_ns + self._sample_offset_ns
            level = self._rx.level_at(sample_ns)
            # Standard UART: line low=bit 0, line high=bit 1.
            # Inverted (polarity=1): line low=bit 1, line high=bit 0.
            bit = level if self._idle_level == 1 else 1 - level
            bit_values.append(bit)
            frames.append(ProtoFrame(
                t_ns=sample_ns,
                type="bit",
                data={"bit": bi, "value": bit},
            ))

        # Assemble byte
        if self.bit_order == "lsb_first":
            byte_val = sum(b << i for i, b in enumerate(bit_values))
        else:
            byte_val = sum(b << (self.data_bits - 1 - i) for i, b in enumerate(bit_values))

        # Parity
        parity_error = False
        parity_ns = start_ns + self._bit_ns + self.data_bits * self._bit_ns
        if self.parity != "none":
            parity_ns += self._sample_offset_ns
            parity_level = self._rx.level_at(int(parity_ns))
            parity_bit = parity_level if self._idle_level == 1 else 1 - parity_level

            expected = self._expected_parity(byte_val)
            if parity_bit != expected:
                parity_error = True

            frames.append(ProtoFrame(
                t_ns=int(parity_ns),
                type="parity",
                data={"value": parity_bit, "expected": expected},
                errors=["Parity error"] if parity_error else [],
            ))
            parity_ns += self._bit_ns

        # Stop bit(s)
        stop_errors = []
        for sb in range(int(self.stop_bits_val)):
            stop_ns = int(parity_ns + sb * self._bit_ns + self._sample_offset_ns)
            stop_level = self._rx.level_at(stop_ns)
            if stop_level != self._idle_level:
                stop_errors.append(f"Stop bit {sb + 1} error")
            frames.append(ProtoFrame(
                t_ns=stop_ns,
                type="stop",
                data={"bit": sb, "value": 1 if stop_level == self._idle_level else 0},
                errors=stop_errors[-1:] if stop_level != self._idle_level else [],
            ))

        texts = [chr(byte_val) if 32 <= byte_val < 127 else f"[{byte_val:02X}]"]
        frame_data = {
            "byte": byte_val,
            "hex": f"0x{byte_val:02X}",
            "text": texts[0],
            "ascii": chr(byte_val) if 32 <= byte_val < 127 else None,
        }

        all_errors = []
        if parity_error:
            all_errors.append("Parity error")
        all_errors.extend(stop_errors)

        frames.append(ProtoFrame(
            t_ns=start_ns,
            type="data",
            data=frame_data,
            errors=all_errors,
        ))

        return frames

    def _expected_parity(self, byte_val: int) -> int:
        bits = bin(byte_val).count("1")
        if self.parity == "even":
            return bits % 2
        elif self.parity == "odd":
            return 1 - (bits % 2)
        elif self.parity == "mark":
            return 1
        elif self.parity == "space":
            return 0
        return 0


# ---------------------------------------------------------------------------
# I²C decoder
# ---------------------------------------------------------------------------

class I2CDecoder:
    """I²C / TWI protocol decoder.

    Required channels:
        scl — serial clock
        sda — serial data

    Optional options:
        addressing — 7bit (default) / 10bit
    """

    NATIVE_ID = "i2c"

    @staticmethod
    def decoder_info():
        return {
            "id": "i2c",
            "name": "I²C (native)",
            "desc": "Inter-Integrated Circuit — START/STOP/address/data/ACK decoder",
            "channels": [
                {"id": "scl", "name": "SCL", "desc": "Serial clock"},
                {"id": "sda", "name": "SDA", "desc": "Serial data"},
            ],
            "opt_channels": [],
            "options": [
                {"id": "addressing", "desc": "Addressing mode: 7bit (default) / 10bit"},
            ],
        }

    # I²C state machine
    _IDLE = 0
    _ADDRESS = 1
    _DATA = 2

    def __init__(
        self,
        edges_scl: list,
        edges_sda: list,
        sample_rate_hz: int,
        options: dict | None = None,
    ):
        self._scl = _EdgeHelper(edges_scl)
        self._sda = _EdgeHelper(edges_sda)
        self._sample_rate_hz = sample_rate_hz
        opts = options or {}
        self._addressing = opts.get("addressing", "7bit").lower()

    def decode(self) -> list[ProtoFrame]:
        frames: list[ProtoFrame] = []
        scl_edges = self._scl.edges
        sda_edges = self._sda.edges
        if len(scl_edges) < 2 or len(sda_edges) < 2:
            return frames

        # Find all START and STOP conditions first
        # START: SDA↓ while SCL=1
        # STOP:  SDA↑ while SCL=1
        starts = []
        stops = []
        for i in range(1, len(sda_edges)):
            prev, cur = sda_edges[i - 1], sda_edges[i]
            scl_level = self._scl.level_at(cur.t_ns)
            if scl_level != 1:
                continue
            if prev.level == 1 and cur.level == 0:
                starts.append(cur.t_ns)
            elif prev.level == 0 and cur.level == 1:
                stops.append(cur.t_ns)

        # Walk through START/STOP pairs and decode bytes between them
        si, ei = 0, 0
        while si < len(starts):
            t_start = starts[si]
            t_stop = stops[ei] if ei < len(stops) and stops[ei] > t_start else None

            frames.append(ProtoFrame(
                t_ns=t_start,
                type="start",
                data={"text": "START"},
            ))

            if t_stop is None:
                break

            # Collect SCL rising edges between START and STOP
            scl_rising = self._scl.rising_edges(t_start, t_stop)
            bit_idx = 0

            # First byte: address + R/W
            addr_bits = []
            for j in range(bit_idx, min(bit_idx + 8, len(scl_rising))):
                sda_val = self._sda.level_at(scl_rising[j])
                addr_bits.append(sda_val)
                frames.append(ProtoFrame(
                    t_ns=scl_rising[j],
                    type="bit",
                    data={"bit": j - bit_idx, "value": sda_val, "context": "address"},
                ))
            bit_idx += 8

            if len(addr_bits) == 8:
                addr = sum(b << (7 - i_byte) for i_byte, b in enumerate(addr_bits))
                rw = addr & 1
                addr7 = addr >> 1

                # ACK for address (9th bit)
                ack = 0
                ack_error = False
                if bit_idx < len(scl_rising):
                    ack = self._sda.level_at(scl_rising[bit_idx])
                    ack_error = (ack != 0)
                    frames.append(ProtoFrame(
                        t_ns=scl_rising[bit_idx],
                        type="ack" if ack == 0 else "nack",
                        data={"ack": ack == 0},
                        errors=["NACK on address"] if ack_error else [],
                    ))
                    bit_idx += 1

                frames.append(ProtoFrame(
                    t_ns=t_start,
                    type="address",
                    data={
                        "address": addr7,
                        "hex": f"0x{addr7:02X}",
                        "rw": "read" if rw else "write",
                    },
                    errors=["NACK on address"] if ack_error else [],
                ))

                # Subsequent data bytes
                while bit_idx + 8 <= len(scl_rising):
                    data_byte_start = bit_idx
                    data_bits_val = []
                    for j in range(data_byte_start, data_byte_start + 8):
                        sda_val = self._sda.level_at(scl_rising[j])
                        data_bits_val.append(sda_val)
                        frames.append(ProtoFrame(
                            t_ns=scl_rising[j],
                            type="bit",
                            data={"bit": j - data_byte_start, "value": sda_val, "context": "data"},
                        ))
                    bit_idx += 8

                    data_byte = sum(b << (7 - i_byte) for i_byte, b in enumerate(data_bits_val))

                    # ACK/NACK
                    data_ack = 0
                    data_ack_err = False
                    if bit_idx < len(scl_rising):
                        data_ack = self._sda.level_at(scl_rising[bit_idx])
                        data_ack_err = (data_ack != 0)
                        frames.append(ProtoFrame(
                            t_ns=scl_rising[bit_idx],
                            type="ack" if data_ack == 0 else "nack",
                            data={"ack": data_ack == 0},
                            errors=["NACK"] if data_ack_err else [],
                        ))
                        bit_idx += 1

                    texts = [chr(data_byte) if 32 <= data_byte < 127 else f"[{data_byte:02X}]"]
                    frames.append(ProtoFrame(
                        t_ns=scl_rising[data_byte_start],
                        type="data",
                        data={
                            "byte": data_byte,
                            "hex": f"0x{data_byte:02X}",
                            "text": texts[0],
                        },
                        errors=["NACK"] if data_ack_err else [],
                    ))

                    if data_ack_err:
                        break

            frames.append(ProtoFrame(
                t_ns=t_stop,
                type="stop",
                data={"text": "STOP"},
            ))

            # Advance to next START after this STOP
            si += 1
            while ei < len(stops) and stops[ei] <= t_stop:
                ei += 1

        return frames


# ---------------------------------------------------------------------------
# SPI decoder
# ---------------------------------------------------------------------------

class SpiDecoder:
    """SPI protocol decoder.

    Required channels:
        clk  — serial clock

    Optional channels:
        mosi — Master Out Slave In
        miso — Master In Slave Out
        cs   — Chip Select (active low)

    Optional options:
        wordsize — bits per word (default 8)
        bitorder — msb_first / lsb_first (default msb_first)
        cpol     — clock polarity: 0/1 (default 0)
        cpha     — clock phase: 0/1 (default 0)
        cs_polarity — active low/high (default low)
    """

    NATIVE_ID = "spi"

    @staticmethod
    def decoder_info():
        return {
            "id": "spi",
            "name": "SPI (native)",
            "desc": "Serial Peripheral Interface — MOSI/MISO/CS word decoder",
            "channels": [
                {"id": "clk", "name": "CLK", "desc": "Serial clock"},
            ],
            "opt_channels": [
                {"id": "mosi", "name": "MOSI", "desc": "Master Out Slave In"},
                {"id": "miso", "name": "MISO", "desc": "Master In Slave Out"},
                {"id": "cs", "name": "CS", "desc": "Chip Select"},
            ],
            "options": [
                {"id": "wordsize", "desc": "Bits per word (default 8)"},
                {"id": "bitorder", "desc": "msb_first/lsb_first (default msb_first)"},
                {"id": "cpol", "desc": "Clock polarity 0/1 (default 0)"},
                {"id": "cpha", "desc": "Clock phase 0/1 (default 0)"},
                {"id": "cs_polarity", "desc": "Chip select active low/high (default low)"},
            ],
        }

    def __init__(
        self,
        edges_clk: list,
        edges_mosi: list | None = None,
        edges_miso: list | None = None,
        edges_cs: list | None = None,
        sample_rate_hz: int = 0,
        options: dict | None = None,
    ):
        self._clk = _EdgeHelper(edges_clk)
        self._mosi = _EdgeHelper(edges_mosi) if edges_mosi else None
        self._miso = _EdgeHelper(edges_miso) if edges_miso else None
        self._cs = _EdgeHelper(edges_cs) if edges_cs else None
        opts = options or {}

        self.wordsize = int(opts.get("wordsize", 8))
        self.bitorder = opts.get("bitorder", "msb_first").lower()
        self.cpol = int(opts.get("cpol", 0))
        self.cpha = int(opts.get("cpha", 0))
        cs_pol = opts.get("cs_polarity", "low").lower()
        self._cs_active = 0 if cs_pol in ("low", "0") else 1

    def decode(self) -> list[ProtoFrame]:
        frames: list[ProtoFrame] = []
        clk_edges = self._clk.edges
        if len(clk_edges) < 2:
            return frames

        # Determine sampling edges based on CPOL/CPHA
        # CPHA=0: sample on first clock edge (leading) of each cycle
        # CPHA=1: sample on second clock edge (trailing) of each cycle
        # CPOL=0: idle low,  leading = rising,  trailing = falling
        # CPOL=1: idle high, leading = falling, trailing = rising
        if self.cpol == 0:
            leading_rising = True  # rising = 0→1
        else:
            leading_rising = False  # falling = 1→0

        if self.cpha == 0:
            sample_on_rising = leading_rising
        else:
            sample_on_rising = not leading_rising

        # Find sample edges
        sample_edges = []
        for i in range(1, len(clk_edges)):
            prev, cur = clk_edges[i - 1], clk_edges[i]
            is_rising = prev.level == 0 and cur.level == 1
            if is_rising == sample_on_rising:
                sample_edges.append(cur.t_ns)

        if not sample_edges:
            return frames

        # Group by CS if available
        cs_regions = self._find_cs_regions(sample_edges[0], sample_edges[-1])

        if cs_regions:
            for cs_start, cs_end in cs_regions:
                frames.append(ProtoFrame(
                    t_ns=cs_start,
                    type="cs_assert",
                    data={"text": "CS asserted"},
                ))

                region_samples = [t for t in sample_edges if cs_start <= t < cs_end]
                self._decode_words(region_samples, frames)

                frames.append(ProtoFrame(
                    t_ns=cs_end,
                    type="cs_deassert",
                    data={"text": "CS deasserted"},
                ))
        else:
            self._decode_words(sample_edges, frames)

        return frames

    def _decode_words(self, sample_times: list[int], frames: list[ProtoFrame]) -> None:
        """Decode words from a list of sample times."""
        word_count = 0
        for wi in range(0, len(sample_times), self.wordsize):
            chunk = sample_times[wi : wi + self.wordsize]
            if len(chunk) < self.wordsize:
                break

            mosi_byte = 0
            miso_byte = 0
            bits_data = []

            for bi, t_ns in enumerate(chunk):
                bit_pos = bi if self.bitorder == "msb_first" else (self.wordsize - 1 - bi)

                mosi_bit = self._mosi.level_at(t_ns) if self._mosi else 0
                miso_bit = self._miso.level_at(t_ns) if self._miso else 0
                mosi_byte |= mosi_bit << (self.wordsize - 1 - bit_pos)
                miso_byte |= miso_bit << (self.wordsize - 1 - bit_pos)

                bits_data.append({
                    "mosi": mosi_bit,
                    "miso": miso_bit,
                })

                frames.append(ProtoFrame(
                    t_ns=t_ns,
                    type="bit",
                    data={"word": word_count, "bit": bi, "mosi": mosi_bit, "miso": miso_bit},
                ))

            mosi_text = chr(mosi_byte) if 32 <= mosi_byte < 127 else f"[{mosi_byte:02X}]"
            miso_text = chr(miso_byte) if 32 <= miso_byte < 127 else f"[{miso_byte:02X}]"
            frames.append(ProtoFrame(
                t_ns=chunk[0],
                type="data",
                data={
                    "word": word_count,
                    "mosi_hex": f"0x{mosi_byte:02X}",
                    "miso_hex": f"0x{miso_byte:02X}",
                    "mosi_text": mosi_text,
                    "miso_text": miso_text,
                },
            ))
            word_count += 1

    def _find_cs_regions(self, t_start: int, t_end: int) -> list[tuple[int, int]]:
        """Find CS-asserted time regions."""
        if not self._cs:
            return []

        cs_edges = self._cs.edges
        regions = []
        in_active = False
        active_start = 0

        for i in range(len(cs_edges)):
            e = cs_edges[i]
            if e.t_ns > t_end:
                break
            if e.level == self._cs_active and not in_active:
                in_active = True
                active_start = e.t_ns
            elif e.level != self._cs_active and in_active:
                in_active = False
                end_ns = e.t_ns
                if end_ns > t_start:
                    regions.append((max(active_start, t_start), end_ns))

        if in_active:
            regions.append((max(active_start, t_start), t_end))

        return regions


# ---------------------------------------------------------------------------
# Decoder registry
# ---------------------------------------------------------------------------

_NATIVE_DECODERS = {
    "uart": (UartDecoder, UartDecoder.decoder_info()),
    "i2c": (I2CDecoder, I2CDecoder.decoder_info()),
    "spi": (SpiDecoder, SpiDecoder.decoder_info()),
}

_ALIASES = {
    "rs232": "uart",
    "serial": "uart",
    "twi": "i2c",
}


def get_native_decoder_ids() -> list[str]:
    """Return list of built-in decoder IDs."""
    return sorted(_NATIVE_DECODERS.keys())


def get_native_decoder_info(decoder_id: str):
    """Return decoder info dict, or None if not a native decoder."""
    decoder_id = _ALIASES.get(decoder_id, decoder_id)
    entry = _NATIVE_DECODERS.get(decoder_id)
    if entry is None:
        return None
    return entry[1]


def list_native_decoders(filter_ids: list[str] | None = None) -> list[dict]:
    """List all native decoders, optionally filtered."""
    result = []
    for did in _NATIVE_DECODERS:
        if filter_ids and did not in filter_ids:
            continue
        result.append(_NATIVE_DECODERS[did][1])
    return result


# ---------------------------------------------------------------------------
# Unified decode entry point (called by CLI)
# ---------------------------------------------------------------------------

def native_decode(
    decoder_id: str,
    channel_map: dict[str, int],
    reader,  # CaptureReader
    options: dict[str, str] | None = None,
    start_ns: int = 0,
    end_ns: int | None = None,
    max_events: int = 100000,
) -> list[dict]:
    """Run a native protocol decoder against a CaptureReader.

    Returns a list of frame dicts ready for JSON serialization.
    """
    decoder_id = _ALIASES.get(decoder_id, decoder_id)
    entry = _NATIVE_DECODERS.get(decoder_id)
    if entry is None:
        raise ValueError(f"Unknown native decoder: {decoder_id}")

    decoder_cls, _ = entry
    info = reader.get_info()
    sr_hz = info.sample_rate_hz
    opts = options or {}

    def _read(ch_key: str):
        ch = channel_map.get(ch_key)
        if ch is None:
            return []
        return reader.read_edges(ch, start_ns, end_ns, max_events)

    if decoder_id == "uart":
        rx = _read("rx")
        tx = _read("tx")
        edges = rx if rx else tx
        if not edges:
            raise ValueError("UART requires --rx or --tx channel mapping")
        dec = decoder_cls(edges, sr_hz, opts)
        drop_errors = opts.pop("drop_errors", "true").lower() in ("1", "true", "yes")
        frames: list[ProtoFrame] = dec.decode(drop_errors=drop_errors)

    elif decoder_id == "i2c":
        edges_scl = _read("scl")
        edges_sda = _read("sda")
        if not edges_scl or not edges_sda:
            raise ValueError("I²C requires --scl and --sda channel mappings")
        dec = decoder_cls(edges_scl, edges_sda, sr_hz, opts)
        frames: list[ProtoFrame] = dec.decode()

    elif decoder_id == "spi":
        edges_clk = _read("clk")
        if not edges_clk:
            raise ValueError("SPI requires --clk channel mapping")
        edges_mosi = _read("mosi")
        edges_miso = _read("miso")
        edges_cs = _read("cs")
        dec = decoder_cls(edges_clk, edges_mosi, edges_miso, edges_cs, sr_hz, opts)
        frames: list[ProtoFrame] = dec.decode()

    else:
        raise ValueError(f"Unknown native decoder: {decoder_id}")

    return [
        {"t_ns": f.t_ns, "type": f.type, "data": f.data, "errors": f.errors}
        for f in frames
    ]
