"""
ATK-Logic pre-flight self-check.
Verifies all prerequisites before attempting waveform capture.
Usage: python atk_preflight.py [--output <filename>]
Exit code 0 = all checks passed, non-zero = at least one check failed.
"""
import os
import sys
import time
import socket
import argparse
import subprocess
from pathlib import Path

# Support running from any directory — add parent (scripts/) to path
_parent_dir = Path(__file__).resolve().parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

# ----- config (all external paths from _config.py) -----
from .._config import PROXY_EXPECTED_KB, REAL_EXPECTED_KB, TCP_HOST, TCP_PORT, SCRIPTS_DIR, APPDATA_ATK, get_data_dir, get_gui_dir
from ..lib.lib_config_sync import sync_set_ini

CLI_SCRIPT = SCRIPTS_DIR / "atk_cli.py"
WAVE_SCRIPT = SCRIPTS_DIR / "analyze" / "atk_classify.py"


def _size_kb(p: Path) -> int:
    try:
        return p.stat().st_size // 1024
    except OSError:
        return -1


def _green(s: str) -> str: return f"\033[32m{s}\033[0m"
def _red(s: str) -> str:   return f"\033[31m{s}\033[0m"
def _yellow(s: str) -> str: return f"\033[33m{s}\033[0m"


def _set_preflight_status_tcp(ok: bool):
    """Persist preflight status in proxy DLL memory (lifetime = GUI process)."""
    try:
        s = socket.socket()
        s.settimeout(3)
        s.connect((TCP_HOST, TCP_PORT))
        val = "1" if ok else "0"
        s.sendall(f'{{"cmd":"set_preflight_status","value":{val}}}\n'.encode())
        s.recv(256)
        s.close()
    except Exception:
        pass  # non-critical — cmd_capture will re-run preflight if needed


def check_proxy_dll():
    """Verify proxy DLL is deployed (not the original)."""
    gui_dir = get_gui_dir()
    proxy_dll = gui_dir / "Qt5Network.dll"
    real_dll = gui_dir / "Qt5Network_real.dll"
    proxy_kb = _size_kb(proxy_dll)
    real_kb = _size_kb(real_dll)

    if proxy_kb < 0:
        return False, f"Proxy DLL not found at {proxy_dll}"
    if PROXY_EXPECTED_KB[0] <= proxy_kb <= PROXY_EXPECTED_KB[1]:
        if real_kb < 0:
            return True, f"Proxy DLL OK ({proxy_kb} KB) — real DLL backup not found, but proxy looks correct"
        return True, f"Proxy DLL OK ({proxy_kb} KB vs real {real_kb} KB)"
    else:
        return False, f"Proxy DLL wrong size ({proxy_kb} KB) — expected ~{PROXY_EXPECTED_KB[0]}-{PROXY_EXPECTED_KB[1]} KB. Rebuild proxy_dll/src or check build flags (/MD vs /MT)"


