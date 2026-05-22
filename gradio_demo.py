#!/usr/bin/env python3
"""
Xdl Download Manager - Gradio Web Demo
A complete web interface for the download manager powered by Gradio 6+.

Usage:
    python3 gradio_demo.py              # Launch on http://localhost:7860
    python3 gradio_demo.py --share      # Launch with public share link
    python3 gradio_demo.py --port 8080  # Launch on custom port
"""

import os
import sys
import time
import json
import threading
import argparse
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gradio as gr

from xdl.downloaders.router import DownloadRouter
from xdl.core.models import DownloadItem, DownloadStatus, DownloadCategory
from xdl.utils.helpers import format_size, format_speed, format_time, is_url


# ──────────────────────────────────────────────
#  Download Manager State
# ──────────────────────────────────────────────

class DownloadManagerState:
    """Thread-safe state manager for the Gradio demo."""

    def __init__(self):
        self.router = DownloadRouter()
        self._downloads: dict = {}
        self._threads: dict = {}
        self._stop_events: dict = {}
        self._lock = threading.Lock()
        self.default_save_path = os.path.join(
            os.path.expanduser("~"), "Downloads", "Xdl"
        )
        os.makedirs(self.default_save_path, exist_ok=True)

    def add_download(self, url: str, save_path: str = "",
                     download_type: str = "Video",
                     quality: str = "Best Quality",
                     audio_format: str = "MP3",
                     segments: int = 8) -> dict:
        """Add a new download and start it."""
        if not is_url(url):
            return {"status": "error", "message": "Invalid URL provided"}

        save_path = save_path or self.default_save_path
        os.makedirs(save_path, exist_ok=True)

        media_format = ""
        media_quality = ""

        if download_type == "Audio":
            media_format = audio_format.lower() if audio_format != "Best Quality" else "bestaudio"
        else:
            quality_map = {
                "Best Quality": "best",
                "720p": "720p",
                "480p": "480p",
                "360p": "360p",
                "240p": "240p",
            }
            media_quality = quality_map.get(quality, "best")

        item = self.router.create_item(url=url, save_path=save_path)

        if download_type == "Audio":
            item.category = DownloadCategory.AUDIO
            item.is_media = True
            item.media_format = media_format
        else:
            if item.category != DownloadCategory.AUDIO:
                item.category = DownloadCategory.VIDEO
            item.is_media = True
            item.media_quality = media_quality

        item.num_segments = segments

        try:
            info = self.router.get_info(url)
            if info.get("filename") and item.filename == "unknown":
                item.filename = info["filename"]
            if info.get("file_size") and not item.file_size:
                item.file_size = info["file_size"]
            if info.get("title"):
                item.filename = info["title"]
        except Exception:
            pass

        stop_event = threading.Event()
        self._stop_events[item.id] = stop_event

        with self._lock:
            self._downloads[item.id] = item

        thread = threading.Thread(
            target=self._run_download, args=(item, stop_event), daemon=True
        )
        self._threads[item.id] = thread
        thread.start()

        return {
            "status": "started",
            "id": item.id,
            "filename": item.filename,
            "site": item.site_name,
            "category": item.category.value,
            "file_size": format_size(item.file_size) if item.file_size else "Detecting...",
        }

    def _run_download(self, item: DownloadItem, stop_event: threading.Event):
        """Run download in background thread."""
        downloader = self.router.get_downloader(item.url)

        original_on_progress = downloader.on_progress
        original_on_complete = downloader.on_complete
        original_on_error = downloader.on_error

        downloader.on_progress = None
        downloader.on_complete = None
        downloader.on_error = None

        try:
            item.status = DownloadStatus.DOWNLOADING
            item.started_at = time.time()
            downloader.download(item, stop_event)

            if not stop_event.is_set():
                item.status = DownloadStatus.COMPLETED
                item.progress = 100.0
                item.completed_at = time.time()
                item.speed = 0.0
                item.eta = 0.0
        except Exception as e:
            if stop_event.is_set():
                item.status = DownloadStatus.PAUSED
            else:
                item.status = DownloadStatus.ERROR
                item.error_message = str(e)
        finally:
            downloader.on_progress = original_on_progress
            downloader.on_complete = original_on_complete
            downloader.on_error = original_on_error
            self._threads.pop(item.id, None)
            self._stop_events.pop(item.id, None)

    def pause_download(self, item_id: str) -> dict:
        with self._lock:
            item = self._downloads.get(item_id)
            if item and item.status == DownloadStatus.DOWNLOADING:
                if item_id in self._stop_events:
                    self._stop_events[item_id].set()
                item.status = DownloadStatus.PAUSED
                return {"status": "paused", "filename": item.filename}
        return {"status": "error", "message": "Download not found or not active"}

    def resume_download(self, item_id: str) -> dict:
        with self._lock:
            item = self._downloads.get(item_id)
            if item and item.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
                item.status = DownloadStatus.PENDING
                item.error_message = ""
                stop_event = threading.Event()
                self._stop_events[item_id] = stop_event
                thread = threading.Thread(
                    target=self._run_download, args=(item, stop_event), daemon=True
                )
                self._threads[item_id] = thread
                thread.start()
                return {"status": "resumed", "filename": item.filename}
        return {"status": "error", "message": "Download not found or not pausable"}

    def cancel_download(self, item_id: str) -> dict:
        with self._lock:
            item = self._downloads.get(item_id)
            if item:
                if item_id in self._stop_events:
                    self._stop_events[item_id].set()
                item.status = DownloadStatus.CANCELLED
                item.speed = 0.0
                return {"status": "cancelled", "filename": item.filename}
        return {"status": "error", "message": "Download not found"}

    def remove_download(self, item_id: str) -> dict:
        with self._lock:
            item = self._downloads.get(item_id)
            if item:
                if item_id in self._stop_events:
                    self._stop_events[item_id].set()
                self._downloads.pop(item_id, None)
                return {"status": "removed", "filename": item.filename}
        return {"status": "error", "message": "Download not found"}

    def get_download_list(self, category_filter: str = "All") -> list:
        with self._lock:
            items = list(self._downloads.values())

        rows = []
        for item in items:
            if category_filter != "All":
                if category_filter == "Completed" and item.status != DownloadStatus.COMPLETED:
                    continue
                elif category_filter == "Active" and item.status != DownloadStatus.DOWNLOADING:
                    continue
                elif category_filter == "Queued" and item.status not in (DownloadStatus.QUEUED, DownloadStatus.PENDING):
                    continue
                elif category_filter == "Paused" and item.status != DownloadStatus.PAUSED:
                    continue
                elif category_filter == "Error" and item.status != DownloadStatus.ERROR:
                    continue
                elif category_filter not in ("All", "Completed", "Active", "Queued", "Paused", "Error"):
                    if item.category.value != category_filter:
                        continue

            status_icon = {
                DownloadStatus.PENDING: "⏳",
                DownloadStatus.QUEUED: "⏳",
                DownloadStatus.DOWNLOADING: "⬇️",
                DownloadStatus.PAUSED: "⏸️",
                DownloadStatus.COMPLETED: "✅",
                DownloadStatus.ERROR: "❌",
                DownloadStatus.CANCELLED: "🚫",
            }.get(item.status, "❓")

            progress_text = f"{item.progress:.1f}%" if item.file_size > 0 else "N/A"
            speed_text = format_speed(item.speed) if item.speed > 0 else "—"
            eta_text = format_time(item.eta) if item.eta > 0 else "—"
            size_text = format_size(item.file_size) if item.file_size else "Unknown"

            rows.append([
                item.id,
                item.filename[:50] + ("..." if len(item.filename) > 50 else ""),
                size_text,
                f"{status_icon} {progress_text}",
                speed_text,
                eta_text,
                f"{status_icon} {item.status.value.title()}",
                item.site_name,
                item.category.value,
            ])

        return rows

    def get_download_info(self, item_id: str) -> dict:
        with self._lock:
            item = self._downloads.get(item_id)
            if not item:
                return {"error": "Download not found"}
            return {
                "id": item.id,
                "url": item.url,
                "filename": item.filename,
                "status": item.status.value,
                "category": item.category.value,
                "file_size": format_size(item.file_size) if item.file_size else "Unknown",
                "downloaded": format_size(item.downloaded),
                "progress": f"{item.progress:.1f}%",
                "speed": format_speed(item.speed) if item.speed > 0 else "—",
                "eta": format_time(item.eta) if item.eta > 0 else "—",
                "site": item.site_name,
                "save_path": item.save_path,
                "error": item.error_message or "None",
                "is_media": item.is_media,
                "media_format": item.media_format or "N/A",
                "media_quality": item.media_quality or "N/A",
                "resume_supported": item.resume_supported,
                "segments": item.num_segments,
            }

    def get_stats(self) -> dict:
        with self._lock:
            items = list(self._downloads.values())
        active = sum(1 for i in items if i.status == DownloadStatus.DOWNLOADING)
        completed = sum(1 for i in items if i.status == DownloadStatus.COMPLETED)
        paused = sum(1 for i in items if i.status == DownloadStatus.PAUSED)
        errors = sum(1 for i in items if i.status == DownloadStatus.ERROR)
        total_speed = sum(i.speed for i in items if i.status == DownloadStatus.DOWNLOADING)
        return {
            "total": len(items),
            "active": active,
            "completed": completed,
            "paused": paused,
            "errors": errors,
            "total_speed": format_speed(total_speed),
        }

    def detect_url(self, url: str) -> dict:
        if not is_url(url):
            return {"site": "Invalid URL", "filename": "", "file_size": "", "category": ""}
        site = self.router.detect_site(url)
        try:
            info = self.router.get_info(url)
            return {
                "site": site,
                "filename": info.get("filename", info.get("title", "Unknown")),
                "file_size": format_size(info.get("file_size", 0)) if info.get("file_size") else "Unknown",
                "category": "Video/Audio" if site == "YouTube/Media" else DownloadCategory.from_extension(
                    info.get("filename", "")
                ).value if info.get("filename") else "Other",
            }
        except Exception as e:
            return {"site": site, "filename": "Unknown", "file_size": "Unknown", "category": "Other", "error": str(e)}


