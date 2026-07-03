"""
ATK-Logic CLI entry point.

Commands:
    info          Show capture file metadata
    export        Export edge events for channel(s)
    list-decoders List available protocol decoders
    decode        Run protocol decoder on capture data
    capture       Start capture from USB device and save as .atkdl

Built-in decoders (native Python, no DLL needed): uart, i2c, spi.
Other decoders require libsigrokdecode-4.dll + Python 3.14.

Usage:
    python atk_cli.py info test.atkdl
    python atk_cli.py export test.atkdl --ch 0 --start 0 --end 1ms
    python atk_cli.py list-decoders --filter uart
    python atk_cli.py decode test.atkdl --decoder uart --rx 0 --option baudrate=115200
    python atk_cli.py capture start --ch 0 --duration 5s --output capture.atkdl
"""

from __future__ import annotations

from . import _bootstrap

import argparse
import json
import sys
import time
from pathlib import Path

from . import _config
from ._config import APPDATA_ATK, SCRIPTS_DIR, TCP_HOST, TCP_PORT, get_data_dir, get_gui_dir
from .lib.lib_config_sync import sync_set_ini, get_set_ini_params

from .lib.lib_reader import CaptureReader, parse_time
from .lib.lib_proto import (
    native_decode,
    get_native_decoder_ids,
    list_native_decoders,
)
# DecoderBridge requires Python 3.14 + libsigrokdecode-4.dll
try:
    from .lib.lib_decoder import DecoderBridge
except RuntimeError:
    DecoderBridge = None  # type: ignore


def _out(data, fmt):
    if fmt == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        for k, v in data.items():
            print(f"{k}: {v}")


def _err(msg):
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# preflight status helpers (DLL-persisted, lifetime = GUI process)
# ---------------------------------------------------------------------------

def api_get_preflight_status() -> bool:
    """Query DLL for preflight status. Returns True if preflight passed in this GUI session."""
    import socket as _socket
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((TCP_HOST, TCP_PORT))
        s.sendall(b'{"cmd":"get_preflight_status"}\n')
        raw = s.recv(4096).decode().strip()
        s.close()
        if raw:
            resp = json.loads(raw)
            return resp.get("value") == "1"
    except Exception:
        pass
    return False


def api_set_preflight_status(ok: bool):
    """Set preflight status in DLL. Survives within one GUI session."""
    import socket as _socket
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((TCP_HOST, TCP_PORT))
        val = "1" if ok else "0"
        s.sendall(f'{{"cmd":"set_preflight_status","value":{val}}}\n'.encode())
        s.recv(256)
        s.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------

def cmd_info(args):
    reader = CaptureReader(args.file)
    info = reader.get_info()
    _out(
        {
            "channels": info.channels,
            "sample_rate_hz": info.sample_rate_hz,
            "total_samples": info.total_samples,
            "duration_ns": info.duration_ns,
            "capture_time": info.capture_time,
            "file_format": info.file_format,
        },
        args.format,
    )


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

def cmd_export(args):
    reader = CaptureReader(args.file)
    start_ns = parse_time(args.start)
    end_ns = parse_time(args.end) if args.end else None
    channel_ids = [int(c.strip()) for c in args.ch.split(",")]
    result = {}
    for cid in channel_ids:
        edges = reader.read_edges(cid, start_ns, end_ns, args.max_events)
        result[str(cid)] = [
            {"t_ns": e.t_ns, "level": e.level, "dur_ns": e.dur_ns} for e in edges
        ]
    _out({"channels": result}, args.format)


# ---------------------------------------------------------------------------
# list-decoders
# ---------------------------------------------------------------------------

def cmd_list_decoders(args):
    filter_ids = [f.strip() for f in args.filter.split(",")] if args.filter else None

    # Always show built-in native decoders first
    data = list_native_decoders(filter_ids)

    # If DLL is available, also show libsigrokdecode decoders
    if DecoderBridge is not None:
        try:
            bridge = DecoderBridge()
            bridge_decoders = bridge.list_decoders(filter_ids)
            data += [
                {
                    "id": d.id,
                    "name": d.name + " (libsigrokdecode)",
                    "desc": d.desc,
                    "channels": d.channels,
                    "opt_channels": d.opt_channels,
                    "options": d.options,
                }
                for d in bridge_decoders
            ]
        except Exception as e:
            _err(f"DLL decoder list failed: {e}")

    _out(data, args.format)


