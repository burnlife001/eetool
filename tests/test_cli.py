import subprocess
import sys


def test_ee_help():
    result = subprocess.run(
        [sys.executable, "-m", "ee_toolkit.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout
