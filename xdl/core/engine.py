"""
Core download engine with multi-threaded segmented downloading,
resume support, and protocol detection.
"""

import os
import re
import time
import threading
import tempfile
import hashlib
from typing import Optional, Callable, Dict, List
from urllib.parse import urlparse

import requests

from .models import DownloadItem, DownloadStatus, DownloadCategory


class SegmentDownloader:
    """Downloads a specific byte range segment of a file."""

    def __init__(self, url: str, start_byte: int, end_byte: int,
                 segment_id: int, temp_dir: str, headers: dict = None):
        self.url = url
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.segment_id = segment_id
        self.temp_dir = temp_dir
        self.headers = headers or {}

        self.downloaded = 0
        self.speed = 0.0
        self.finished = False
        self.error = None
        self._stop_event = threading.Event()
        self._last_speed_check = time.time()
        self._last_downloaded = 0

    @property
    def temp_file(self) -> str:
        return os.path.join(self.temp_dir, f"seg_{self.segment_id}.tmp")

    def stop(self):
        self._stop_event.set()

    def download(self, session: requests.Session, on_progress: Callable = None):
        """Download this segment."""
        headers = dict(self.headers)
        current_pos = self.start_byte + self.downloaded
        if self.downloaded > 0:
            headers["Range"] = f"bytes={current_pos}-{self.end_byte}"
        elif self.end_byte > 0:
            headers["Range"] = f"bytes={self.start_byte}-{self.end_byte}"

        try:
            response = session.get(self.url, headers=headers, stream=True,
                                   timeout=60, verify=True)
            response.raise_for_status()

            mode = "ab" if self.downloaded > 0 else "wb"
            with open(self.temp_file, mode) as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if self._stop_event.is_set():
                        self.error = "Cancelled"
                        return

                    if chunk:
                        f.write(chunk)
                        self.downloaded += len(chunk)

                        # Calculate speed
                        now = time.time()
                        elapsed = now - self._last_speed_check
                        if elapsed >= 0.5:
                            self.speed = (self.downloaded - self._last_downloaded) / elapsed
                            self._last_speed_check = now
                            self._last_downloaded = self.downloaded

                        if on_progress:
                            on_progress(self.segment_id, self.downloaded, self.speed)

            self.finished = True
            self.speed = 0.0

        except Exception as e:
            self.error = str(e)
            self.speed = 0.0