# ---------------------------------------------------------------------------
# decode
# ---------------------------------------------------------------------------

def cmd_decode(args):
    reader = CaptureReader(args.file)
    info = reader.get_info()
    multiply_ns = 1_000_000_000 // info.sample_rate_hz if info.sample_rate_hz else 50

    start_ns = parse_time(args.start)
    end_ns = parse_time(args.end) if args.end else None

    # Build channel map from --rx, --tx, --scl, etc.
    channel_map: dict[str, int] = {}
    for key in ("rx", "tx", "scl", "sda", "clk", "mosi", "miso", "cs"):
        val = getattr(args, key, None)
        if val is not None:
            channel_map[key] = val

    decoder_options: dict[str, str] = {}
    if args.option:
        for opt in args.option:
            if "=" in opt:
                k, v = opt.split("=", 1)
                decoder_options[k] = v

    # ── Native decoder path (built-in, no DLL needed) ──
    native_ids = get_native_decoder_ids()
    if args.decoder in native_ids:
        try:
            frames = native_decode(
                decoder_id=args.decoder,
                channel_map=channel_map,
                reader=reader,
                options=decoder_options,
                start_ns=start_ns,
                end_ns=end_ns,
                max_events=args.max_events,
            )
        except Exception as e:
            _out({"error": str(e)}, args.format)
            sys.exit(1)

        _out(
            {
                "decoder": args.decoder,
                "engine": "native",
                "frames": frames,
                "stats": {"total_frames": len(frames)},
            },
            args.format,
        )
        return

    # ── DLL decoder path (libsigrokdecode) ──
    if DecoderBridge is None:
        _out(
            {
                "error": (
                    f"Decoder '{args.decoder}' not built-in. "
                    f"Built-in decoders: {', '.join(native_ids)}. "
                    "For other decoders, run with python3.14.exe launcher and libsigrokdecode-4.dll."
                )
            },
            args.format,
        )
        sys.exit(1)

    # Convert edges to dense sample tuples for DLL decoder
    all_edge_events: list[tuple[int, int]] = []
    if channel_map:
        first_ch = next(iter(channel_map.values()))
        edges = reader.read_edges(first_ch, start_ns, end_ns, args.max_events)
        start_sample = start_ns // multiply_ns
        for e in edges:
            s = e.t_ns // multiply_ns
            all_edge_events.append((s, e.level))
        if edges:
            last = edges[-1]
            final_s = (last.t_ns + last.dur_ns) // multiply_ns
            all_edge_events.append((final_s, last.level))

    bridge = DecoderBridge()
    try:
        bridge.init()
        frames = bridge.decode(
            decoder_id=args.decoder,
            channel_map=channel_map,
            options=decoder_options,
            edge_events=all_edge_events,
            sample_rate_hz=info.sample_rate_hz,
        )
    except Exception as e:
        _out({"error": str(e)}, args.format)
        sys.exit(1)

    _out(
        {
            "decoder": args.decoder,
            "engine": "libsigrokdecode",
            "frames": [
                {"t_ns": f.t_ns, "type": f.type, "data": f.data, "errors": f.errors}
                for f in frames
            ],
            "stats": {"total_frames": len(frames)},
        },
        args.format,
    )


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

def _cleanup_unsaved_markers():
    """Remove ATK-Logic temp/memory markers left by a previous force-kill.

    These markers cause ATK-Logic to show a "recover unsaved data?" dialog
    on close (WM_CLOSE) and on startup.  The dialog blocks graceful shutdown,
    which forces us to /f kill again — a vicious cycle.

    _restart_gui() calls this BEFORE sending WM_CLOSE so the process can exit
    cleanly.  Since _restart_gui() is only invoked for config sync (not to
    recover user data), deleting these markers is safe.
    """
    import shutil
    memory_dir = APPDATA_ATK / "temp" / "memory"
    lock_file = APPDATA_ATK / "temp" / "lock"
    if memory_dir.exists():
        try:
            shutil.rmtree(str(memory_dir), ignore_errors=True)
        except Exception:
            pass
    if lock_file.exists():
        try:
            lock_file.unlink()
        except Exception:
            pass


