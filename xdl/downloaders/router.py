"""
Download router - automatically selects the appropriate downloader
based on the URL and manages downloader instances.
"""

import threading
from typing import Optional, List, Type

from .base import BaseDownloader
from .youtube import YouTubeDownloader
from .gdrive import GDriveDownloader
from .mediafire import MediaFireDownloader
from .pixeldrain import PixeldrainDownloader
from .huggingface import HuggingFaceDownloader
from .generic import GenericDownloader
from ..core.models import DownloadItem, DownloadStatus, DownloadCategory


class DownloadRouter:
    """
    Routes download requests to the appropriate site-specific downloader.
    Falls back to the generic HTTP downloader when no specific handler is found.
    """

    def __init__(self):
        self._downloaders: List[BaseDownloader] = [
            YouTubeDownloader(),
            GDriveDownloader(),
            MediaFireDownloader(),
            PixeldrainDownloader(),
            HuggingFaceDownloader(),
        ]
        self._fallback = GenericDownloader()

        # Active download threads
        self._threads: dict = {}
        self._stop_events: dict = {}

        # Callbacks
        self.on_progress = None
        self.on_complete = None
        self.on_error = None

        # Wire up callbacks for all downloaders
        for downloader in self._downloaders:
            downloader.on_progress = self._forward_progress
            downloader.on_complete = self._forward_complete
            downloader.on_error = self._forward_error
        self._fallback.on_progress = self._forward_progress
        self._fallback.on_complete = self._forward_complete
        self._fallback.on_error = self._forward_error

    def _forward_progress(self, item):
        if self.on_progress:
            self.on_progress(item)

    def _forward_complete(self, item):
        if self.on_complete:
            self.on_complete(item)

    def _forward_error(self, item):
        if self.on_error:
            self.on_error(item)

    def detect_site(self, url: str) -> str:
        """Detect which site a URL belongs to."""
        downloader = self.get_downloader(url)
        return downloader.name

    def _find_downloader(self, url: str) -> Optional[BaseDownloader]:
        """Find the appropriate downloader for a URL."""
        for downloader in self._downloaders:
            if downloader.can_handle(url):
                return downloader
        # Check fallback
        if self._fallback.can_handle(url):
            return self._fallback
        return None

    def get_downloader(self, url: str) -> BaseDownloader:
        """Get the downloader for a URL (fallback to generic)."""
        downloader = self._find_downloader(url)
        return downloader if downloader else self._fallback

    def get_info(self, url: str) -> dict:
        """Get file/video information for a URL."""
        downloader = self.get_downloader(url)
        try:
            return downloader.get_info(url)
        except Exception as e:
            return {"error": str(e), "url": url}

    def create_item(self, url: str, save_path: str = "",
                    media_format: str = "", media_quality: str = "") -> DownloadItem:
        """Create a DownloadItem with auto-detected information."""
        info = self.get_info(url)
        downloader = self.get_downloader(url)

        item = DownloadItem()
        item.url = url
        item.save_path = save_path
        item.site_name = downloader.name
        item.media_format = media_format
        item.media_quality = media_quality

        # Apply detected info
        if info:
            if info.get("filename"):
                item.filename = info["filename"]
            if info.get("file_size"):
                item.file_size = info["file_size"]
            if info.get("title"):
                item.filename = info["title"]

        # Detect category
        is_media_site = downloader.name in ["YouTube/Media"]
        if is_media_site:
            if media_format in ("mp3", "aac", "flac", "opus", "wav"):
                item.category = DownloadCategory.AUDIO
                item.is_media = True
            else:
                item.category = DownloadCategory.VIDEO
                item.is_media = True
        elif item.filename != "unknown":
            item.category = DownloadCategory.from_extension(item.filename)

        return item

    def start_download(self, item: DownloadItem) -> bool:
        """Start downloading using the appropriate downloader."""
        if item.id in self._threads:
            return False

        downloader = self.get_downloader(item.url)

        stop_event = threading.Event()
        self._stop_events[item.id] = stop_event

        thread = threading.Thread(
            target=self._run_download,
            args=(downloader, item, stop_event),
            daemon=True
        )
        self._threads[item.id] = thread
        thread.start()
        return True

    def _run_download(self, downloader: BaseDownloader, item: DownloadItem,
                      stop_event: threading.Event):
        """Run download with error handling."""
        try:
            item.status = DownloadStatus.DOWNLOADING
            item.started_at = __import__("time").time()
            downloader.download(item, stop_event)

            if not stop_event.is_set():
                item.status = DownloadStatus.COMPLETED
                item.progress = 100.0
                item.completed_at = __import__("time").time()
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
        finally:
            self._threads.pop(item.id, None)
            self._stop_events.pop(item.id, None)

    def pause_download(self, item_id: str):
        """Pause a running download."""
        if item_id in self._stop_events:
            self._stop_events[item_id].set()

    def resume_download(self, item: DownloadItem) -> bool:
        """Resume a paused/errored download."""
        if item.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
            item.status = DownloadStatus.PENDING
            item.error_message = ""
            return self.start_download(item)
        return False

    def cancel_download(self, item_id: str):
        """Cancel a download."""
        self.pause_download(item_id)

    def is_downloading(self, item_id: str) -> bool:
        """Check if an item is being downloaded."""
        return item_id in self._threads

    @property
    def supported_sites(self) -> List[str]:
        """Get list of supported site names."""
        return [d.name for d in self._downloaders] + [self._fallback.name]
