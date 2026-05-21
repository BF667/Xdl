"""
Pixeldrain downloader - enhanced version of the original Xdl module.
"""

import os
import time
import threading

import requests

from .base import BaseDownloader
from ..core.models import DownloadItem, DownloadStatus


class PixeldrainDownloader(BaseDownloader):
    """Pixeldrain file downloader with progress tracking."""

    name = "Pixeldrain"
    supported_domains = ["pixeldrain.com"]

    def can_handle(self, url: str) -> bool:
        return "pixeldrain.com" in url

    def get_info(self, url: str) -> dict:
        try:
            file_id = self._extract_file_id(url)
            api_url = f"https://pixeldrain.com/api/file/{file_id}/info"
            resp = requests.get(api_url, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "filename": data.get("name", "unknown"),
                    "file_size": data.get("file_size", 0),
                    "mime_type": data.get("mime_type", ""),
                }
        except Exception:
            pass

        return {}

    def download(self, item: DownloadItem, stop_event: threading.Event):
        file_id = self._extract_file_id(item.url)
        api_url = f"https://pixeldrain.com/api/file/{file_id}"

        with requests.get(api_url, stream=True, timeout=120) as response:
            response.raise_for_status()

            # Get filename from Content-Disposition
            cd = response.headers.get("Content-Disposition", "")
            if cd:
                import re
                match = re.search(r'filename="?([^";\n]+)"?', cd)
                if match:
                    item.filename = match.group(1)

            if not item.file_size:
                item.file_size = int(response.headers.get("Content-Length", 0))

            output_file = os.path.join(item.save_path, item.filename)

            with open(output_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if stop_event.is_set():
                        raise Exception("Download cancelled")

                    if chunk:
                        f.write(chunk)
                        item.downloaded += len(chunk)

                        if item.file_size > 0:
                            item.progress = (item.downloaded / item.file_size) * 100

                        if self.on_progress:
                            self.on_progress(item)

    def _extract_file_id(self, url: str) -> str:
        """Extract file ID from Pixeldrain URL."""
        if "/u/" in url:
            return url.split("/u/")[-1].split("?")[0]
        elif "/l/" in url:
            return url.split("/l/")[-1].split("?")[0]
        return url.split("/")[-1].split("?")[0]
