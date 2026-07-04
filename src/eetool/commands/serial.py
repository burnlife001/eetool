import argparse
import configparser
import enum
import os
import signal
import sys
import time
from pathlib import Path

from eetool.core.locks import ProcessLock

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # pragma: no cover
    serial = None


class CMDS(enum.Enum):
    k1 = "k1"
    k2 = "k2"
    k3 = "k3"
    k4 = "k4"


_DEFAULT_LOG = "C:/Users/yg/AppData/Local/Temp/yg8_uart.txt"
_SERIAL_INI = Path.home() / ".local" / "share" / "eetool" / "serial.ini"


def find_ch340_ports():
    """Return list of (device, description) for CH340-based COM ports."""
    if serial is None:  # pragma: no cover
        return [], []
    ch340 = []
    all_ports = []
    for p in serial.tools.list_ports.comports():
        all_ports.append((p.device, p.description))
        if "CH340" in p.description.upper():
            ch340.append((p.device, p.description))
    return ch340, all_ports


def list_ports():
    """Print all serial ports, marking CH340."""
    if serial is None:  # pragma: no cover
        print("[ERROR] pyserial not installed.")
        return 1
    ch340, all_ports = find_ch340_ports()
    if not all_ports:
        print("[INFO] No serial ports detected.")
        return 0

    print(f"{'PORT':<12} DESCRIPTION")
    print("-" * 50)
    for dev, desc in all_ports:
        marker = " ★ CH340" if any(dev == c[0] for c in ch340) else ""
        print(f"{dev:<12} {desc}{marker}")

    if ch340:
        print(f"\n[INFO] Found {len(ch340)} CH340 port(s).")
    return 0


def _resolve_port(port):
    if port:
        return port
    if serial is None:  # pragma: no cover
        return None
    ch340, _ = find_ch340_ports()
    if len(ch340) == 0:
        print("[ERROR] No CH340 port found. Use --list to view available ports, then --port to specify.")
        return None
    if len(ch340) > 1:
        print(f"[INFO] Multiple CH340 ports found, using first: {ch340[0][0]}")
    return ch340[0][0]


# ── INI persistence ──────────────────────────────────────────────────────────

def load_serial_config():
    """Load saved serial settings from INI. Returns dict with typed values."""
    config = configparser.ConfigParser()
    if not _SERIAL_INI.exists():
        return {}
    config.read(_SERIAL_INI, encoding="utf-8")
    if not config.has_section("serial"):
        return {}

    raw = dict(config.items("serial"))
    result: dict = {}

    for key in ("baud", "bytesize"):
        if key in raw and raw[key].strip():
            try:
                result[key] = int(raw[key])
            except ValueError:
                pass

    if "stopbits" in raw and raw["stopbits"].strip():
        try:
            result["stopbits"] = float(raw["stopbits"])
        except ValueError:
            pass

    if "timeout" in raw and raw["timeout"].strip():
        try:
            result["timeout"] = float(raw["timeout"])
        except ValueError:
            pass

    if "hex" in raw:
        result["hex"] = raw["hex"].lower() == "true"

    for key in ("port", "parity"):
        if key in raw:
            result[key] = raw[key]

    return result


def save_serial_config(args):
    """Save current serial settings to INI."""
    _SERIAL_INI.parent.mkdir(parents=True, exist_ok=True)
    config = configparser.ConfigParser()
    config["serial"] = {}

    if getattr(args, "port", None):
        config["serial"]["port"] = args.port
    if getattr(args, "baud", None) is not None:
        config["serial"]["baud"] = str(args.baud)
    if getattr(args, "bytesize", None) is not None:
        config["serial"]["bytesize"] = str(args.bytesize)
    if getattr(args, "parity", None) is not None:
        config["serial"]["parity"] = args.parity
    if getattr(args, "stopbits", None) is not None:
        config["serial"]["stopbits"] = str(args.stopbits)
    if getattr(args, "hex", None) is not None:
        config["serial"]["hex"] = str(args.hex).lower()
    if getattr(args, "timeout", None) is not None:
        config["serial"]["timeout"] = str(args.timeout)

    with open(_SERIAL_INI, "w", encoding="utf-8") as f:
        config.write(f)


def _apply_ini_defaults(args):
    """Apply saved INI defaults to args when a value was not provided."""
    ini = load_serial_config()
    defaults = {
        "port": None,
        "baud": 115200,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1.0,
        "hex": False,
        "timeout": None,
    }
    for key, fallback in defaults.items():
        value = getattr(args, key, None)
        if value is None:
            setattr(args, key, ini.get(key, fallback))


# ── serial open / helpers ────────────────────────────────────────────────────

