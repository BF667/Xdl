"""
Base class for all site-specific downloaders.
"""

import os
import time
import threading
from abc import ABC, abstractmethod
from typing import Optional, Callable
from ..core.models import DownloadItem, DownloadStatus


class BaseDownloader(ABC):
    """Abstract base class for site-specific downloaders."""

    name: str = "Base"
    supported_domains: list = []

    def __init__(self):
        self._stop_events: dict = {}
        self.on_progress: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Check if this downloader can handle the given URL."""
        pass

    @abstractmethod
    def get_info(self, url: str) -> dict:
        """Get file/video information without downloading."""
        pass

    @abstractmethod
    def download(self, item: DownloadItem, stop_event: threading.Event):
        """Download the item. Must respect stop_event for pause/cancel."""
        pass

    def start(self, item: DownloadItem) -> threading.Thread:
        """Start downloading in a separate thread."""
        stop_event = threading.Event()
        self._stop_events[item.id] = stop_event

        thread = threading.Thread(
            target=self._run_download,
            args=(item, stop_event),
            daemon=True
        )
        thread.start()
        return thread

    def _run_download(self, item: DownloadItem, stop_event: threading.Event):
        """Run download with error handling."""
        try:
            item.status = DownloadStatus.DOWNLOADING
            item.started_at = time.time()
            self.download(item, stop_event)

            if not stop_event.is_set():
                item.status = DownloadStatus.COMPLETED
                item.progress = 100.0
                item.completed_at = time.time()
                item.speed = 0.0
                if self.on_complete:
                    self.on_complete(item)

        except Exception as e:
            if stop_event.is_set():
                item.status = DownloadStatus.PAUSED
            else:
                item.status = DownloadStatus.ERROR
                item.error_message = str(e)
                if self.on_error:
                    self.on_error(item)

    def stop(self, item_id: str):
        """Signal the download to stop."""
        if item_id in self._stop_events:
            self._stop_events[item_id].set()

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format bytes to human-readable size."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
