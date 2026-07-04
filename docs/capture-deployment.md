# ATK-Logic Capture

CLI-based capture & waveform analysis for the ATK-Logic USB logic analyzer (ALIENTEK), deployed as a [Claude Code](https://claude.com/claude-code) skill.

## Quick Start

```powershell
# One-shot deploy
pwsh install.ps1

# Capture 2 seconds on CH0+CH1
eetool capture start --ch 0,1 --duration 2s

# Analyze captured waveform
eetool capture classify <file.atkdl>
```

## Prerequisites

- Windows 10/11 x64
- PowerShell 7+
- Python 3.12+ (on PATH)
- ATK-Logic USB logic analyzer hardware
- ATK-Logic GUI installed (from ALIENTEK)

## What install.ps1 Does

| Step | Action |
|------|--------|
| 1 | Creates `.venv`, installs `eetool` in editable mode, and symlinks `eetool.exe` to `~/.local/bin` |
| 2 | Creates the `~/.claude/skills/eetool` junction pointing to the project root |
| 3 | Finds ATK-Logic GUI across 8+ standard install paths |
| 4 | Deploys proxy DLL: backs up `Qt5Network.dll` → `Qt5Network_real.dll`, then installs the proxy |
| 5 | Updates `src/eetool/capture/config.ini` and `_config.py` fallback paths with local paths (GUI, appdata) |
| 6 | Ensures the Python dependency `uiautomation` is installed |
| 7 | Runs preflight self-check (`python -m eetool.capture.capture.atk_preflight --fix`) |

## Directory Layout

```
project root (eetool/)
├── SKILL.md              # Skill manifest (Claude Code)
├── README.md             # Project README
├── install.ps1           # One-shot deployment script
├── proxy_dll/
│   ├── outdll/
│   │   └── Qt5Network.dll    # Pre-built proxy DLL (~307 KB)
│   ├── proxy_main.c
│   ├── Qt5Network_proxy.def
│   ├── build.ps1
│   └── README.md
└── src/eetool/capture/
    ├── _config.py         # Centralized path configuration
    ├── _bootstrap.py      # DLL search path setup
    ├── atk_cli.py         # Main CLI: info, export, decode, capture
    ├── capture/atk_preflight.py   # Pre-flight self-check (with --fix auto-repair)
    ├── analyze/atk_classify.py    # Signal classifier (auto-scans channels)
    ├── analyze/atk_pwm.py         # PWM / breathing LED analyzer
    ├── uia_save.py        # UIA automation for Save As dialog
    └── lib/
        ├── lib_reader.py  # .atkdl / .bin file reader
        ├── lib_proto.py   # Native protocol decoders (UART, I²C, SPI)
        └── lib_decoder.py # libsigrokdecode bridge (Python 3.14+, optional)
```

## Manual Deploy

If `install.ps1` doesn't fit your environment, follow these steps:

### 1. Install the package

```powershell
pip install -e .
```

### 2. Install Python dependency

```powershell
pip install uiautomation
```

### 3. Deploy proxy DLL

In the ATK-Logic install directory:

```powershell
ren Qt5Network.dll Qt5Network_real.dll
copy <eetool-root>/proxy_dll/outdll/Qt5Network.dll .
```

If no pre-built DLL, build with MSVC: `cd proxy_dll && pwsh build.ps1`

### 4. Edit config

Edit `src/eetool/capture/config.ini`:

```ini
[atk-logic]
GUI_DIR = D:/Programs/ATK-Logic
DATA_DIR = E:/__electric/atk-logic-data
```

### 5. Verify

```powershell
python -m eetool.capture.capture.atk_preflight --fix
```

All 4 checks PASS = ready.

## License

MIT