def _restart_gui():
    """Kill ATK-Logic.exe, restart it, and wait for TCP + GUI window ready.

    Exits on timeout.

    Cleans up unsaved-data markers first so WM_CLOSE doesn't trigger a
    blocking "recover data?" dialog.  Tries graceful close first, falls back
    to /f only if the process survives >3s.  After restart, waits for BOTH
    the TCP server AND a visible GUI window before returning — otherwise F1
    keybd_event lands on nothing (window not yet created) and the capture
    silently produces no data.
    """
    import socket
    import subprocess as sp

    # ── Step 0: clean up markers from any previous force-kill ──
    # Without this, ATK-Logic shows a "recover unsaved data?" dialog on
    # WM_CLOSE, which blocks the graceful close and causes another /f kill.
    _cleanup_unsaved_markers()

    # ── Step 1: graceful close first (WM_CLOSE), force-kill only as last resort ──
    print(f"  [sync] gracefully closing ATK-Logic.exe...")
    try:
        sp.run(["taskkill", "/im", "ATK-Logic.exe"],
               capture_output=True, timeout=10)
    except sp.TimeoutExpired:
        pass

    # Poll for process exit (up to 3 s) — WM_CLOSE may take a moment
    poll_deadline = time.time() + 3
    still_alive = False
    while time.time() < poll_deadline:
        try:
            check = sp.run(
                ["tasklist", "/fi", "IMAGENAME eq ATK-Logic.exe", "/nh"],
                capture_output=True, text=True, timeout=5
            )
            if "ATK-Logic.exe" not in check.stdout:
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        still_alive = True

    if still_alive:
        print(f"  [sync] still running after 3s, force killing...")
        try:
            sp.run(["taskkill", "/f", "/im", "ATK-Logic.exe"],
                   capture_output=True, timeout=10)
            time.sleep(0.5)
        except Exception:
            pass
        # Clean up again — /f kill may have left fresh markers
        _cleanup_unsaved_markers()

    # ── Step 1: restart GUI ──
    gui_exe = get_gui_dir() / "ATK-Logic.exe"
    print(f"  [sync] restarting GUI: {gui_exe}")
    sp.Popen(
        [str(gui_exe)],
        stdout=sp.DEVNULL, stderr=sp.DEVNULL,
        creationflags=sp.DETACHED_PROCESS if sys.platform == "win32" else 0
    )

    # ── Step 2: poll TCP until ready ──
    deadline = time.time() + 15
    tcp_ready = False
    while time.time() < deadline:
        try:
            s = socket.socket()
            s.settimeout(1)
            s.connect((TCP_HOST, TCP_PORT))
            s.close()
            tcp_ready = True
            break
        except Exception:
            time.sleep(0.5)
    if not tcp_ready:
        print(f"  [error] TCP not ready after 15s, cannot proceed")
        sys.exit(1)
    print(f"  [sync] TCP {TCP_HOST}:{TCP_PORT} ready")

    # ── Step 3: wait for GUI window to become visible ──
    # DLL server starts in DllMain (process attach), which runs BEFORE Qt
    # creates the main window.  If we return immediately after TCP connect,
    # the next capture's F1 keybd_event can land on nothing — producing
    # "Capture complete (no new .atkdl found)".
    print(f"  [sync] waiting for GUI window...")
    win_deadline = time.time() + 15
    window_found = False
    while time.time() < win_deadline:
        try:
            r = sp.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-Process -Name 'ATK-Logic' -ErrorAction SilentlyContinue |"
                 " Where-Object { $_.MainWindowTitle -ne '' }).Count"],
                capture_output=True, text=True, timeout=5
            )
            count = r.stdout.strip()
            if count and count != "0":
                window_found = True
                break
        except Exception:
            pass
        time.sleep(0.5)
    if window_found:
        print(f"  [sync] GUI window visible")
        # Extra settling time for Qt to finish painting + keyboard focus
        time.sleep(1.0)
    else:
        print(f"  [warn] GUI window not visible within 15s, proceeding anyway")