def _open_serial(port, baud, bytesize, parity, stopbits, timeout=0.5):
    if serial is None:  # pragma: no cover
        print("[ERROR] pyserial not installed.")
        return None

    parity_map = {
        "N": serial.PARITY_NONE,
        "E": serial.PARITY_EVEN,
        "O": serial.PARITY_ODD,
        "M": serial.PARITY_MARK,
        "S": serial.PARITY_SPACE,
    }
    byte_map = {
        5: serial.FIVEBITS,
        6: serial.SIXBITS,
        7: serial.SEVENBITS,
        8: serial.EIGHTBITS,
    }
    stop_map = {
        1: serial.STOPBITS_ONE,
        1.5: serial.STOPBITS_ONE_POINT_FIVE,
        2: serial.STOPBITS_TWO,
    }

    try:
        return serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=byte_map.get(bytesize, serial.EIGHTBITS),
            parity=parity_map.get(parity, serial.PARITY_NONE),
            stopbits=stop_map.get(stopbits, serial.STOPBITS_ONE),
            timeout=timeout,
        )
    except serial.SerialException as e:
        print(f"[ERROR] Cannot open {port}: {e}")
        return None


def _sendcmd(ser, cmd):
    text = cmd.value if isinstance(cmd, CMDS) else cmd
    data = (text + "\r\n").encode("ascii")
    ser.write(data)
    ser.flush()
    print(f"[SEND] {text}")


_keep_running = True


def _on_sigint(signum, frame):
    global _keep_running
    _keep_running = False


def _read_loop(ser, *, fmt="ascii", log_file=None, timeout=None):
    global _keep_running
    _keep_running = True
    signal.signal(signal.SIGINT, _on_sigint)

    last_data_ts = time.time()
    line_count = 0

    print(f"[INFO] Connected to {ser.port} @ {ser.baudrate} baud ({ser.bytesize}{ser.parity[0]}{ser.stopbits})")
    print("[INFO] Press Ctrl+C to stop.\n")

    fh = open(log_file, "w", encoding="utf-8") if log_file else None

    try:
        while _keep_running:
            try:
                if ser.in_waiting:
                    raw = ser.readline()
                    if not raw:
                        continue

                    last_data_ts = time.time()
                    line_count += 1

                    if fmt == "hex":
                        text = raw.hex(" ").upper()
                    else:
                        text = raw.decode("ascii", errors="replace").rstrip("\n").rstrip("\r")

                    print(text, flush=True)

                    if fh:
                        fh.write(text + "\n")
                        fh.flush()
                else:
                    time.sleep(0.01)
                    if timeout and (time.time() - last_data_ts > timeout):
                        print(f"\n[INFO] Idle timeout ({timeout}s) reached. Disconnecting.")
                        break
            except serial.SerialException as e:
                print(f"\n[ERROR] Serial error: {e}")
                break
    finally:
        if fh:
            fh.close()
            print(f"\n[INFO] Log saved to: {Path(log_file).resolve()}")
        ser.close()
        print(f"[INFO] Disconnected. {line_count} lines received.")


def send_command(args):
    port = _resolve_port(args.port)
    if not port:
        return 1
    args.port = port
    lock = ProcessLock(f"serial-{port}")
    with lock:
        ser = _open_serial(
            port,
            args.baud,
            args.bytesize,
            args.parity,
            args.stopbits,
        )
        if ser is None:
            return 1
        try:
            _sendcmd(ser, args.cmd)
        finally:
            ser.close()
        save_serial_config(args)
    return 0


def listen_port(args):
    port = _resolve_port(args.port)
    if not port:
        return 1
    args.port = port
    lock = ProcessLock(f"serial-{port}")
    with lock:
        ser = _open_serial(
            port,
            args.baud,
            args.bytesize,
            args.parity,
            args.stopbits,
        )
        if ser is None:
            return 1
        try:
            _read_loop(
                ser,
                fmt="hex" if args.hex else "ascii",
                log_file=args.log,
                timeout=args.timeout,
            )
        finally:
            save_serial_config(args)
    return 0


def add_subparser(subparsers):
    parser = subparsers.add_parser("serial", help="Serial port tools")
    sub = parser.add_subparsers(dest="serial_command", required=True)

    listen = sub.add_parser("listen", help="Listen to a serial port")
    listen.add_argument("--port", default=None)
    listen.add_argument("--baud", type=int, default=None)
    listen.add_argument("--bytesize", type=int, default=None, choices=[5, 6, 7, 8])
    listen.add_argument("--parity", default=None, choices=["N", "E", "O", "M", "S"])
    listen.add_argument("--stopbits", type=float, default=None, choices=[1, 1.5, 2])
    listen.add_argument("--hex", action="store_true", default=None)
    listen.add_argument("--timeout", type=float, default=None)
    listen.add_argument("--log", default=_DEFAULT_LOG)

    send = sub.add_parser("send", help="Send a command")
    send.add_argument("cmd", choices=[c.value for c in CMDS])
    send.add_argument("--port", default=None)
    send.add_argument("--baud", type=int, default=None)
    send.add_argument("--bytesize", type=int, default=None, choices=[5, 6, 7, 8])
    send.add_argument("--parity", default=None, choices=["N", "E", "O", "M", "S"])
    send.add_argument("--stopbits", type=float, default=None, choices=[1, 1.5, 2])

    sub.add_parser("list", help="List COM ports")


def run(args):
    if args.serial_command == "list":
        return list_ports()
    if args.serial_command == "send":
        _apply_ini_defaults(args)
        return send_command(args)
    if args.serial_command == "listen":
        _apply_ini_defaults(args)
        return listen_port(args)
    return 1