def check_gui_running():
    """Check ATK-Logic GUI process exists."""
    try:
        result = subprocess.run(
            ["tasklist", "/fi", "IMAGENAME eq ATK-Logic.exe", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=5
        )
        if "ATK-Logic.exe" in result.stdout:
            return True, "ATK-Logic.exe is running"
        else:
            return False, f"ATK-Logic.exe NOT running — start it: {get_gui_dir() / 'ATK-Logic.exe'}"
    except Exception as e:
        return False, f"Cannot check process list: {e}"


def check_tcp():
    """Verify TCP connection to proxy DLL server."""
    try:
        s = socket.socket()
        s.settimeout(3)
        s.connect((TCP_HOST, TCP_PORT))
        s.close()
        return True, f"TCP {TCP_HOST}:{TCP_PORT} OK"
    except Exception as e:
        return False, f"TCP {TCP_HOST}:{TCP_PORT} FAILED — {e}. Is ATK-Logic running with proxy DLL?"


def check_cli():
    """Verify atk_cli.py exists."""
    if CLI_SCRIPT.exists():
        return True, f"CLI script OK: {CLI_SCRIPT}"
    return False, f"CLI script NOT found: {CLI_SCRIPT}"


def check_classify():
    """Verify atk_classify.py exists."""
    if WAVE_SCRIPT.exists():
        return True, f"Signal classifier OK: {WAVE_SCRIPT}"
    return False, f"Signal classifier NOT found: {WAVE_SCRIPT}"


def check_output(output_name: str | None):
    """Validate DATA_DIR is writable. output_name is filename-only (no path)."""
    if not output_name:
        return True, "No --output specified (will use auto-timestamp)"

    # DATA_DIR is read from config.ini
    parent = get_data_dir()
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
            return True, f"Created output directory: {parent}"
        except OSError as e:
            return False, f"Cannot create output directory {parent}: {e}"

    if not os.access(str(parent), os.W_OK):
        return False, f"Output directory not writable: {parent}"

    # Clean up stale file at output location
    dst = parent / Path(output_name).name
    warnings = []
    if dst.exists():
        if dst.is_dir():
            import shutil
            shutil.rmtree(str(dst))
            warnings.append(f"removed stale directory: {dst.name}")
        else:
            dst.unlink()
            warnings.append(f"removed stale file: {dst.name}")

    msg = f"Output path OK: {dst}"
    if warnings:
        msg += " — " + ", ".join(warnings)
    return True, msg


def _cleanup_unsaved_markers():
    """Remove ATK-Logic temp/memory markers left by a previous force-kill.

    These markers cause ATK-Logic to show a "recover unsaved data?" dialog
    on startup.  Called before starting the GUI so the first launch is clean.
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


def fix_gui_and_tcp():
    """Start GUI if not running, then poll TCP until ready (15s timeout).
    Returns (ok, msg, gui_was_running: bool)."""
    # Check if GUI already running
    try:
        result = subprocess.run(
            ["tasklist", "/fi", "IMAGENAME eq ATK-Logic.exe", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=5
        )
        gui_running = "ATK-Logic.exe" in result.stdout
    except Exception:
        gui_running = False

    if not gui_running:
        # Remove unsaved-data markers from any previous force-kill so the
        # GUI doesn't show a "recover data?" dialog on startup.
        _cleanup_unsaved_markers()

        gui_exe = get_gui_dir() / "ATK-Logic.exe"
        print(f"  Starting GUI: {gui_exe}", flush=True)
        try:
            subprocess.Popen(
                [str(gui_exe)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
            )
        except Exception as e:
            return False, f"Failed to start GUI: {e}", gui_running

    # Poll TCP until ready
    timeout_s = 15
    interval_s = 0.5
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            s = socket.socket()
            s.settimeout(1)
            s.connect((TCP_HOST, TCP_PORT))
            s.close()
            detail = "already running" if gui_running else "auto-started"
            return True, f"GUI {detail}, TCP {TCP_HOST}:{TCP_PORT} ready", gui_running
        except Exception:
            time.sleep(interval_s)

    return False, (
        f"TCP {TCP_HOST}:{TCP_PORT} not ready after {timeout_s}s — "
        "GUI may have failed to start or launched with an unexpected window class"
    ), gui_running


def main():
    import json as _json

    parser = argparse.ArgumentParser(description="ATK-Logic pre-flight check")
    parser.add_argument("--output", "-o", help="Planned output .atkdl filename only (validates DATA_DIR)")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-start GUI and wait for TCP if not running")
    parser.add_argument("--json", action="store_true",
                        help="Output machine-parseable JSON instead of human-readable text")
    parser.add_argument("--ch", help="Comma-separated channel IDs to enable (e.g. 0,1,2,3)")
    parser.add_argument("--sample-rate-hz", type=int, help="Sample rate in Hz")
    parser.add_argument("--threshold", type=float, help="Threshold voltage")
    args = parser.parse_args()

    gui_was_running = None  # only set by --fix mode

    if args.fix:
        # ── Sync capture params to set.ini BEFORE starting GUI ──
        # This way the GUI starts with the correct channels/rate/threshold,
        # avoiding a second restart in cmd_capture.
        ch_list = None
        if args.ch:
            ch_list = [int(x.strip()) for x in args.ch.split(",") if x.strip()]
        sync_done = False
        if ch_list is not None or args.sample_rate_hz is not None or args.threshold is not None:
            sync_result = sync_set_ini(
                channels=ch_list,
                set_hz=args.sample_rate_hz,
                threshold=args.threshold,
            )
            sync_done = len(sync_result["changes"]) > 0

        proxy_ok, proxy_msg = check_proxy_dll()
        gui_ok, gui_msg, gui_was_running = fix_gui_and_tcp()
        cli_ok, cli_msg = check_cli()
        classify_ok, classify_msg = check_classify()
        out_ok, out_msg = check_output(args.output)

        checks = [
            ("Proxy DLL",       proxy_ok, proxy_msg),
            ("GUI + TCP",       gui_ok, gui_msg),
            ("CLI script",      cli_ok, cli_msg),
            ("Signal classifier", classify_ok, classify_msg),
            ("Output path",     out_ok, out_msg),
        ]
    else:
        gui_ok, gui_msg = check_gui_running()
        gui_was_running = gui_ok  # if process check passes, GUI was already running

        checks = [
            ("Proxy DLL",       *check_proxy_dll()),
            ("GUI process",     gui_ok, gui_msg),
            ("TCP 9876",        *check_tcp()),
            ("CLI script",      *check_cli()),
            ("Signal classifier", *check_classify()),
            ("Output path",     *check_output(args.output)),
        ]

    all_ok = True
    results = {}

    if not args.json:
        print("=== ATK-Logic Pre-flight ===\n")

    for item in checks:
        if len(item) == 3:
            name, ok, msg = item
        else:
            name, ok, msg = item[0], item[1], item[2] if len(item) > 2 else ""

        if not args.json:
            status = _green("PASS") if ok else _red("FAIL")
            print(f"  [{status}] {name}: {msg}")

        results[name] = {"status": "pass" if ok else "fail", "message": msg}
        if not ok:
            all_ok = False

    if args.json:
        output = {"all_ok": all_ok, "checks": results}
        if gui_was_running is not None:
            output["gui_was_running"] = gui_was_running
            output["sync_done"] = sync_done
        print(_json.dumps(output, ensure_ascii=False))
    else:
        print()
        if all_ok:
            print(_green("All checks passed — ready to capture."))
        else:
            print(_red("Some checks FAILED — fix issues above before capturing."))

    # Persist preflight status in DLL so cmd_capture can skip re-running
    if all_ok:
        _set_preflight_status_tcp(True)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