def _get_gui_start_time():
    """Get ATK-Logic.exe process start time as Unix timestamp. Returns 0 if unknown."""
    import subprocess as _sp
    try:
        r = _sp.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process -Name 'ATK-Logic' -ErrorAction SilentlyContinue |"
             " Select-Object -First 1).StartTime.ToUniversalTime().ToString('o')"],
            capture_output=True, text=True, timeout=5
        )
        ts_str = r.stdout.strip()
        if ts_str:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(ts_str)
            return dt.timestamp()
    except Exception:
        pass
    return 0.0


def configure_channels(ch_list):
    """Enable only the specified channels in set.ini before capture.

    DEPRECATED: prefer sync_set_ini(channels=..., set_hz=..., threshold=...).
    """
    from lib.lib_config_sync import sync_set_ini
    result = sync_set_ini(channels=ch_list)
    return len(result["changes"]) > 0


def read_path_ini():
    """Read trgDir from config.ini DATA_DIR. Returns Path object."""
    return _config.get_data_dir()


def sync_save_path(trgDir):
    """Ensure set.ini savePath matches trgDir. Kills/restarts GUI if mismatch.
    Returns True if GUI was restarted."""
    set_ini = APPDATA_ATK / "set.ini"
    if not set_ini.exists():
        print(f"  [warn] set.ini not found at {set_ini}, skipping savePath sync")
        return False

    text = set_ini.read_text(encoding="utf-8")
    trgDir_s = str(trgDir).replace("\\", "/")

    # Parse savePath= value
    atkDir = None
    for line in text.splitlines():
        line_s = line.strip()
        if line_s.startswith("savePath") and "=" in line_s:
            val = line_s.split("=", 1)[1].strip()
            if val:
                atkDir = val.replace("\\", "/")
            break

    if atkDir is None:
        print(f"  [warn] savePath not found in set.ini, will set to {trgDir_s}")
    elif atkDir == trgDir_s:
        print(f"  [sync] savePath already correct: {trgDir_s}")
        return False

    # Mismatch or missing — modify set.ini then restart GUI
    print(f"  [sync] savePath mismatch: set.ini={atkDir} vs trgDir={trgDir_s}")

    if atkDir is not None:
        # Try forward-slash variant first, then backslash
        new_text = text.replace(f"savePath={atkDir}", f"savePath={trgDir_s}")
        atkDir_bs = atkDir.replace("/", "\\")
        if atkDir_bs != atkDir:
            n2 = text.replace(f"savePath={atkDir_bs}", f"savePath={trgDir_s}")
            if n2 != text:
                new_text = n2
    else:
        new_text = text.rstrip("\n") + f"\nsavePath={trgDir_s}\n"

    set_ini.write_text(new_text, encoding="utf-8")
    print(f"  [sync] set.ini updated: savePath={trgDir_s}")

    _restart_gui()
    return True


