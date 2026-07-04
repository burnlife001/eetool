import argparse
import enum
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


def _open_serial(port, baud):
    if serial is None:  # pragma: no cover
        print("[ERROR] pyserial not installed.")
        return None
    try:
        return serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
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

    print(f"[INFO] Connected to {ser.port} @ {ser.baudrate} baud")
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
    lock = ProcessLock(f"serial-{port}")
    with lock:
        ser = _open_serial(port, args.baud)
        if ser is None:
            return 1
        try:
            _sendcmd(ser, args.cmd)
        finally:
            ser.close()
    return 0


def listen_port(args):
    port = _resolve_port(args.port)
    if not port:
        return 1
    lock = ProcessLock(f"serial-{port}")
    with lock:
        ser = _open_serial(port, args.baud)
        if ser is None:
            return 1
        _read_loop(
            ser,
            fmt="hex" if args.hex else "ascii",
            log_file=args.log,
            timeout=args.timeout,
        )
    return 0


def add_subparser(subparsers):
    parser = subparsers.add_parser("serial", help="Serial port tools")
    sub = parser.add_subparsers(dest="serial_command", required=True)

    listen = sub.add_parser("listen", help="Listen to a serial port")
    listen.add_argument("--port", default=None)
    listen.add_argument("--baud", type=int, default=115200)
    listen.add_argument("--hex", action="store_true")
    listen.add_argument("--timeout", type=float, default=None)
    listen.add_argument("--log", default=_DEFAULT_LOG)

    send = sub.add_parser("send", help="Send a command")
    send.add_argument("cmd", choices=[c.value for c in CMDS])
    send.add_argument("--port", default=None)
    send.add_argument("--baud", type=int, default=115200)

    sub.add_parser("list", help="List COM ports")


def run(args):
    if args.serial_command == "list":
        return list_ports()
    if args.serial_command == "send":
        return send_command(args)
    if args.serial_command == "listen":
        return listen_port(args)
    return 1
