"""Bootstrap: add lib/bin/ to the DLL search path so .pyd extensions load."""
import os
import sys
from pathlib import Path

_BIN = Path(__file__).parent.parent / "lib" / "bin"
if _BIN.exists():
    os.add_dll_directory(str(_BIN.resolve()))
