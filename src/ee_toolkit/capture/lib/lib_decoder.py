"""
ATK-Logic decoder bridge via ctypes.

Wraps libsigrokdecode-4.dll to expose protocol decoders.
The DLL must be compiled against the same Python version as the host process.
"""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import _bootstrap

if sys.version_info < (3, 12):
    raise RuntimeError(
        "libsigrokdecode-4.dll requires Python 3.12+. "
        "Build it from atk_libsigrokdecode source with matching Python version."
    )


# ---------------------------------------------------------------------------
# ctypes structures (mirror atk_decoder.h)
# ---------------------------------------------------------------------------

class _AtkGSList(ctypes.Structure):
    pass


_AtkGSList._fields_ = [
    ("data", ctypes.c_void_p),
    ("next", ctypes.POINTER(_AtkGSList)),
]


class _AtkDecoder(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_char_p),
        ("name", ctypes.c_char_p),
        ("longname", ctypes.c_char_p),
        ("desc", ctypes.c_char_p),
        ("license", ctypes.c_char_p),
        ("inputs", ctypes.POINTER(_AtkGSList)),
        ("outputs", ctypes.POINTER(_AtkGSList)),
        ("tags", ctypes.POINTER(_AtkGSList)),
        ("channels", ctypes.POINTER(_AtkGSList)),
        ("opt_channels", ctypes.POINTER(_AtkGSList)),
        ("annotations", ctypes.POINTER(_AtkGSList)),
        ("annotation_rows", ctypes.POINTER(_AtkGSList)),
        ("binary", ctypes.POINTER(_AtkGSList)),
        ("logic_output_channels", ctypes.POINTER(_AtkGSList)),
        ("options", ctypes.POINTER(_AtkGSList)),
        ("py_mod", ctypes.c_void_p),
        ("py_dec", ctypes.c_void_p),
    ]


class _AtkChannel(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_char_p),
        ("name", ctypes.c_char_p),
        ("desc", ctypes.c_char_p),
        ("order", ctypes.c_int),
    ]


class _AtkDecoderOption(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_char_p),
        ("desc", ctypes.c_char_p),
        ("def_val", ctypes.c_void_p),
        ("values", ctypes.POINTER(_AtkGSList)),
    ]


class _AtkInputData(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("constant", ctypes.c_uint8),
    ]


class _AtkPdOutput(ctypes.Structure):
    _fields_ = [
        ("pdo_id", ctypes.c_int),
        ("output_type", ctypes.c_int),
        ("di", ctypes.c_void_p),
        ("proto_id", ctypes.c_char_p),
        ("meta_type", ctypes.c_void_p),
        ("meta_name", ctypes.c_char_p),
        ("meta_descr", ctypes.c_char_p),
    ]


class _AtkProtoData(ctypes.Structure):
    _fields_ = [
        ("start_sample", ctypes.c_uint64),
        ("end_sample", ctypes.c_uint64),
        ("pdo", ctypes.POINTER(_AtkPdOutput)),
        ("data", ctypes.c_void_p),
    ]


class _AtkProtoDataAnn(ctypes.Structure):
    _fields_ = [
        ("ann_class", ctypes.c_int),
        ("ann_row", ctypes.c_int),
        ("ann_text", ctypes.POINTER(ctypes.c_char_p)),
    ]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ATK_OUTPUT_ANN = 0
ATK_OUTPUT_PYTHON = 1
ATK_OUTPUT_BINARY = 2
ATK_OUTPUT_LOGIC = 3
ATK_OUTPUT_META = 4

ATK_OK = 0


# ---------------------------------------------------------------------------
# Data classes for public API
# ---------------------------------------------------------------------------

@dataclass
class DecoderInfo:
    id: str
    name: str
    desc: str
    channels: list[dict] = field(default_factory=list)
    opt_channels: list[dict] = field(default_factory=list)
    options: list[dict] = field(default_factory=list)


@dataclass
class DecodeFrame:
    t_ns: int
    type: str
    data: dict
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper: walk GSList
# ---------------------------------------------------------------------------

def _gslist_to_list(gslist_ptr) -> list[Any]:
    items = []
    while gslist_ptr:
        items.append(gslist_ptr.contents.data)
        gslist_ptr = gslist_ptr.contents.next
    return items


