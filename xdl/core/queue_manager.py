"""
Download queue manager with scheduling, prioritization,
and concurrent download limiting.
"""

import time
import threading
from typing import Optional, List, Callable
from .models import DownloadItem, DownloadStatus
from .engine import DownloadEngine


class QueueManager:
    """
    Manages the download queue with:
    - Concurrent download limiting
    - Priority-based scheduling
    - Automatic queue processing
    - Start time scheduling
    """

    def __init__(self, engine: DownloadEngine, max_concurrent: int = 3):
        self.engine = engine
        self.max_concurrent = max_concurrent

        self._queue: List[DownloadItem] = []
        self._completed: List[DownloadItem] = []
        self._lock = threading.Lock()
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Callbacks
        self.on_item_added: Optional[Callable] = None
        self.on_item_started: Optional[Callable] = None
        self.on_item_completed: Optional[Callable] = None
        self.on_queue_changed: Optional[Callable] = None

        # Wire up engine callbacks
        self.engine.on_complete = self._handle_complete
        self.engine.on_error = self._handle_error
        self.engine.on_progress = self._handle_progress

    def add(self, item: DownloadItem) -> str:
        """Add an item to the download queue."""
        with self._lock:
            item.status = DownloadStatus.QUEUED
            self._queue.append(item)

        if self.on_item_added:
            self.on_item_added(item)

        if self.on_queue_changed:
            self.on_queue_changed()

        # Auto-start processing
        if not self._running:
            self.start_processing()

        return item.id

    def remove(self, item_id: str) -> bool:
        """Remove an item from the queue."""
        with self._lock:
            # Check active queue
            for i, item in enumerate(self._queue):
                if item.id == item_id:
                    if self.engine.is_downloading(item_id):
                        self.engine.cancel_download(item_id)
                    self._queue.pop(i)
                    if self.on_queue_changed:
                        self.on_queue_changed()
                    return True

            # Check completed
            for i, item in enumerate(self._completed):
                if item.id == item_id:
                    self._completed.pop(i)
                    if self.on_queue_changed:
                        self.on_queue_changed()
                    return True

        return False

    def pause(self, item_id: str):
        """Pause a download."""
        with self._lock:
            for item in self._queue:
                if item.id == item_id:
                    self.engine.pause_download(item_id)
                    item.status = DownloadStatus.PAUSED
                    if self.on_queue_changed:
                        self.on_queue_changed()
                    break

    def resume(self, item_id: str):
        """Resume a paused download."""
        with self._lock:
            for item in self._queue:
                if item.id == item_id and item.status in (
                    DownloadStatus.PAUSED, DownloadStatus.ERROR
                ):
                    item.status = DownloadStatus.PENDING
                    self.engine.resume_download(item)
                    if self.on_queue_changed:
                        self.on_queue_changed()
                    break

    def move_up(self, item_id: str):
        """Move an item up in the queue."""
        with self._lock:
            for i, item in enumerate(self._queue):
                if item.id == item_id and i > 0:
                    # Don't move items that are actively downloading
                    if item.status == DownloadStatus.DOWNLOADING:
                        break
                    self._queue[i], self._queue[i - 1] = self._queue[i - 1], self._queue[i]
                    break

        if self.on_queue_changed:
            self.on_queue_changed()

    def move_down(self, item_id: str):
        """Move an item down in the queue."""
        with self._lock:
            for i, item in enumerate(self._queue):
                if item.id == item_id and i < len(self._queue) - 1:
                    if item.status == DownloadStatus.DOWNLOADING:
                        break
                    next_item = self._queue[i + 1]
                    if next_item.status == DownloadStatus.DOWNLOADING:
                        break
                    self._queue[i], self._queue[i + 1] = self._queue[i + 1], self._queue[i]
                    break

        if self.on_queue_changed:
            self.on_queue_changed()

    def start_processing(self):
        """Start the queue processor."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._processor_thread = threading.Thread(
            target=self._process_queue, daemon=True
        )
        self._processor_thread.start()

    def stop_processing(self):
        """Stop the queue processor."""
        self._running = False
        self._stop_event.set()

    def _process_queue(self):
        """Main queue processing loop."""
        while not self._stop_event.is_set():
            with self._lock:
                # Count active downloads
                active = sum(
                    1 for item in self._queue
                    if item.status == DownloadStatus.DOWNLOADING
                )

                # Start next queued items
                if active < self.max_concurrent:
                    for item in self._queue:
                        if item.status in (DownloadStatus.QUEUED, DownloadStatus.PENDING):
                            self.engine.start_download(item)
                            if self.on_item_started:
                                self.on_item_started(item)
                            active += 1
                            if active >= self.max_concurrent:
                                break

            self._stop_event.wait(1.0)

    def _handle_complete(self, item: DownloadItem):
        """Handle download completion."""
        with self._lock:
            # Move from queue to completed
            for i, q_item in enumerate(self._queue):
                if q_item.id == item.id:
                    self._queue.pop(i)
                    break
            self._completed.append(item)

        if self.on_item_completed:
            self.on_item_completed(item)
        if self.on_queue_changed:
            self.on_queue_changed()

    def _handle_error(self, item: DownloadItem):
        """Handle download error."""
        if self.on_queue_changed:
            self.on_queue_changed()

    def _handle_progress(self, item: DownloadItem):
        """Handle download progress update."""
        # Progress is handled by the GUI directly
        pass

    def get_all_items(self) -> List[DownloadItem]:
        """Get all items (queue + completed)."""
        with self._lock:
            return list(self._queue) + list(self._completed)

    def get_queue_items(self) -> List[DownloadItem]:
        """Get queued/active items."""
        with self._lock:
            return list(self._queue)

    def get_completed_items(self) -> List[DownloadItem]:
        """Get completed items."""
        with self._lock:
            return list(self._completed)

    def get_item(self, item_id: str) -> Optional[DownloadItem]:
        """Get a specific item by ID."""
        for item in self.get_all_items():
            if item.id == item_id:
                return item
        return None

    def clear_completed(self):
        """Clear all completed downloads."""
        with self._lock:
            self._completed.clear()
        if self.on_queue_changed:
            self.on_queue_changed()

    def get_stats(self) -> dict:
        """Get queue statistics."""
        with self._lock:
            total = len(self._queue) + len(self._completed)
            downloading = sum(1 for i in self._queue if i.status == DownloadStatus.DOWNLOADING)
            queued = sum(1 for i in self._queue if i.status == DownloadStatus.QUEUED)
            paused = sum(1 for i in self._queue if i.status == DownloadStatus.PAUSED)
            completed = len(self._completed)
            errors = sum(1 for i in self._queue if i.status == DownloadStatus.ERROR)

            total_speed = sum(i.speed for i in self._queue if i.status == DownloadStatus.DOWNLOADING)

        return {
            "total": total,
            "downloading": downloading,
            "queued": queued,
            "paused": paused,
            "completed": completed,
            "errors": errors,
            "total_speed": total_speed,
        }
