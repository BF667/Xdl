"""
YouTube and video site downloader using yt-dlp.
Supports 1000+ sites including YouTube, Vimeo, Dailymotion,
Twitter, Facebook, TikTok, Twitch, and many more.
"""

import os
import re
import time
import threading
from typing import Optional

from .base import BaseDownloader
from ..core.models import DownloadItem, DownloadStatus, DownloadCategory


class YouTubeDownloader(BaseDownloader):
    """
    Universal video/audio downloader powered by yt-dlp.
    Supports YouTube, Vimeo, Dailymotion, Twitter, Facebook,
    TikTok, Twitch, SoundCloud, Bilibili, and 1000+ more sites.
    """

    name = "YouTube/Media"
    supported_domains = [
        "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
        "twitch.tv", "twitter.com", "x.com", "facebook.com",
        "instagram.com", "tiktok.com", "reddit.com", "soundcloud.com",
        "bandcamp.com", "bilibili.com", "streamable.com", "mixcloud.com",
    ]

    # Video formats mapping
    VIDEO_FORMATS = {
        "best": "Best Quality (Video + Audio)",
        "bestvideo+bestaudio": "Best Video + Best Audio (separate)",
        "720p": "720p HD",
        "480p": "480p SD",
        "360p": "360p",
        "240p": "240p",
    }

    # Audio formats mapping
    AUDIO_FORMATS = {
        "bestaudio": "Best Audio Quality",
        "mp3": "MP3",
        "aac": "AAC",
        "flac": "FLAC",
        "opus": "Opus",
        "wav": "WAV",
    }

    def __init__(self):
        super().__init__()
        self._ytdl_instances = {}

    # Extended list of video/media sites that yt-dlp supports
    _known_media_domains = [
        "youtube.com", "youtu.be", "m.youtube.com",
        "vimeo.com", "dailymotion.com", "twitch.tv",
        "twitter.com", "x.com", "facebook.com", "instagram.com",
        "tiktok.com", "reddit.com", "soundcloud.com", "bandcamp.com",
        "bilibili.com", "streamable.com", "mixcloud.com",
        "ok.ru", "rutube.ru", "veoh.com", "metacafe.com",
        "break.com", "funnyordie.com", "coub.com",
        "tumblr.com", "pinterest.com", "snapchat.com",
        "periscope.tv", "pscp.tv", "livestream.com",
        "dailymotion.com", "nicovideo.jp", "nico.nico",
        "openrec.tv", "yapic.ru", "peertube",
        "rumble.com", "odysee.com", "bitchute.com",
        "brighteon.com", "spankbang.com", "pornhub.com",
        "xvideos.com", "xhamster.com",
        "epidemicsound.com", "audiomack.com",
        "newgrounds.com", "itch.io",
        "panopto.com", "echo360.org",
        "ted.com", "udemy.com", "skillshare.com",
        "coursera.org", "pluralsight.com",
        "crunchyroll.com", "funimation.com",
        "nhk.or.jp", "tver.jp",
        "zattoo.com", "teleboy.ch", "tvplus.com",
        "art19.com", "podbean.com", "simplecast.com",
    ]

    def can_handle(self, url: str) -> bool:
        """Check if yt-dlp can handle this URL.
        Only returns True for known media sites.
        Other URLs fall through to the generic downloader.
        """
        # Check against known video/audio domains
        for domain in self._known_media_domains:
            if domain in url:
                return True
        return False

    def get_info(self, url: str) -> dict:
        """Get video/audio information."""
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                return {}

            # Handle playlists
            if "entries" in info:
                entries = list(info["entries"]) if info["entries"] else []
                return {
                    "title": info.get("title", "Playlist"),
                    "is_playlist": True,
                    "entries": entries,
                    "count": len(entries),
                    "thumbnail": info.get("thumbnail", ""),
                }

            formats = info.get("formats", [])
            best_format = info.get("format", "")
            duration = info.get("duration", 0)

            return {
                "title": info.get("title", "Unknown"),
                "is_playlist": False,
                "duration": duration,
                "thumbnail": info.get("thumbnail", ""),
                "description": info.get("description", ""),
                "uploader": info.get("uploader", ""),
                "view_count": info.get("view_count", 0),
                "like_count": info.get("like_count", 0),
                "formats": len(formats),
                "best_format": best_format,
                "file_size": info.get("filesize") or info.get("filesize_approx", 0),
            }

    def download(self, item: DownloadItem, stop_event: threading.Event):
        """Download video/audio using yt-dlp."""
        import yt_dlp

        is_audio = item.media_format in ("mp3", "aac", "flac", "opus", "wav") or item.category == DownloadCategory.AUDIO

        # Determine format
        if is_audio:
            format_spec = self._get_audio_format(item.media_format or "bestaudio")
            postprocessors = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": item.media_format or "mp3",
            }]
            outtmpl = os.path.join(item.save_path, "%(title)s.%(ext)s")
        else:
            format_spec = self._get_video_format(item.media_quality or "best")
            postprocessors = []
            outtmpl = os.path.join(item.save_path, "%(title)s.%(ext)s")

        class ProgressHook:
            def __init__(self, dl_item):
                self.item = dl_item
                self._last_time = time.time()
                self._last_bytes = 0

            def __call__(self, d):
                if stop_event.is_set():
                    raise Exception("Download cancelled by user")

                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                    downloaded = d.get("downloaded_bytes", 0)
                    speed = d.get("speed", 0) or 0

                    self.item.file_size = total
                    self.item.update_progress(downloaded, speed)

                    if self.on_progress:
                        self.on_progress(self.item)

                elif d["status"] == "finished":
                    self.item.progress = 100.0
                    self.item.status = DownloadStatus.COMPLETED

        hook = ProgressHook(item)
        hook.on_progress = self.on_progress

        ydl_opts = {
            "format": format_spec,
            "outtmpl": outtmpl,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "no_warnings": True,
            "progress_hooks": [hook],
            "postprocessors": postprocessors,
            "merge_output_format": "mp4" if not is_audio else None,
            "noplaylist": not self._is_playlist_url(item.url),
            "socket_timeout": 60,
            "retries": 5,
            "fragment_retries": 5,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(item.url, download=True)
            if result:
                # Get the actual filename
                if "entries" in result:
                    entries = list(result["entries"]) if result["entries"] else []
                    if entries:
                        item.filename = ydl.prepare_filename(entries[0])
                else:
                    item.filename = os.path.basename(ydl.prepare_filename(result))

    def _get_video_format(self, quality: str) -> str:
        """Get yt-dlp format string for video quality."""
        format_map = {
            "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "bestvideo+bestaudio": "bestvideo+bestaudio",
            "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
            "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
            "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]",
            "240p": "bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/best[height<=240]",
        }
        return format_map.get(quality, format_map["best"])

    def _get_audio_format(self, format_name: str) -> str:
        """Get yt-dlp format string for audio quality."""
        if format_name == "bestaudio":
            return "bestaudio/best"
        return f"bestaudio[ext={format_name}]/bestaudio/best"

    def _is_playlist_url(self, url: str) -> bool:
        """Check if URL is a playlist."""
        playlist_patterns = [
            r"[?&]list=",
            r"/playlist",
            r"/channel/",
            r"/c/",
            r"/user/",
        ]
        return any(re.search(p, url) for p in playlist_patterns)
