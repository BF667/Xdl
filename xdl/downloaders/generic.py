"""
Generic HTTP/HTTPS downloader for any URL that doesn't match
a specific site handler. Supports multi-segment downloading
and resume.
"""

import os
import time
import threading

import requests

from .base import BaseDownloader
from ..core.models import DownloadItem, DownloadStatus
from ..core.engine import DownloadEngine


class GenericDownloader(BaseDownloader):
    """
    Generic file downloader for HTTP/HTTPS URLs.
    Falls back to segmented downloading engine.
    """

    name = "Generic HTTP"
    supported_domains = []  # Matches everything as fallback

    def __init__(self):
        super().__init__()
        self._engine = DownloadEngine()

    def can_handle(self, url: str) -> bool:
        """Generic downloader can handle any HTTP/HTTPS URL."""
        return url.startswith(("http://", "https://", "ftp://"))

    def get_info(self, url: str) -> dict:
        """Get file info using HEAD request."""
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            })

            resp = session.head(url, allow_redirects=True, timeout=30)

            filename = "unknown"
            if "Content-Disposition" in resp.headers:
                import re
                cd = resp.headers["Content-Disposition"]
                match = re.search(r'filename[^;=\n]*=((["\']).*?\2|[^;\n]*)', cd)
                if match:
                    filename = match.group(1).strip('"\'')
            else:
                from urllib.parse import urlparse, unquote
                parsed = urlparse(url)
                path = unquote(parsed.path)
                if path:
                    filename = os.path.basename(path)
                if not filename or "." not in filename:
                    filename = f"download_{int(time.time())}"

            return {
                "filename": filename,
                "file_size": int(resp.headers.get("Content-Length", 0)),
                "content_type": resp.headers.get("Content-Type", ""),
                "resume_supported": "bytes" in resp.headers.get("Accept-Ranges", ""),
            }
        except Exception as e:
            return {"filename": "unknown", "error": str(e)}

    def download(self, item: DownloadItem, stop_event: threading.Event):
        """Download using the segmented download engine."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })

        # Get file info if not already set
        if not item.file_size or item.filename == "unknown":
            info = self.get_info(item.url)
            if item.filename == "unknown" and info.get("filename"):
                item.filename = info["filename"]
            if not item.file_size and info.get("file_size"):
                item.file_size = info["file_size"]

        output_file = os.path.join(item.save_path, item.filename)

        # Check for partial download (resume)
        resume_from = 0
        if os.path.exists(output_file):
            existing_size = os.path.getsize(output_file)
            info = self.get_info(item.url)
            if info.get("resume_supported") and existing_size < item.file_size:
                resume_from = existing_size
                item.downloaded = resume_from

        headers = {}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"

        response = session.get(item.url, headers=headers, stream=True,
                               timeout=120, verify=True)
        response.raise_for_status()

        mode = "ab" if resume_from > 0 else "wb"
        last_time = time.time()
        last_bytes = resume_from

        with open(output_file, mode) as f:
            for chunk in response.iter_content(chunk_size=65536):
                if stop_event.is_set():
                    raise Exception("Download cancelled")

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

                    if item.file_size > 0:
                        item.progress = (item.downloaded / item.file_size) * 100

                    if self.on_progress:
                        self.on_progress(item)

        session.close()
