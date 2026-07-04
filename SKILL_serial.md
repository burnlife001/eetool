---
name: eetool-serial
description: Serial-port read/write/list with cross-process locking. Triggers on: eetool serial, 串口, COM port, serial listen, serial send, serial list.
---

# eetool-serial

Deep dive for `eetool serial ...`. Read `SKILL.md` first for routing.

## Subcommands

| Subcommand | Purpose |
|------------|---------|
| `eetool serial list` | Enumerate COM ports with metadata (VID/PID, description). |
| `eetool serial listen --port COMx` | Stream bytes from a port (cross-process locked). |
| `eetool serial send --port COMx --data "..."` | Send bytes / hex string to a port. |

Settings (baudrate, bytesize, parity, stopbits, timeout) are persisted to
`~/.local/share/eetool/serial.ini` so subsequent calls don't need to repeat
them.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Port busy | Another process holds COM | Close other serial tools; `ProcessLock` serializes within eetool |
| Permission denied | Insufficient rights | Run terminal as user with device access |
| Garbled output | Baud/parity/stopbits mismatch | Match MCU config with `--baudrate --bytesize --parity --stopbits` |
| No data received | Timeout too short | Increase `--timeout` or leave unset |

## Concurrency

Hardware-dependent commands (`serial`, `capture`) acquire a `ProcessLock`
so concurrent invocations serialize access to the device. Multiple CLI
processes talking to the same COM port will queue, not corrupt.

## Typical session

```bash
# Discover ports
eetool serial list

# Open a session — defaults match 115200 8N1 with 30s timeout
eetool serial listen --port COM7

# In another shell, send a command to the device
eetool serial send --port COM7 --data "AT+VERSION\r\n"
```