class DownloadEngine:
    """
    Multi-threaded download engine that supports:
    - Segmented downloading with configurable segments
    - Resume/pause for interrupted downloads
    - Speed calculation and ETA
    - Protocol detection (HTTP/HTTPS, FTP, etc.)
    - Site-specific downloader routing
    """

    def __init__(self, max_concurrent: int = 3, default_segments: int = 8,
                 default_save_path: str = None, proxy: str = None,
                 user_agent: str = None):
        self.max_concurrent = max_concurrent
        self.default_segments = default_segments
        self.default_save_path = default_save_path or os.path.join(
            os.path.expanduser("~"), "Downloads", "Xdl"
        )
        self.proxy = proxy
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        self._active_downloads: Dict[str, threading.Thread] = {}
        self._segments: Dict[str, List[SegmentDownloader]] = {}
        self._sessions: Dict[str, requests.Session] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

        # Callbacks
        self.on_progress: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        os.makedirs(self.default_save_path, exist_ok=True)

    def _create_session(self) -> requests.Session:
        """Create a configured requests session."""
        session = requests.Session()
        session.headers.update({"User-Agent": self.user_agent})
        if self.proxy:
            session.proxies.update({
                "http": self.proxy,
                "https": self.proxy,
            })
        return session

    def _detect_site(self, url: str) -> str:
        """Detect the hosting site from URL."""
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        site_map = {
            "youtube.com": "YouTube",
            "youtu.be": "YouTube",
            "m.youtube.com": "YouTube",
            "google drive": "Google Drive",
            "drive.google.com": "Google Drive",
            "docs.google.com": "Google Drive",
            "mediafire.com": "MediaFire",
            "pixeldrain.com": "Pixeldrain",
            "huggingface.co": "HuggingFace",
            "vimeo.com": "Vimeo",
            "dailymotion.com": "Dailymotion",
            "twitch.tv": "Twitch",
            "twitter.com": "Twitter/X",
            "x.com": "Twitter/X",
            "facebook.com": "Facebook",
            "instagram.com": "Instagram",
            "tiktok.com": "TikTok",
            "reddit.com": "Reddit",
            "soundcloud.com": "SoundCloud",
            "bandcamp.com": "Bandcamp",
            "bilibili.com": "Bilibili",
            "dropbox.com": "Dropbox",
            "mega.nz": "Mega",
            "1fichier.com": "1Fichier",
        }

        for domain, site in site_map.items():
            if domain in hostname:
                return site
        return "Generic"

    def _get_filename_from_url(self, url: str, response: requests.Response = None) -> str:
        """Extract filename from URL or Content-Disposition header."""
        # Try Content-Disposition first
        if response and "Content-Disposition" in response.headers:
            cd = response.headers["Content-Disposition"]
            match = re.search(r'filename[^;=\n]*=((["\']).*?\2|[^;\n]*)', cd)
            if match:
                filename = match.group(1).strip('"\'')
                if filename:
                    return filename

        # Try URL path
        parsed = urlparse(url)
        path = parsed.path
        if path:
            filename = os.path.basename(path)
            if filename and "." in filename:
                return filename

        # Fallback
        return f"download_{int(time.time())}"

    def _get_file_info(self, url: str, session: requests.Session) -> dict:
        """Get file information without downloading (HEAD request)."""
        info = {
            "file_size": 0,
            "filename": "unknown",
            "resume_supported": False,
            "content_type": "",
        }

        try:
            # Try HEAD first
            resp = session.head(url, allow_redirects=True, timeout=30)
            info["file_size"] = int(resp.headers.get("Content-Length", 0))
            info["resume_supported"] = "bytes" in resp.headers.get("Accept-Ranges", "")
            info["content_type"] = resp.headers.get("Content-Type", "")

            filename = self._get_filename_from_url(url, resp)
            if filename:
                info["filename"] = filename

            # If HEAD didn't give us size, try GET with Range
            if info["file_size"] == 0:
                resp = session.get(url, allow_redirects=True, stream=True, timeout=30)
                info["file_size"] = int(resp.headers.get("Content-Length", 0))
                info["resume_supported"] = "bytes" in resp.headers.get("Accept-Ranges", "")

                filename = self._get_filename_from_url(url, resp)
                if filename:
                    info["filename"] = filename

                resp.close()

        except Exception:
            pass

        return info

    def start_download(self, item: DownloadItem) -> bool:
        """Start downloading a DownloadItem using segmented downloading."""
        if item.id in self._active_downloads:
            return False

        stop_event = threading.Event()
        self._stop_events[item.id] = stop_event

        thread = threading.Thread(
            target=self._download_worker,
            args=(item, stop_event),
            daemon=True
        )
        self._active_downloads[item.id] = thread
        thread.start()
        return True

    def _download_worker(self, item: DownloadItem, stop_event: threading.Event):
        """Worker thread for segmented downloading."""
        session = self._create_session()
        self._sessions[item.id] = session
        temp_dir = tempfile.mkdtemp(prefix=f"xdl_{item.id}_")

        try:
            item.status = DownloadStatus.DOWNLOADING
            item.started_at = time.time()

            # Get file info
            file_info = self._get_file_info(item.url, session)
            if not item.filename or item.filename == "unknown":
                item.filename = file_info["filename"]
            if not item.file_size:
                item.file_size = file_info["file_size"]
            item.resume_supported = file_info["resume_supported"]
            item.site_name = self._detect_site(item.url)

            # Determine category
            item.category = DownloadCategory.from_extension(item.filename)

            # Ensure save path
            if not item.save_path:
                item.save_path = self.default_save_path
            os.makedirs(item.save_path, exist_ok=True)

            output_file = os.path.join(item.save_path, item.filename)

            # Check if resume is possible
            resume_from = 0
            if os.path.exists(output_file):
                existing_size = os.path.getsize(output_file)
                if item.resume_supported and existing_size < item.file_size and existing_size > 0:
                    resume_from = existing_size
                    item.downloaded = resume_from

            # Determine number of segments
            num_segments = item.num_segments if item.resume_supported and item.file_size > 1024 * 1024 else 1
            if not item.resume_supported:
                num_segments = 1

            file_size = item.file_size - resume_from

            if num_segments > 1 and file_size > 0:
                # Segmented download
                segment_size = file_size // num_segments
                segments = []

                for i in range(num_segments):
                    start = resume_from + (i * segment_size)
                    end = resume_from + ((i + 1) * segment_size - 1) if i < num_segments - 1 else item.file_size - 1

                    seg = SegmentDownloader(
                        url=item.url,
                        start_byte=start,
                        end_byte=end,
                        segment_id=i,
                        temp_dir=temp_dir,
                        headers={"User-Agent": self.user_agent}
                    )
                    segments.append(seg)

                self._segments[item.id] = segments

                # Start all segments
                seg_threads = []
                for seg in segments:
                    t = threading.Thread(
                        target=seg.download,
                        args=(session, None),
                        daemon=True
                    )
                    seg_threads.append(t)
                    t.start()

                # Monitor progress
                while not stop_event.is_set():
                    total_downloaded = resume_from + sum(s.downloaded for s in segments)
                    total_speed = sum(s.speed for s in segments)
                    item.update_progress(total_downloaded, total_speed)

                    if self.on_progress:
                        self.on_progress(item)

                    # Check if all segments finished
                    all_done = all(s.finished for s in segments)
                    any_error = any(s.error for s in segments)

                    if any_error:
                        # Stop remaining segments
                        for s in segments:
                            s.stop()
                        raise Exception(f"Segment error: {next(s.error for s in segments if s.error)}")

                    if all_done:
                        break

                    time.sleep(0.3)

                # Wait for all threads
                for t in seg_threads:
                    t.join(timeout=10)

                if stop_event.is_set():
                    item.status = DownloadStatus.PAUSED
                    return

                # Merge segments
                with open(output_file, "wb") as out_f:
                    if resume_from > 0:
                        # Copy existing part
                        pass  # We'll overwrite with all segments from resume point
                    for seg in sorted(segments, key=lambda s: s.segment_id):
                        if os.path.exists(seg.temp_file):
                            with open(seg.temp_file, "rb") as seg_f:
                                out_f.write(seg_f.read())

                # Cleanup temp files
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

            else:
                # Single-segment download (small files or non-resumable)
                headers = {"User-Agent": self.user_agent}
                if resume_from > 0:
                    headers["Range"] = f"bytes={resume_from}-"

                response = session.get(item.url, headers=headers, stream=True,
                                       timeout=120, verify=True)
                response.raise_for_status()

                mode = "ab" if resume_from > 0 else "wb"
                with open(output_file, mode) as f:
                    last_time = time.time()
                    last_bytes = resume_from

                    for chunk in response.iter_content(chunk_size=65536):
                        if stop_event.is_set():
                            item.status = DownloadStatus.PAUSED
                            return

                        if chunk:
                            f.write(chunk)
                            item.downloaded += len(chunk)

                            # Speed calculation
                            now = time.time()
                            elapsed = now - last_time
                            if elapsed >= 0.5:
                                item.speed = (item.downloaded - last_bytes) / elapsed
                                last_time = now
                                last_bytes = item.downloaded

                            item.update_progress(item.downloaded, item.speed)

                            if self.on_progress:
                                self.on_progress(item)

            # Download complete
            item.progress = 100.0
            item.status = DownloadStatus.COMPLETED
            item.completed_at = time.time()
            item.speed = 0.0
            item.eta = 0.0

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
            session.close()
            with self._lock:
                self._active_downloads.pop(item.id, None)
                self._sessions.pop(item.id, None)
                self._segments.pop(item.id, None)
                self._stop_events.pop(item.id, None)

    def pause_download(self, item_id: str):
        """Pause a running download."""
        if item_id in self._stop_events:
            self._stop_events[item_id].set()

        if item_id in self._segments:
            for seg in self._segments[item_id]:
                seg.stop()

    def resume_download(self, item: DownloadItem) -> bool:
        """Resume a paused download."""
        if item.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
            item.status = DownloadStatus.PENDING
            return self.start_download(item)
        return False

    def cancel_download(self, item_id: str):
        """Cancel a download completely."""
        self.pause_download(item_id)

        # Cleanup temp files
        import shutil
        temp_dir = tempfile.gettempdir()
        for d in os.listdir(temp_dir):
            if d.startswith(f"xdl_{item_id}_"):
                shutil.rmtree(os.path.join(temp_dir, d), ignore_errors=True)

    def get_active_count(self) -> int:
        """Get number of active downloads."""
        return len(self._active_downloads)

    def is_downloading(self, item_id: str) -> bool:
        """Check if a specific item is currently downloading."""
        return item_id in self._active_downloads
