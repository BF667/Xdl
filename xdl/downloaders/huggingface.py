"""
HuggingFace model/dataset downloader - enhanced version of the original Xdl module.
"""

import os
import time
import threading

import requests
import tqdm

from .base import BaseDownloader
from ..core.models import DownloadItem, DownloadStatus


class HuggingFaceDownloader(BaseDownloader):
    """HuggingFace file downloader with progress tracking."""

    name = "HuggingFace"
    supported_domains = ["huggingface.co"]

    def can_handle(self, url: str) -> bool:
        return "huggingface.co" in url

    def get_info(self, url: str) -> dict:
        resolved_url = self._resolve_url(url)
        filename = os.path.basename(resolved_url)
        return {
            "filename": filename,
            "resolved_url": resolved_url,
        }

    def download(self, item: DownloadItem, stop_event: threading.Event):
        url = self._resolve_url(item.url)
        output_path = os.path.join(
            item.save_path,
            os.path.basename(url)
        )

        item.filename = os.path.basename(url)

        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        total = int(response.headers.get("content-length", 0))
        item.file_size = total

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=10 * 1024 * 1024):
                if stop_event.is_set():
                    raise Exception("Download cancelled")

                if chunk:
                    f.write(chunk)
                    item.downloaded += len(chunk)

                    if total > 0:
                        item.progress = (item.downloaded / total) * 100

                    if self.on_progress:
                        self.on_progress(item)

    def _resolve_url(self, url: str) -> str:
        """Resolve HuggingFace URL to direct download link."""
        return (
            url.replace("/blob/", "/resolve/")
            .replace("/tree/", "/resolve/")
            .replace("?download=true", "")
            .strip()
        )