def cmd_capture(args):
    import json
    import socket
    import time
    import subprocess as sp

    # ── Config sync: opt-in only ──
    # Without --sync or explicit --ch/--sample-rate-hz/--threshold, skip all
    # set.ini modification and GUI restart. Just capture with whatever the GUI
    # currently has configured.
    trgDir = read_path_ini()
    print(f"  [pre] trgDir from config.ini: {trgDir}")

    # ── Preflight status (DLL-persisted, lifetime = GUI session) ──
    # First capture in a GUI session: run preflight + set status.
    # Subsequent captures: skip preflight (already validated this session).
    # Pass capture params to preflight so it syncs set.ini BEFORE starting the
    # GUI — avoids a second GUI restart in cmd_capture's own sync step.
    preflight_ok = api_get_preflight_status()
    pf_sync_done = False  # preflight already synced params to set.ini
    if not preflight_ok:
        print("  [pre] Preflight status: NOT OK — running preflight...")
        preflight_script = str(SCRIPTS_DIR / "capture" / "atk_preflight.py")
        pf_cmd = [sys.executable, preflight_script, "--fix", "--json"]
        if args.ch is not None:
            pf_cmd.extend(["--ch", args.ch])
        if args.sample_rate_hz is not None:
            pf_cmd.extend(["--sample-rate-hz", str(args.sample_rate_hz)])
        if args.threshold is not None:
            pf_cmd.extend(["--threshold", str(args.threshold)])
        pf_result = sp.run(pf_cmd, capture_output=True, text=True, timeout=25)
        if pf_result.returncode != 0:
            _err(f"Preflight failed (exit {pf_result.returncode})")
            if pf_result.stdout:
                _err(pf_result.stdout.strip())
            sys.exit(1)
        try:
            pf_json = json.loads(pf_result.stdout.strip().split("\n")[-1])
            if pf_json.get("all_ok"):
                api_set_preflight_status(True)
                pf_sync_done = pf_json.get("sync_done", False)
                print("  [pre] Preflight passed — status set in DLL")
            else:
                _err("Preflight failed — check output above")
                sys.exit(1)
        except (json.JSONDecodeError, IndexError):
            _err("Preflight output parse error")
            sys.exit(1)
    else:
        print("  [pre] Preflight status: OK (already verified this GUI session)")

    explicit_ch = args.ch is not None
    explicit_hz = args.sample_rate_hz is not None
    explicit_threshold = args.threshold is not None
    # Skip sync if preflight already did it (params were written to set.ini
    # before GUI start — no restart needed)
    do_sync = (args.sync or explicit_ch or explicit_hz or explicit_threshold) and not pf_sync_done

    gui_restarted = False  # track for post-restart preflight re-check

    if do_sync:
        ch_list_for_sync = [int(x.strip()) for x in args.ch.split(",") if x.strip()] if explicit_ch else None
        sync_result = sync_set_ini(
            channels=ch_list_for_sync,
            set_hz=args.sample_rate_hz,
            threshold=args.threshold,
        )
        needs_restart = len(sync_result["changes"]) > 0
        save_restarted = sync_save_path(trgDir)
        if needs_restart and not save_restarted:
            _restart_gui()
        gui_restarted = needs_restart or save_restarted

        # After sync, read back actual values for display
        actual = get_set_ini_params()
        ch_list = ch_list_for_sync if explicit_ch else actual.get("channels", [0, 1, 2, 3])
        display_hz = args.sample_rate_hz if explicit_hz else actual.get("setHz", 20_000_000)
        display_threshold = args.threshold if explicit_threshold else actual.get("thresholdLevel", 1.5)
    else:
        # Read set.ini for display only — don't modify anything.
        # set.ini may be stale if the user changed channels in-GUI without
        # triggering a save (GUI only writes set.ini on exit/capture).
        actual = get_set_ini_params()
        ch_list = actual.get("channels", [0, 1, 2, 3])
        display_hz = actual.get("setHz", 20_000_000)
        display_threshold = actual.get("thresholdLevel", 1.5)
        needs_restart = False

        if pf_sync_done:
            # Preflight already synced params before starting GUI — set.ini is
            # authoritative, no staleness check needed.
            print(f"  [pre] set.ini: ch={ch_list}, {display_hz/1e6:.0f}MHz, {display_threshold}V (synced by preflight)")
        else:
            # Staleness check: compare set.ini mtime vs GUI process start time.
            # If set.ini is older, the GUI loaded these values at startup but the
            # user may have changed them in the GUI since (in-GUI changes don't
            # write back to set.ini until exit/capture).
            set_ini_path = APPDATA_ATK / "set.ini"
            set_ini_mtime = set_ini_path.stat().st_mtime if set_ini_path.exists() else 0
            gui_start = _get_gui_start_time()
            if gui_start > 0 and set_ini_mtime < gui_start:
                freshness = "⚠ stale (in-GUI changes may not be reflected)"
                hint = True
            elif gui_start > 0:
                freshness = "(fresh — written after GUI start)"
                hint = False
            else:
                freshness = "(GUI not detected)"
                hint = False

            print(f"  [pre] set.ini: ch={ch_list}, {display_hz/1e6:.0f}MHz, {display_threshold}V {freshness}")
            if hint:
                print(f"  [pre] Pass --ch/--sample-rate-hz/--threshold to enforce known values if in doubt")

    # ── Post-restart preflight re-check ──
    # _restart_gui() reloads the DLL, which resets g_preflight_ok to 0 in
    # DllMain.  If the GUI was restarted (for channel / sample-rate /
    # threshold / savePath changes), re-run preflight to validate the new
    # GUI instance.  Don't pass capture params — set.ini was already synced
    # in the do_sync block above.
    if gui_restarted:
        preflight_ok = api_get_preflight_status()
        if not preflight_ok:
            print("  [pre] Post-restart preflight: NOT OK — re-running...")
            preflight_script = str(SCRIPTS_DIR / "capture" / "atk_preflight.py")
            pf_cmd = [sys.executable, preflight_script, "--fix", "--json"]
            pf_result = sp.run(pf_cmd, capture_output=True, text=True, timeout=25)
            if pf_result.returncode != 0:
                _err(f"Post-restart preflight failed (exit {pf_result.returncode})")
                if pf_result.stdout:
                    _err(pf_result.stdout.strip())
                sys.exit(1)
            try:
                pf_json = json.loads(pf_result.stdout.strip().split("\n")[-1])
                if pf_json.get("all_ok"):
                    api_set_preflight_status(True)
                    print("  [pre] Post-restart preflight passed")
                else:
                    _err("Post-restart preflight failed — check output above")
                    sys.exit(1)
            except (json.JSONDecodeError, IndexError):
                _err("Post-restart preflight output parse error")
                sys.exit(1)
        else:
            print("  [pre] Post-restart preflight: OK")

    # ── Query isCtrlSPressed BEFORE opening main sock ──
    # DLL handles only one client at a time (g_client guard in server_thread).
    # If sock connects first, qsock is accepted at TCP level but rejected by
    # InterlockedCompareExchangePointer → closesocket immediately. The query
    # then fails with ConnectionReset or empty recv, which the old silent
    # `except: pass` hid. Moving qsock before sock fixes this race.
    isCtrlSPressed = False
    try:
        qsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        qsock.settimeout(3)
        qsock.connect(("127.0.0.1", 9876))
        qsock.sendall(b'{"cmd":"get_isCtrlSPressed"}\n')
        raw = qsock.recv(4096).decode().strip()
        if raw:
            qresp = json.loads(raw)
            if qresp.get("value") == "1":
                isCtrlSPressed = True
        qsock.close()
    except Exception as e:
        print(f"  [warn] isCtrlSPressed query failed ({e}), assuming False")

    print(f"  [pre] isCtrlSPressed = {isCtrlSPressed}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)

    try:
        sock.connect(("127.0.0.1", 9876))
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        _err(f"Cannot connect to ATK-Logic GUI at 127.0.0.1:9876 ({e})")
        _err("Please start ATK-Logic.exe first, then retry.")
        sys.exit(1)

    try:
        if args.capture_action == "start":
            duration_str = args.duration
            duration_ns = parse_time(duration_str)
            duration_s = duration_ns / 1_000_000_000

            if args.output is None:
                ts = time.strftime("%Y%m%d_%H%M%S")
                output = str(trgDir / f"capture-{ts}.atkdl")
            else:
                output = str(trgDir / Path(args.output).name)

            Path(output).parent.mkdir(parents=True, exist_ok=True)

            # Record pre-capture newest .atkdl mtime (for non-picker save detection)
            pre_mtime = 0.0
            for f in trgDir.glob("*.atkdl"):
                mt = f.stat().st_mtime
                if mt > pre_mtime:
                    pre_mtime = mt

            print(f"=== ATK-Logic Capture ===")
            print(f"  Sample rate: {display_hz / 1e6:.0f} MHz")
            print(f"  Duration:    {duration_s:.1f}s")
            print(f"  Channels:    {ch_list}")
            print(f"  Threshold:   {display_threshold} V")
            print(f"  Save name:   {Path(output).name}  (picker only; direct save detected via timestamp)")
            print(f"  RLE:         {'on' if args.rle else 'off'}")

            req = {
                "cmd": "start",
                "chs": ch_list,
                "duration_s": duration_s,
                "sample_rate_hz": display_hz,
                "threshold_v": display_threshold,
                "rle": args.rle,
            }
            # Only pass output filename for first save (picker case).
            # On subsequent saves the GUI ignores it — it overwrites in-place
            # at its last-used path. Passing it is harmless but misleading.
            if not isCtrlSPressed:
                req["output"] = output
            sock.sendall((json.dumps(req) + "\n").encode())

            # Wait for responses: progress updates then final result
            sock.settimeout(duration_s + 30)
            buf = b""
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        resp = json.loads(line.decode())
                        status = resp.get("status", "")
                        if status == "progress":
                            phase = resp.get("phase", "capture")
                            schedule = resp.get("schedule", 0)
                            print(f"\r  [{phase}] {schedule}%", end="", flush=True)
                        elif status == "ok":
                            save_prompt = resp.get("save_prompt")
                            if save_prompt == "open":
                                # First save — picker opened, use UIA to fill and save
                                filename = resp.get("filename", "capture.atkdl")
                                print(f"\r  [save] picker open, filling path via UIA...", flush=True)
                                uia_script = str(SCRIPTS_DIR / "capture" / "uia_save.py")
                                try:
                                    sp.run(
                                        [sys.executable, uia_script, filename],
                                        timeout=20, check=False
                                    )
                                except sp.TimeoutExpired:
                                    pass
                                # Verify file saved
                                dst = Path(output)
                                if dst.exists() and dst.stat().st_size > 1000:
                                    # Mark first save done so subsequent saves skip picker
                                    try:
                                        ssock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                        ssock.settimeout(3)
                                        ssock.connect(("127.0.0.1", 9876))
                                        ssock.sendall(b'{"cmd":"set_isCtrlSPressed","value":1}\n')
                                        ssock.recv(256)
                                        ssock.close()
                                    except Exception:
                                        pass
                                    print(f"\nCapture complete!")
                                    print(f"  File:    {output}")
                                    print(f"  Size:    {dst.stat().st_size / 1024:.0f} KB")
                                    return

                                print(f"\nError: file not found at {output}")
                                sys.exit(1)
                            else:
                                # save_prompt == "none" — direct save (no picker).
                                # GUI saves to its last-used path; find files newer
                                # than the pre-capture newest.
                                newest = None
                                newest_time = pre_mtime
                                for f in trgDir.glob("*.atkdl"):
                                    mt = f.stat().st_mtime
                                    if mt > newest_time:
                                        newest_time = mt
                                        newest = f
                                if newest:
                                    print(f"\nCapture complete!")
                                    print(f"  File:    {newest}")
                                    print(f"  Size:    {newest.stat().st_size / 1024:.0f} KB")
                                else:
                                    print(f"\nCapture complete (no new .atkdl found in {trgDir})")
                                return
                        elif status == "error":
                            print(f"\nError: {resp.get('msg', 'unknown error')}")
                            sys.exit(1)
                except socket.timeout:
                    print(f"\nError: Capture timed out (no response from GUI)")
                    sys.exit(1)

        elif args.capture_action == "stop":
            req = {"cmd": "stop"}
            sock.sendall((json.dumps(req) + "\n").encode())
            sock.settimeout(5)
            resp_data = sock.recv(4096)
            resp = json.loads(resp_data.decode().strip())
            if resp.get("status") == "ok":
                print("Capture stopped.")
            else:
                _err(f"Error: {resp.get('msg', 'unknown error')}")
                sys.exit(1)
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def cmd_config(args):
    """Manage ATK-Logic set.ini capture parameters.

    show — read and display set.ini params
    set  — write params to set.ini (backs up first if changes needed)
    """
    action = args.config_action

    if action == "show":
        params = get_set_ini_params()
        if not params:
            print("(no capture params found in set.ini)")
        else:
            for k, v in params.items():
                print(f"  {k}: {v}")
        return

    if action == "set":
        # Parse comma-separated channels
        ch_list = None
        if args.ch is not None:
            ch_list = [int(x.strip()) for x in args.ch.split(",") if x.strip()]
        sync_set_ini(
            channels=ch_list,
            set_hz=args.hz,
            threshold=args.threshold,
            dry_run=args.dry_run,
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    # Force UTF-8 stdout on Windows (avoid GBK codec errors with e.g. I²C)
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

    parser = argparse.ArgumentParser(
        description="ATK-Logic CLI — logic analyzer data reader and decoder"
    )
    parser.add_argument(
        "--format", choices=("json", "text"), default="json", help="Output format"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # info
    p = sub.add_parser("info", help="Show capture file metadata")
    p.add_argument("file", type=Path, help="Path to .atkdl or .bin file")
    p.set_defaults(func=cmd_info)

    # export
    p = sub.add_parser("export", help="Export edge events for channel(s)")
    p.add_argument("file", type=Path)
    p.add_argument("--ch", required=True, help="Comma-separated channel IDs, e.g. 0,2,3")
    p.add_argument("--start", default="0", help="Start time (ns/us/ms/s)")
    p.add_argument("--end", default=None, help="End time (ns/us/ms/s)")
    p.add_argument("--max-events", type=int, default=10000)
    p.set_defaults(func=cmd_export)

    # list-decoders
    p = sub.add_parser("list-decoders", help="List available protocol decoders")
    p.add_argument("--filter", default=None, help="Comma-separated decoder IDs")
    p.set_defaults(func=cmd_list_decoders)

    # decode
    p = sub.add_parser("decode", help="Decode waveform with a protocol decoder")
    p.add_argument("file", type=Path)
    p.add_argument("--decoder", required=True, help="Decoder ID, e.g. uart")
    p.add_argument("--start", default="0", help="Start time")
    p.add_argument("--end", default=None, help="End time")
    p.add_argument("--max-events", type=int, default=100000, help="Max edge events")
    p.add_argument("--rx", type=int, help="Map RX to channel N")
    p.add_argument("--tx", type=int, help="Map TX to channel N")
    p.add_argument("--scl", type=int, help="Map SCL to channel N")
    p.add_argument("--sda", type=int, help="Map SDA to channel N")
    p.add_argument("--clk", type=int, help="Map CLK to channel N")
    p.add_argument("--mosi", type=int, help="Map MOSI to channel N")
    p.add_argument("--miso", type=int, help="Map MISO to channel N")
    p.add_argument("--cs", type=int, help="Map CS to channel N")
    p.add_argument("--option", action="append", help="Decoder option as key=value")
    p.set_defaults(func=cmd_decode)

    # capture
    p = sub.add_parser("capture", help="Start/stop USB capture from logic analyzer device")
    p.add_argument("capture_action", choices=("start", "stop"), help="Start or stop capture")
    p.add_argument("--ch", type=str, default=None,
                   help="Comma-separated channel IDs. Default: use GUI current. Pass to force-sync channels.")
    p.add_argument("--duration", default="3s", help="Capture duration (ns/us/ms/s, default 3s)")
    p.add_argument("--sample-rate-hz", dest="sample_rate_hz", type=int, default=None,
                   help="Sample rate in Hz. Default: use GUI current. Pass to force-sync rate.")
    p.add_argument("--threshold", type=float, default=None,
                   help="Logic threshold voltage. Default: use GUI current. Pass to force-sync threshold.")
    p.add_argument("--sync", "-S", action="store_true", default=False,
                   help="Sync capture params + savePath to GUI before capture (may restart GUI)")
    p.add_argument("--rle", action="store_true", default=False,
                   help="Enable FPGA RLE compression (default off, matching GUI)")
    p.add_argument("--no-rle", action="store_false", dest="rle",
                   help="Disable FPGA RLE compression")
    p.add_argument("--output", "-o", default=None, help="Output .atkdl filename only (no path; always saved to DATA_DIR. default: capture_<timestamp>.atkdl)")
    p.set_defaults(func=cmd_capture)

    # config
    p = sub.add_parser("config", help="Read/write ATK-Logic set.ini capture parameters")
    p.add_argument("config_action", choices=("show", "set"),
                   help="show: display set.ini params | set: write params to set.ini")
    p.add_argument("--ch", default=None, help="Comma-separated channel IDs (e.g. 0,1,2,3)")
    p.add_argument("--hz", type=int, default=None, help="Sample rate in Hz (e.g. 20000000)")
    p.add_argument("--threshold", type=float, default=None, help="Threshold voltage (e.g. 1.5)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would change without writing")
    p.set_defaults(func=cmd_config)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
