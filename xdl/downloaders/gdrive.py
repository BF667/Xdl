"""
Google Drive downloader - enhanced version of the original Xdl gdown module.
"""

import os
import re
import json
import codecs
import tempfile
import time
import threading

import requests
import tqdm
from urllib.parse import urlparse, parse_qs, unquote

from .base import BaseDownloader
from ..core.models import DownloadItem, DownloadStatus


class GDriveDownloader(BaseDownloader):
    """Google Drive file downloader with resume support."""

    name = "Google Drive"
    supported_domains = ["drive.google.com", "docs.google.com"]

    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.hostname in self.supported_domains if parsed.hostname else False

    def get_info(self, url: str) -> dict:
        file_id = self._extract_file_id(url)
        if not file_id:
            return {}

        try:
            sess = self._create_session()
            api_url = f"https://drive.google.com/file/d/{file_id}/view"
            resp = sess.get(api_url, timeout=30)

            # Try to extract filename from page
            match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', resp.text)
            filename = match.group(1) if match else f"gdrive_{file_id}"

            return {
                "file_id": file_id,
                "filename": filename,
                "file_size": 0,
            }
        except Exception:
            return {"file_id": file_id, "filename": f"gdrive_{file_id}"}

    def download(self, item: DownloadItem, stop_event: threading.Event):
        file_id = self._extract_file_id(item.url)
        if not file_id:
            raise ValueError("Could not extract Google Drive file ID")

        sess = self._create_session()
        url = f"https://drive.google.com/uc?id={file_id}"
        url_origin = url

        is_gdrive_download_link = True

        while True:
            if stop_event.is_set():
                raise Exception("Download cancelled")

            res = sess.get(url, stream=True, verify=True)
            if url == url_origin and res.status_code == 500:
                url = f"https://drive.google.com/open?id={file_id}"
                continue

            if "Content-Disposition" in res.headers:
                break
            if not is_gdrive_download_link:
                break

            try:
                url = self._get_url_from_confirmation(res.text)
            except Exception as e:
                raise Exception(str(e))

        # Extract filename
        content_disposition = unquote(res.headers.get("Content-Disposition", ""))
        match = re.search(r"filename\*=UTF-8''(.*)", content_disposition) or \
                re.search(r'filename=["\']?(.*?)["\']?$', content_disposition)
        filename = match.group(1).replace(os.path.sep, "_") if match else f"gdrive_{file_id}"

        item.filename = filename
        output_file = os.path.join(item.save_path, filename)
        item.file_size = int(res.headers.get("Content-Length", 0))

        # Download with progress
        tmp_file = tempfile.mktemp(
            suffix=".tmp",
            prefix=os.path.basename(output_file),
            dir=item.save_path
        )

        try:
            with tqdm.tqdm(
                desc=os.path.basename(output_file),
                total=item.file_size or None,
                ncols=100,
                unit="B",
                unit_scale=True,
                leave=False
            ) as pbar:
                with open(tmp_file, "wb") as f:
                    for chunk in res.iter_content(chunk_size=512 * 1024):
                        if stop_event.is_set():
                            raise Exception("Download cancelled")

                        if chunk:
                            f.write(chunk)
                            item.downloaded += len(chunk)
                            pbar.update(len(chunk))

                            if item.file_size > 0:
                                item.progress = (item.downloaded / item.file_size) * 100

                            if self.on_progress:
                                self.on_progress(item)

            # Rename temp file to final
            if os.path.exists(output_file):
                os.remove(output_file)
            os.rename(tmp_file, output_file)

        except Exception:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            raise
        finally:
            sess.close()

    def _extract_file_id(self, url: str) -> str:
        """Extract file ID from various Google Drive URL formats."""
        patterns = [
            r"/file/d/([a-zA-Z0-9_-]+)",
            r"/file/u/\d+/d/([a-zA-Z0-9_-]+)",
            r"open\?id=([a-zA-Z0-9_-]+)",
            r"uc\?id=([a-zA-Z0-9_-]+)",
            r"/document/d/([a-zA-Z0-9_-]+)",
            r"/presentation/d/([a-zA-Z0-9_-]+)",
            r"/spreadsheets/d/([a-zA-Z0-9_-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        parsed = urlparse(url)
        file_id = parse_qs(parsed.query).get("id", [None])[0]
        return file_id

    def _get_url_from_confirmation(self, contents: str) -> str:
        """Get download URL from Google Drive confirmation page."""
        patterns = [
            r'href="(/uc\?export=download[^"]+)"',
            r'href="/open\?id=([^"]+)"',
            r'"downloadUrl":"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, contents)
            if match:
                url = match.group(1)
                if 'id=' in pattern:
                    uuid_match = re.search(
                        r'<input\s+type="hidden"\s+name="uuid"\s+value="([^"]+)"',
                        contents
                    )
                    uuid_val = uuid_match.group(1) if uuid_match else ""
                    url = f"https://drive.google.com/uc?export=download&id={match.group(1)}&confirm=t&uuid={uuid_val}"
                elif 'downloadUrl' in pattern:
                    url = url.replace("\\u003d", "=").replace("\\u0026", "&")
                else:
                    url = "https://docs.google.com" + url.replace("&amp;", "&")
                return url

        match = re.search(r'<p class="uc-error-subcaption">(.*)</p>', contents)
        if match:
            raise Exception(match.group(1))
        raise Exception("Could not retrieve the public link for the file.")

    def _create_session(self) -> requests.Session:
        sess = requests.Session()
        sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        return sess