# ---------------------------------------------------------------------------
# Decoder bridge
# ---------------------------------------------------------------------------

class DecoderBridge:
    """High-level wrapper around libsigrokdecode."""

    def __init__(self, project_root: Path | str | None = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent.resolve()
        self._project_root = Path(project_root)
        self._dll_path = self._find_dll()
        self._dll = ctypes.CDLL(str(self._dll_path))
        self._init_ok = False
        self._frames: list[DecodeFrame] = []
        self._ann_cb = None
        self._setup_signatures()

    @staticmethod
    def _find_dll() -> Path:
        candidates = [
            Path(__file__).parent.parent / "lib" / "bin" / "libsigrokdecode-4.dll",
            Path(__file__).parent.parent / "libsigrokdecode-4.dll",
        ]
        for p in candidates:
            if p.exists():
                return p
        raise FileNotFoundError("libsigrokdecode-4.dll not found")

    def _setup_signatures(self) -> None:
        dll = self._dll

        # PyInit_sigrokdecode — creates the sigrokdecode Python module
        dll.PyInit_sigrokdecode.argtypes = []
        dll.PyInit_sigrokdecode.restype = ctypes.py_object

        # Search path
        dll.srd_decoder_searchpath_add.argtypes = [ctypes.c_char_p]
        dll.srd_decoder_searchpath_add.restype = ctypes.c_int

        # decoder.c
        dll.atk_decoder_load_all.argtypes = []
        dll.atk_decoder_load_all.restype = ctypes.c_int

        dll.atk_decoder_list.argtypes = []
        dll.atk_decoder_list.restype = ctypes.POINTER(_AtkGSList)

        dll.atk_decoder_get_by_id.argtypes = [ctypes.c_char_p]
        dll.atk_decoder_get_by_id.restype = ctypes.POINTER(_AtkDecoder)

        # session.c
        dll.atk_decoder_session_new.argtypes = []
        dll.atk_decoder_session_new.restype = ctypes.c_void_p

        dll.atk_decoder_session_start.argtypes = [ctypes.c_void_p]
        dll.atk_decoder_session_start.restype = ctypes.c_int

        dll.atk_decoder_session_metadata_set_samplerate.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint64,
        ]
        dll.atk_decoder_session_metadata_set_samplerate.restype = ctypes.c_int

        dll.atk_decoder_session_send.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint64,
            ctypes.c_uint64,
            ctypes.c_void_p,
        ]
        dll.atk_decoder_session_send.restype = ctypes.c_int

        dll.atk_decoder_session_send_eof.argtypes = [ctypes.c_void_p]
        dll.atk_decoder_session_send_eof.restype = ctypes.c_int

        dll.atk_decoder_session_destroy.argtypes = [ctypes.c_void_p]
        dll.atk_decoder_session_destroy.restype = ctypes.c_int

        # instance.c
        dll.atk_decoder_inst_new.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_void_p,
        ]
        dll.atk_decoder_inst_new.restype = ctypes.c_void_p

        dll.atk_decoder_inst_channel_set_all.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        dll.atk_decoder_inst_channel_set_all.restype = ctypes.c_int

        # hash table
        dll.atk_decoder_hashtable_create.argtypes = []
        dll.atk_decoder_hashtable_create.restype = ctypes.c_void_p

        dll.atk_decoder_hashtable_destroy.argtypes = [ctypes.c_void_p]
        dll.atk_decoder_hashtable_destroy.restype = None

        dll.atk_decoder_hashtable_set_option.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_AtkDecoder),
            ctypes.c_char_p,
            ctypes.c_char_p,
        ]
        dll.atk_decoder_hashtable_set_option.restype = ctypes.c_int

        dll.atk_decoder_hashtable_set_channel.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        dll.atk_decoder_hashtable_set_channel.restype = None

        # callback
        dll.atk_decoder_pd_output_callback_add.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        dll.atk_decoder_pd_output_callback_add.restype = ctypes.c_int

    def init(self) -> None:
        """Initialize the decoder subsystem entirely from Python.

        We cannot call srd_init() because it internally calls
        PyImport_AppendInittab() which crashes if Python is already
        initialized. Instead we replicate its initialization manually:
        1. Create sigrokdecode module via PyInit_sigrokdecode
        2. Register it as a DLL data symbol and in sys.modules
        3. Set max_session_id to 0 (was -1, signaled "uninitialized")
        4. Add decoder search paths
        5. Load all decoder .py files
        """
        import ctypes

        # 1. Create the sigrokdecode Python module
        self._dll.PyInit_sigrokdecode.argtypes = []
        self._dll.PyInit_sigrokdecode.restype = ctypes.py_object
        module = self._dll.PyInit_sigrokdecode()
        if module is None:
            raise RuntimeError("PyInit_sigrokdecode returned NULL")

        # 2. Write module pointer to mod_sigrokdecode DLL data symbol
        k32 = ctypes.WinDLL("kernel32")
        k32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        k32.GetProcAddress.restype = ctypes.c_void_p

        mod_addr = k32.GetProcAddress(
            ctypes.c_void_p(self._dll._handle), b"mod_sigrokdecode"
        )
        if not mod_addr:
            raise RuntimeError("mod_sigrokdecode symbol not found")

        class _PyObjPtr(ctypes.Structure):
            _fields_ = [("obj", ctypes.py_object)]

        _PyObjPtr.from_address(mod_addr).obj = module
        sys.modules["sigrokdecode"] = module

        # 3. Reset max_session_id from -1 to 0 (unblocks decoder loading)
        mid_addr = k32.GetProcAddress(
            ctypes.c_void_p(self._dll._handle), b"max_session_id"
        )
        if mid_addr:
            mid_ptr = ctypes.cast(mid_addr, ctypes.POINTER(ctypes.c_int))
            mid_ptr[0] = 0

        # 4. Add decoder search paths
        decoders_path = str(self._project_root / "runtime" / "decoders")
        rc = self._dll.srd_decoder_searchpath_add(decoders_path.encode("utf-8"))
        if rc != ATK_OK:
            raise RuntimeError(f"srd_decoder_searchpath_add failed: {rc}")

        # 5. Load all protocol decoders
        rc = self._dll.atk_decoder_load_all()
        if rc != ATK_OK:
            raise RuntimeError(f"atk_decoder_load_all failed: {rc}")

        self._init_ok = True

    def close(self) -> None:
        self._init_ok = False

    def list_decoders(self, filter_ids: list[str] | None = None) -> list[DecoderInfo]:
        if not self._init_ok:
            self.init()

        decoders = []
        gslist = self._dll.atk_decoder_list()
        for ptr in _gslist_to_list(gslist):
            dec = ctypes.cast(ptr, ctypes.POINTER(_AtkDecoder)).contents
            dec_id = dec.id.decode("utf-8") if dec.id else ""
            if filter_ids and dec_id not in filter_ids:
                continue

            info = DecoderInfo(
                id=dec_id,
                name=(dec.name or b"").decode("utf-8"),
                desc=(dec.desc or b"").decode("utf-8"),
            )

            for ch_ptr in _gslist_to_list(dec.channels):
                ch = ctypes.cast(ch_ptr, ctypes.POINTER(_AtkChannel)).contents
                info.channels.append(
                    {
                        "id": (ch.id or b"").decode("utf-8"),
                        "name": (ch.name or b"").decode("utf-8"),
                        "desc": (ch.desc or b"").decode("utf-8"),
                    }
                )

            for ch_ptr in _gslist_to_list(dec.opt_channels):
                ch = ctypes.cast(ch_ptr, ctypes.POINTER(_AtkChannel)).contents
                info.opt_channels.append(
                    {
                        "id": (ch.id or b"").decode("utf-8"),
                        "name": (ch.name or b"").decode("utf-8"),
                        "desc": (ch.desc or b"").decode("utf-8"),
                    }
                )

            for opt_ptr in _gslist_to_list(dec.options):
                opt = ctypes.cast(opt_ptr, ctypes.POINTER(_AtkDecoderOption)).contents
                info.options.append(
                    {
                        "id": (opt.id or b"").decode("utf-8"),
                        "desc": (opt.desc or b"").decode("utf-8"),
                    }
                )

            decoders.append(info)

        return decoders

    def decode(
        self,
        decoder_id: str,
        channel_map: dict[str, int],
        options: dict[str, str],
        edge_events: list[tuple[int, int]],
        sample_rate_hz: int,
    ) -> list[DecodeFrame]:
        if not self._init_ok:
            self.init()

        self._frames = []
        sess = self._dll.atk_decoder_session_new()
        if not sess:
            raise RuntimeError("atk_decoder_session_new failed")

        try:
            dec = self._dll.atk_decoder_get_by_id(decoder_id.encode("utf-8"))
            if not dec:
                raise ValueError(f"Decoder not found: {decoder_id}")

            opts_ht = self._dll.atk_decoder_hashtable_create()
            for k, v in options.items():
                self._dll.atk_decoder_hashtable_set_option(
                    opts_ht, dec, k.encode("utf-8"), str(v).encode("utf-8")
                )

            di = self._dll.atk_decoder_inst_new(
                sess, decoder_id.encode("utf-8"), opts_ht
            )
            self._dll.atk_decoder_hashtable_destroy(opts_ht)
            if not di:
                raise RuntimeError("atk_decoder_inst_new failed")

            ch_ht = self._dll.atk_decoder_hashtable_create()
            for ch_id, ch_val in channel_map.items():
                self._dll.atk_decoder_hashtable_set_channel(
                    ch_ht, ch_id.encode("utf-8"), ch_val
                )
            self._dll.atk_decoder_inst_channel_set_all(di, ch_ht)
            self._dll.atk_decoder_hashtable_destroy(ch_ht)

            _CBFUNC = ctypes.CFUNCTYPE(
                None, ctypes.POINTER(_AtkProtoData), ctypes.c_void_p
            )

            def _ann_cb(pdata_ptr, _cb_data):
                pdata = pdata_ptr.contents
                pdo = pdata.pdo.contents
                if pdo.output_type != ATK_OUTPUT_ANN:
                    return
                ann = ctypes.cast(
                    pdata.data, ctypes.POINTER(_AtkProtoDataAnn)
                ).contents
                texts = []
                i = 0
                while ann.ann_text[i]:
                    texts.append(ann.ann_text[i].decode("utf-8"))
                    i += 1
                t_ns = int(pdata.start_sample * (1_000_000_000 / sample_rate_hz))
                self._frames.append(
                    DecodeFrame(
                        t_ns=t_ns,
                        type="data",
                        data={"text": " ".join(texts), "class": ann.ann_class},
                    )
                )

            self._ann_cb = _CBFUNC(_ann_cb)
            self._dll.atk_decoder_pd_output_callback_add(
                sess, ATK_OUTPUT_ANN, self._ann_cb, None
            )

            self._dll.atk_decoder_session_metadata_set_samplerate(
                sess, sample_rate_hz
            )

            rc = self._dll.atk_decoder_session_start(sess)
            if rc != ATK_OK:
                raise RuntimeError(f"atk_decoder_session_start failed: {rc}")

            self._send_sample_data(sess, edge_events, sample_rate_hz)

            self._dll.atk_decoder_session_send_eof(sess)

        finally:
            self._dll.atk_decoder_session_destroy(sess)

        return self._frames

    def _send_sample_data(
        self,
        sess,
        edge_events: list[tuple[int, int]],
        sample_rate_hz: int,
    ) -> None:
        if not edge_events:
            return

        max_sample = max(s for s, _ in edge_events)
        dense = bytearray()
        current_level = 0
        pos = 0
        for s, level in edge_events:
            while pos < s:
                dense.append(current_level)
                pos += 1
            current_level = level
        while pos <= max_sample:
            dense.append(current_level)
            pos += 1

        packed = bytearray()
        for i in range(0, len(dense), 8):
            byte = 0
            for j in range(8):
                if i + j < len(dense) and dense[i + j]:
                    byte |= 1 << (7 - j)
            packed.append(byte)

        chunk_samples = 4 * 1024 * 1024
        chunk_bytes = (chunk_samples + 7) // 8
        start_sample = edge_events[0][0]

        for i in range(0, len(packed), chunk_bytes):
            chunk = packed[i : i + chunk_bytes]
            arr = (ctypes.c_uint8 * len(chunk))(*chunk)
            inbuf = _AtkInputData()
            inbuf.data = arr
            inbuf.constant = 0
            chunk_start = start_sample + i * 8
            chunk_end = chunk_start + len(chunk) * 8
            self._dll.atk_decoder_session_send(
                sess, chunk_start, chunk_end, ctypes.byref(inbuf)
            )