# Global state
state = DownloadManagerState()


# ──────────────────────────────────────────────
#  Gradio 6 Interface
# ──────────────────────────────────────────────

def create_demo():
    """Create the Gradio demo interface."""

    with gr.Blocks(title="Xdl Download Manager") as demo:

        # ── Header ──
        gr.Markdown("# Xdl Download Manager\nOpen-source IDM alternative | 1000+ video sites | Multi-threaded downloads | Resume support")

        # ── Stats Row ──
        with gr.Row():
            stat_total = gr.Number(label="Total Downloads", value=0, interactive=False)
            stat_active = gr.Number(label="Active", value=0, interactive=False)
            stat_completed = gr.Number(label="Completed", value=0, interactive=False)
            stat_speed = gr.Textbox(label="Total Speed", value="0 B/s", interactive=False)

        # ── Main Tabs ──
        with gr.Tabs():
            # ═══════════════════════════════════
            # Tab 1: Add Download
            # ═══════════════════════════════════
            with gr.Tab("Add Download", id="add_tab"):
                with gr.Row():
                    with gr.Column(scale=2):
                        url_input = gr.Textbox(
                            label="Download URL",
                            placeholder="Paste URL here (YouTube, Google Drive, MediaFire, any direct link...)",
                            lines=1,
                            max_lines=1,
                        )
                        with gr.Row():
                            detect_btn = gr.Button("Detect Site", variant="secondary", size="sm")
                            detect_info = gr.JSON(label="Detection Result")
                        save_path_input = gr.Textbox(
                            label="Save Path",
                            value=state.default_save_path,
                            lines=1,
                        )

                    with gr.Column(scale=1):
                        download_type = gr.Radio(
                            choices=["Video", "Audio"],
                            value="Video",
                            label="Download Type",
                        )
                        quality_dropdown = gr.Dropdown(
                            choices=["Best Quality", "720p", "480p", "360p", "240p"],
                            value="Best Quality",
                            label="Video Quality",
                        )
                        audio_format_dropdown = gr.Dropdown(
                            choices=["MP3", "AAC", "FLAC", "Opus", "WAV", "Best Quality"],
                            value="MP3",
                            label="Audio Format",
                            interactive=False,
                        )
                        segments_slider = gr.Slider(
                            minimum=1, maximum=32, value=8, step=1,
                            label="Download Segments",
                            info="More segments = faster for large files",
                        )

                with gr.Row():
                    add_btn = gr.Button("Start Download", variant="primary", size="lg")
                    add_result = gr.Textbox(label="Status", interactive=False)

                gr.Markdown("### Batch Download")
                batch_urls = gr.Textbox(
                    label="Multiple URLs (one per line)",
                    placeholder="https://youtube.com/watch?v=...\nhttps://vimeo.com/...\nhttps://example.com/file.zip",
                    lines=4,
                )
                batch_btn = gr.Button("Add All URLs", variant="secondary")
                batch_result = gr.Textbox(label="Batch Status", interactive=False)

            # ═══════════════════════════════════
            # Tab 2: Downloads
            # ═══════════════════════════════════
            with gr.Tab("Downloads", id="downloads_tab"):
                with gr.Row():
                    category_filter = gr.Dropdown(
                        choices=[
                            "All", "Active", "Completed", "Paused", "Error", "Queued",
                            "Video", "Audio", "Document", "Compressed", "Program", "Image", "Other",
                        ],
                        value="All",
                        label="Filter by Category",
                        scale=1,
                    )
                    refresh_btn = gr.Button("Refresh", variant="secondary", size="sm", scale=0)

                downloads_table = gr.Dataframe(
                    headers=["ID", "Filename", "Size", "Progress", "Speed", "ETA", "Status", "Site", "Category"],
                    label="Download List",
                    interactive=False,
                    wrap=True,
                    column_widths=["60px", "200px", "80px", "100px", "80px", "60px", "100px", "100px", "80px"],
                )

                with gr.Row():
                    with gr.Column(scale=1):
                        selected_id = gr.Textbox(label="Selected Download ID", placeholder="Enter download ID from table above")
                    with gr.Column(scale=2):
                        with gr.Row():
                            resume_btn = gr.Button("Resume", variant="primary")
                            pause_btn = gr.Button("Pause", variant="secondary")
                            cancel_btn = gr.Button("Cancel", variant="stop")
                            remove_btn = gr.Button("Remove", variant="secondary")

                action_result = gr.Textbox(label="Action Result", interactive=False)
                download_details = gr.JSON(label="Download Details")

            # ═══════════════════════════════════
            # Tab 3: URL Info
            # ═══════════════════════════════════
            with gr.Tab("URL Info", id="info_tab"):
                info_url = gr.Textbox(
                    label="URL to Analyze",
                    placeholder="Enter any URL to get download information...",
                    lines=1,
                )
                info_btn = gr.Button("Analyze URL", variant="primary")
                info_result = gr.JSON(label="URL Information")

                gr.Markdown("""
                ### Supported Sites
                | Category | Sites |
                |----------|-------|
                | **Video** | YouTube, Vimeo, Dailymotion, TikTok, Twitch, Rumble, Odysee, Bilibili, and 900+ more |
                | **Social** | Twitter/X, Facebook, Instagram, Reddit |
                | **Audio** | SoundCloud, Bandcamp, Audiomack, Mixcloud |
                | **Cloud** | Google Drive, MediaFire, Pixeldrain, HuggingFace |
                | **Generic** | Any HTTP/HTTPS direct download link |
                """)

            # ═══════════════════════════════════
            # Tab 4: Settings
            # ═══════════════════════════════════
            with gr.Tab("Settings", id="settings_tab"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### General Settings")
                        settings_save_path = gr.Textbox(
                            label="Default Save Path",
                            value=state.default_save_path,
                        )
                        settings_concurrent = gr.Slider(
                            minimum=1, maximum=10, value=3, step=1,
                            label="Max Concurrent Downloads",
                        )
                        settings_segments = gr.Slider(
                            minimum=1, maximum=32, value=8, step=1,
                            label="Default Segments",
                        )

                    with gr.Column():
                        gr.Markdown("### Connection Settings")
                        settings_proxy = gr.Textbox(
                            label="Proxy Server",
                            placeholder="http://proxy:port or socks5://proxy:port",
                        )
                        settings_user_agent = gr.Textbox(
                            label="Custom User-Agent",
                            placeholder="Leave empty for default",
                        )
                        settings_speed_limit = gr.Number(
                            label="Speed Limit (KB/s, 0 = unlimited)",
                            value=0,
                        )

                save_settings_btn = gr.Button("Save Settings", variant="primary")
                settings_result = gr.Textbox(label="Settings Status", interactive=False)

            # ═══════════════════════════════════
            # Tab 5: About
            # ═══════════════════════════════════
            with gr.Tab("About", id="about_tab"):
                gr.Markdown("""
                # Xdl Download Manager v2.0.0

                **An open-source alternative to Internet Download Manager (IDM)**

                Built with Python, PyQt5, Gradio 6, yt-dlp, and requests.

                ## Features
                - **Multi-threaded Downloads** — Up to 32 segments for maximum speed
                - **Resume Support** — Pause and resume downloads anytime
                - **1000+ Video Sites** — YouTube, Vimeo, TikTok, Twitter, and more
                - **Audio Extraction** — Convert videos to MP3, AAC, FLAC, Opus, WAV
                - **Cloud Storage** — Google Drive, MediaFire, Pixeldrain, HuggingFace
                - **Smart Categories** — Auto-organize by file type
                - **Batch Download** — Add multiple URLs at once
                - **CLI Mode** — `python3 main.py --cli URL`
                - **GUI Mode** — `python3 main.py`
                - **Web Demo** — This Gradio interface!

                ## Powered By
                - [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Video/audio extraction engine
                - [Gradio 6](https://gradio.app) — Web interface framework
                - [PyQt5](https://riverbankcomputing.com/software/pyqt/) — Desktop GUI
                - [requests](https://docs.python-requests.org/) — HTTP library

                ## License
                Unlicense — Free and unencumbered software released into the public domain.

                ## Links
                - **GitHub**: [https://github.com/BF667/Xdl](https://github.com/BF667/Xdl)
                """)

        # ──────────────────────────────────────
        #  Event Handlers
        # ──────────────────────────────────────

        def detect_url_handler(url):
            if not url or not url.strip():
                return {"site": "No URL provided", "filename": "", "file_size": "", "category": ""}
            return state.detect_url(url.strip())

        def toggle_audio_format(download_type):
            return gr.Dropdown(interactive=(download_type == "Audio"))

        def toggle_quality(download_type):
            return gr.Dropdown(interactive=(download_type != "Audio"))

        def add_download_handler(url, save_path, download_type, quality, audio_format, segments):
            if not url or not url.strip():
                return "Please enter a URL"
            result = state.add_download(
                url=url.strip(), save_path=save_path,
                download_type=download_type, quality=quality,
                audio_format=audio_format, segments=int(segments),
            )
            if result["status"] == "started":
                return f"Download started: {result['filename']} ({result['site']})"
            return f"Error: {result.get('message', 'Unknown error')}"

        def batch_download_handler(urls_text, save_path):
            if not urls_text or not urls_text.strip():
                return "No URLs provided"
            urls = [u.strip() for u in urls_text.strip().split("\n") if is_url(u.strip())]
            if not urls:
                return "No valid URLs found"
            results = []
            for url in urls:
                result = state.add_download(url=url, save_path=save_path)
                results.append(f"{'OK' if result['status'] == 'started' else 'FAIL'}: {result.get('filename', url[:50])}")
            return f"Added {len(urls)} downloads:\n" + "\n".join(results)

        def refresh_downloads(category_filter):
            return state.get_download_list(category_filter)

        def update_stats():
            stats = state.get_stats()
            return stats["total"], stats["active"], stats["completed"], stats["total_speed"]

        def resume_handler(item_id):
            if not item_id or not item_id.strip():
                return "Please enter a download ID", None
            result = state.resume_download(item_id.strip())
            return f"{'Resumed' if result['status'] == 'resumed' else 'Error: ' + result.get('message', 'Unknown')}: {result.get('filename', '')}", None

        def pause_handler(item_id):
            if not item_id or not item_id.strip():
                return "Please enter a download ID", None
            result = state.pause_download(item_id.strip())
            return f"{'Paused' if result['status'] == 'paused' else 'Error: ' + result.get('message', 'Unknown')}: {result.get('filename', '')}", None

        def cancel_handler(item_id):
            if not item_id or not item_id.strip():
                return "Please enter a download ID", None
            result = state.cancel_download(item_id.strip())
            return f"{'Cancelled' if result['status'] == 'cancelled' else 'Error: ' + result.get('message', 'Unknown')}: {result.get('filename', '')}", None

        def remove_handler(item_id):
            if not item_id or not item_id.strip():
                return "Please enter a download ID", None
            result = state.remove_download(item_id.strip())
            return f"{'Removed' if result['status'] == 'removed' else 'Error: ' + result.get('message', 'Unknown')}: {result.get('filename', '')}", None

        def info_handler(url):
            if not url or not url.strip():
                return {"error": "Please enter a URL"}
            return state.detect_url(url.strip())

        def details_handler(item_id):
            if not item_id or not item_id.strip():
                return {"error": "Please enter a download ID"}
            return state.get_download_info(item_id.strip())

        def save_settings_handler(save_path, concurrent, segments, proxy, user_agent, speed_limit):
            state.default_save_path = save_path
            state.router._fallback._engine.max_concurrent = int(concurrent)
            state.router._fallback._engine.default_segments = int(segments)
            if proxy:
                state.router._fallback._engine.proxy = proxy
            if user_agent:
                state.router._fallback._engine.user_agent = user_agent
            return "Settings saved successfully!"

        # ──────────────────────────────────────
        #  Wire up events
        # ──────────────────────────────────────

        detect_btn.click(fn=detect_url_handler, inputs=[url_input], outputs=[detect_info])

        download_type.change(fn=toggle_audio_format, inputs=[download_type], outputs=[audio_format_dropdown])
        download_type.change(fn=toggle_quality, inputs=[download_type], outputs=[quality_dropdown])

        add_btn.click(
            fn=add_download_handler,
            inputs=[url_input, save_path_input, download_type, quality_dropdown, audio_format_dropdown, segments_slider],
            outputs=[add_result],
        ).then(
            fn=refresh_downloads, inputs=[category_filter], outputs=[downloads_table],
        ).then(
            fn=update_stats, outputs=[stat_total, stat_active, stat_completed, stat_speed],
        )

        batch_btn.click(
            fn=batch_download_handler, inputs=[batch_urls, save_path_input], outputs=[batch_result],
        ).then(
            fn=refresh_downloads, inputs=[category_filter], outputs=[downloads_table],
        )

        refresh_btn.click(
            fn=refresh_downloads, inputs=[category_filter], outputs=[downloads_table],
        ).then(
            fn=update_stats, outputs=[stat_total, stat_active, stat_completed, stat_speed],
        )

        category_filter.change(fn=refresh_downloads, inputs=[category_filter], outputs=[downloads_table])

        resume_btn.click(fn=resume_handler, inputs=[selected_id], outputs=[action_result, download_details]).then(
            fn=refresh_downloads, inputs=[category_filter], outputs=[downloads_table])

        pause_btn.click(fn=pause_handler, inputs=[selected_id], outputs=[action_result, download_details]).then(
            fn=refresh_downloads, inputs=[category_filter], outputs=[downloads_table])

        cancel_btn.click(fn=cancel_handler, inputs=[selected_id], outputs=[action_result, download_details]).then(
            fn=refresh_downloads, inputs=[category_filter], outputs=[downloads_table])

        remove_btn.click(fn=remove_handler, inputs=[selected_id], outputs=[action_result, download_details]).then(
            fn=refresh_downloads, inputs=[category_filter], outputs=[downloads_table],
        ).then(
            fn=update_stats, outputs=[stat_total, stat_active, stat_completed, stat_speed],
        )

        selected_id.change(fn=details_handler, inputs=[selected_id], outputs=[download_details])

        info_btn.click(fn=info_handler, inputs=[info_url], outputs=[info_result])

        save_settings_btn.click(
            fn=save_settings_handler,
            inputs=[settings_save_path, settings_concurrent, settings_segments, settings_proxy, settings_user_agent, settings_speed_limit],
            outputs=[settings_result],
        )

        # Auto-refresh using gr.Timer (Gradio 6+)
        timer = gr.Timer(value=3.0)
        timer.tick(fn=refresh_downloads, inputs=[category_filter], outputs=[downloads_table])
        timer.tick(fn=update_stats, outputs=[stat_total, stat_active, stat_completed, stat_speed])

    return demo


# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Xdl Download Manager - Gradio Web Demo")
    parser.add_argument("--share", action="store_true", help="Create a public share link")
    parser.add_argument("--port", type=int, default=7860, help="Port to run on (default: 7860)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Xdl Download Manager - Gradio Web Demo")
    print("  Powered by Gradio 6+")
    print("=" * 60)
    print(f"\n  Starting server on http://{args.host}:{args.port}")
    if args.share:
        print("  Public share link will be generated")
    print("\n  Features:")
    print("    - Add single or batch downloads")
    print("    - Video/Audio quality selection")
    print("    - Pause/Resume/Cancel controls")
    print("    - Real-time progress tracking")
    print("    - URL detection and info")
    print("    - 1000+ video sites supported")
    print("=" * 60 + "\n")

    demo = create_demo()
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        inbrowser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
