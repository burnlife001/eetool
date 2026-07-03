"""
ATK-Logic Capture — centralized path configuration.
Import this module to get all external paths; nothing else should hardcode paths.
"""
from pathlib import Path

# —— self location ——
SCRIPTS_DIR = Path(__file__).resolve().parent   # .../skills/atk-logic-capture/scripts/
SKILL_DIR = SCRIPTS_DIR.parent                   # .../skills/atk-logic-capture/

# —— external binaries (immovable: closed-source GUI + DLL hijack requirement) ——
# GUI_DIR is read from config.ini at runtime — see get_gui_dir() below.

# —— capture data & logs ——
# DATA_DIR is read from config.ini at runtime — see get_data_dir() below.

# —— ATK-Logic appdata ——
APPDATA_ATK = Path("C:/Users/yg/AppData/Roaming/ALIENTEK/ATK-LogicView")

# —— config.ini ——
CONFIG_INI = SCRIPTS_DIR / "config.ini"


def get_data_dir() -> Path:
    """Read DATA_DIR from config.ini. Returns Path, or hardcoded fallback if missing."""
    if CONFIG_INI.exists():
        text = CONFIG_INI.read_text(encoding="utf-8")
        for line in text.splitlines():
            line_s = line.strip()
            if line_s.lower().startswith("data_dir") and "=" in line_s:
                val = line_s.split("=", 1)[1].strip()
                return Path(val)
    # Fallback — should only trigger if config.ini is missing
    return Path("E:/__electric/atk-logic-data/")


def get_log_dir() -> Path:
    """Return LOG_DIR derived from DATA_DIR."""
    return get_data_dir() / "logs"


def get_gui_dir() -> Path:
    """Read GUI_DIR from config.ini. Returns Path, or hardcoded fallback if missing."""
    if CONFIG_INI.exists():
        text = CONFIG_INI.read_text(encoding="utf-8")
        for line in text.splitlines():
            line_s = line.strip()
            if line_s.lower().startswith("gui_dir") and "=" in line_s:
                val = line_s.split("=", 1)[1].strip()
                return Path(val)
    # Fallback — should only trigger if config.ini is missing
    return Path("D:/Programs/ATK-Logic")

# —— TCP ——
TCP_HOST = "127.0.0.1"
TCP_PORT = 9876

# —— DLL size expectations (KB) ——
PROXY_EXPECTED_KB = (250, 400)
REAL_EXPECTED_KB = (1200, 1500)
