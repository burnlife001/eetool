import os
import tempfile
from pathlib import Path

import pytest

from eetool.core.locks import ProcessLock


def test_process_lock_acquires_and_releases():
    with tempfile.TemporaryDirectory() as tmp:
        lock = ProcessLock("test-lock", base_dir=tmp)
        with lock:
            assert Path(lock.lock_path).exists()
        assert not Path(lock.lock_path).exists()


def test_process_lock_blocks_second_acquire():
    with tempfile.TemporaryDirectory() as tmp:
        lock1 = ProcessLock("same-lock", base_dir=tmp)
        lock2 = ProcessLock("same-lock", base_dir=tmp)
        with lock1:
            with pytest.raises(RuntimeError, match="already held"):
                with lock2:
                    pass
