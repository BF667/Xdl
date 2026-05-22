"""
MediaFire downloader - enhanced version of the original Xdl module.
"""

import os
import time
import threading

import requests
from bs4 import BeautifulSoup

from .base import BaseDownloader
from ..core.models import DownloadItem, DownloadStatus


class MediaFireDownloader(BaseDownloader):
    """MediaFire file downloader with progress tracking."""

    name = "MediaFire"
    supported_domains = ["mediafire.com"]

    def can_handle(self, url: str) -> bool:
        return "mediafire.com" in url

    def get_info(self, url: str) -> dict:
        try:
            sess = requests.Session()
            sess.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp = sess.get(url, timeout=30)

            soup = BeautifulSoup(resp.content, "html.parser")

            # Try to get filename from the page
            filename_tag = soup.find("div", class_="filename")
            filename = filename_tag.text.strip() if filename_tag else url.split("/")[-2]

            # Try to get file size
            size_tag = soup.find("span", class_="fileSize")
            file_size_text = size_tag.text.strip() if size_tag else ""

            return {
                "filename": filename,
                "file_size_text": file_size_text,
                "url": url,
            }
        except Exception:
            return {"url": url}

    def download(self, item: DownloadItem, stop_event: threading.Event):
        sess = requests.Session()
        sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        # Get the actual download link
        resp = sess.get(item.url, timeout=30)
        soup = BeautifulSoup(resp.content, "html.parser")
        download_btn = soup.find(id="downloadButton")

        if not download_btn:
            raise Exception("Could not find download button on MediaFire page")

        download_url = download_btn.get("href")
        if not download_url:
            raise Exception("Could not extract download URL from MediaFire")

        # Determine filename
        if not item.filename or item.filename == "unknown":
            filename_tag = soup.find("div", class_="filename")
            item.filename = filename_tag.text.strip() if filename_tag else item.url.split("/")[-2]

        output_file = os.path.join(item.save_path, item.filename)

        # Download with progress
        with sess.get(download_url, stream=True, timeout=120) as r:
            r.raise_for_status()

            total_length = int(r.headers.get("content-length", 0))
            item.file_size = total_length

            with open(output_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if stop_event.is_set():
                        raise Exception("Download cancelled")

                    if chunk:
                        f.write(chunk)
                        item.downloaded += len(chunk)

                        if total_length > 0:
                            item.progress = (item.downloaded / total_length) * 100

                        if self.on_progress:
                            self.on_progress(item)

        sess.close()
