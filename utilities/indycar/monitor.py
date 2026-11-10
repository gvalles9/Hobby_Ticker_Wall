"""Background monitor for the INDYCAR feeds.

``SceneManager.kick()`` calls every scene's ``poll()`` on each render
frame (about 12.5 times a second).  Fetching a feed there would stall the
display, so the polling service runs in a daemon thread and scenes only
read the latest immutable :class:`~utilities.indycar.models.Snapshot`.
"""

from __future__ import annotations

import logging
import threading
import time

from utilities.indycar.models import Snapshot
from utilities.indycar.service import IndyCarService

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5.0


class IndyCarMonitor:
    """Singleton daemon thread that keeps one fresh snapshot available."""

    _instance: IndyCarMonitor | None = None

    @classmethod
    def instance(cls) -> IndyCarMonitor:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Stop and drop the singleton (used by tests and config reloads)."""
        if cls._instance is not None:
            cls._instance.stop()
            cls._instance = None

    def __init__(
        self,
        service: IndyCarService | None = None,
        interval: float = POLL_INTERVAL_SECONDS,
    ) -> None:
        self.service = service or IndyCarService()
        self.interval = max(1.0, float(interval))
        self._snapshot = Snapshot()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        """Start the background poller once; safe to call repeatedly."""
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="indycar-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None

    def snapshot(self) -> Snapshot:
        """Return the latest snapshot immediately (never fetches)."""
        with self._lock:
            return self._snapshot

    def refresh(self, *, force: bool = True) -> Snapshot:
        """Fetch synchronously; intended for tests and manual refresh."""
        try:
            snapshot = self.service.snapshot(force=force)
        except Exception as exc:  # keep the scene protocol exception-free
            logger.warning("INDYCAR refresh failed: %s", exc)
            snapshot = Snapshot(
                fetched_at=time.time(),
                error=f"{type(exc).__name__}: {exc}",
            )
        with self._lock:
            self._snapshot = snapshot
        return snapshot

    def _run(self) -> None:
        logger.info("INDYCAR monitor started")
        while not self._stop.is_set():
            self.refresh()
            self._stop.wait(self.interval)
        logger.info("INDYCAR monitor stopped")
