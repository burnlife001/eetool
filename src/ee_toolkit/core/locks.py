import tempfile
from pathlib import Path

from filelock import FileLock, Timeout


class ProcessLock:
    def __init__(self, name: str, base_dir: str | None = None, timeout: float = 0):
        if base_dir is None:
            base_dir = tempfile.gettempdir()
        self.lock_path = Path(base_dir) / f"ee-{name}.lock"
        self.timeout = timeout
        self._lock = FileLock(str(self.lock_path))

    def __enter__(self):
        try:
            self._lock.acquire(timeout=self.timeout)
        except Timeout:
            raise RuntimeError(
                f"Resource lock '{self.lock_path.name}' is already held by another process."
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._lock.release()
        except RuntimeError:
            pass
        return False

    def is_locked(self) -> bool:
        return self._lock.is_locked
