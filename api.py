#!/usr/bin/env python3
"""
Xdl Download Manager - FastAPI Backend Server
REST API + WebSocket for the TypeScript web frontend.

Usage:
    python3 api.py                          # Launch API on http://localhost:8000
    python3 api.py --port 8080              # Custom port
    python3 api.py --ngrok                  # Launch with ngrok tunnel
    python3 api.py --ngrok --ngrok-token X  # With custom ngrok auth token
"""

import os
import sys
import time
import json
import threading
import argparse
import asyncio
from typing import Optional, List
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from xdl.downloaders.router import DownloadRouter
from xdl.core.models import DownloadItem, DownloadStatus, DownloadCategory
from xdl.utils.helpers import format_size, format_speed, format_time, is_url


# ──────────────────────────────────────────────
#  Pydantic Models (Request/Response)
# ──────────────────────────────────────────────

class AddDownloadRequest(BaseModel):
    url: str
    save_path: str = ""
    download_type: str = "Video"  # Video or Audio
    quality: str = "Best Quality"
    audio_format: str = "MP3"
    segments: int = 8

class BatchDownloadRequest(BaseModel):
    urls: List[str]
    save_path: str = ""

class ActionRequest(BaseModel):
    item_id: str

class SettingsRequest(BaseModel):
    default_save_path: Optional[str] = None
    max_concurrent: Optional[int] = None
    default_segments: Optional[int] = None
    proxy: Optional[str] = None
    user_agent: Optional[str] = None
    speed_limit_kb: Optional[int] = None

class DetectRequest(BaseModel):
    url: str


# ──────────────────────────────────────────────
#  Download Manager State
# ──────────────────────────────────────────────

class DownloadManager:
    """Thread-safe download manager shared between API and WebSocket."""

    def __init__(self):
        self.router = DownloadRouter()
        self._downloads: dict = {}
        self._threads: dict = {}
        self._stop_events: dict = {}
        self._lock = threading.Lock()
        self.default_save_path = os.path.join(
            os.path.expanduser("~"), "Downloads", "Xdl"
        )
        self.max_concurrent = 3
        self.default_segments = 8
        self.proxy = ""
        self.user_agent = ""
        self.speed_limit_kb = 0
        os.makedirs(self.default_save_path, exist_ok=True)

        # WebSocket subscribers
        self._ws_clients: List[WebSocket] = []
        self._ws_lock = threading.Lock()

    def add_ws_client(self, ws: WebSocket):
        with self._ws_lock:
            self._ws_clients.append(ws)

    def remove_ws_client(self, ws: WebSocket):
        with self._ws_lock:
            try:
                self._ws_clients.remove(ws)
            except ValueError:
                pass

    async def broadcast_update(self):
        """Send current state to all connected WebSocket clients."""
        data = self._get_full_state()
        message = json.dumps(data)
        with self._ws_lock:
            dead = []
            for ws in self._ws_clients:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._ws_clients.remove(ws)

    def _get_full_state(self) -> dict:
        with self._lock:
            items = list(self._downloads.values())
        downloads = []
        for item in items:
            downloads.append(self._item_to_dict(item))
        active = sum(1 for i in items if i.status == DownloadStatus.DOWNLOADING)
        completed = sum(1 for i in items if i.status == DownloadStatus.COMPLETED)
        paused = sum(1 for i in items if i.status == DownloadStatus.PAUSED)
        errors = sum(1 for i in items if i.status == DownloadStatus.ERROR)
        total_speed = sum(i.speed for i in items if i.status == DownloadStatus.DOWNLOADING)
        return {
            "downloads": downloads,
            "stats": {
                "total": len(items),
                "active": active,
                "completed": completed,
                "paused": paused,
                "errors": errors,
                "total_speed": format_speed(total_speed),
                "total_speed_bytes": total_speed,
            }
        }

    def _item_to_dict(self, item: DownloadItem) -> dict:
        return {
            "id": item.id,
            "url": item.url,
            "filename": item.filename,
            "save_path": item.save_path,
            "status": item.status.value,
            "category": item.category.value,
            "file_size": item.file_size,
            "file_size_formatted": format_size(item.file_size) if item.file_size else "Unknown",
            "downloaded": item.downloaded,
            "downloaded_formatted": format_size(item.downloaded),
            "speed": item.speed,
            "speed_formatted": format_speed(item.speed) if item.speed > 0 else "—",
            "progress": round(item.progress, 1),
            "num_segments": item.num_segments,
            "resume_supported": item.resume_supported,
            "created_at": item.created_at,
            "started_at": item.started_at,
            "completed_at": item.completed_at,
            "eta": item.eta,
            "eta_formatted": format_time(item.eta) if item.eta > 0 else "—",
            "error_message": item.error_message,
            "site_name": item.site_name,
            "is_media": item.is_media,
            "media_format": item.media_format,
            "media_quality": item.media_quality,
        }

    def add_download(self, req: AddDownloadRequest) -> dict:
        if not is_url(req.url):
            return {"status": "error", "message": "Invalid URL provided"}

        save_path = req.save_path or self.default_save_path
        os.makedirs(save_path, exist_ok=True)

        media_format = ""
        media_quality = ""

        if req.download_type == "Audio":
            media_format = req.audio_format.lower() if req.audio_format != "Best Quality" else "bestaudio"
        else:
            quality_map = {
                "Best Quality": "best",
                "720p": "720p",
                "480p": "480p",
                "360p": "360p",
                "240p": "240p",
            }
            media_quality = quality_map.get(req.quality, "best")

        item = self.router.create_item(url=req.url, save_path=save_path)

        if req.download_type == "Audio":
            item.category = DownloadCategory.AUDIO
            item.is_media = True
            item.media_format = media_format
        else:
            if item.category != DownloadCategory.AUDIO:
                item.category = DownloadCategory.VIDEO
            item.is_media = True
            item.media_quality = media_quality

        item.num_segments = req.segments

        try:
            info = self.router.get_info(req.url)
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
            "download": self._item_to_dict(item),
        }

    def _run_download(self, item: DownloadItem, stop_event: threading.Event):
        downloader = self.router.get_downloader(item.url)
        original_on_progress = downloader.on_progress
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
            self._threads.pop(item.id, None)
            self._stop_events.pop(item.id, None)

    def pause_download(self, item_id: str) -> dict:
        with self._lock:
            item = self._downloads.get(item_id)
            if item and item.status == DownloadStatus.DOWNLOADING:
                if item_id in self._stop_events:
                    self._stop_events[item_id].set()
                item.status = DownloadStatus.PAUSED
                return {"status": "paused", "download": self._item_to_dict(item)}
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
                return {"status": "resumed", "download": self._item_to_dict(item)}
        return {"status": "error", "message": "Download not found or not pausable"}

    def cancel_download(self, item_id: str) -> dict:
        with self._lock:
            item = self._downloads.get(item_id)
            if item:
                if item_id in self._stop_events:
                    self._stop_events[item_id].set()
                item.status = DownloadStatus.CANCELLED
                item.speed = 0.0
                return {"status": "cancelled", "download": self._item_to_dict(item)}
        return {"status": "error", "message": "Download not found"}

    def remove_download(self, item_id: str) -> dict:
        with self._lock:
            item = self._downloads.get(item_id)
            if item:
                if item_id in self._stop_events:
                    self._stop_events[item_id].set()
                self._downloads.pop(item_id, None)
                return {"status": "removed", "download": self._item_to_dict(item)}
        return {"status": "error", "message": "Download not found"}

    def get_downloads(self, category: str = "All") -> List[dict]:
        with self._lock:
            items = list(self._downloads.values())

        result = []
        for item in items:
            if category != "All":
                status_map = {
                    "Active": DownloadStatus.DOWNLOADING,
                    "Completed": DownloadStatus.COMPLETED,
                    "Paused": DownloadStatus.PAUSED,
                    "Error": DownloadStatus.ERROR,
                    "Queued": DownloadStatus.QUEUED,
                }
                if category in status_map:
                    if item.status != status_map[category]:
                        continue
                elif item.category.value != category:
                    continue
            result.append(self._item_to_dict(item))
        return result

    def get_download(self, item_id: str) -> Optional[dict]:
        with self._lock:
            item = self._downloads.get(item_id)
            if item:
                return self._item_to_dict(item)
        return None

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
            "total_speed_bytes": total_speed,
        }

    def detect_url(self, url: str) -> dict:
        if not is_url(url):
            return {"site": "Invalid URL", "filename": "", "file_size": "", "category": "", "error": "Invalid URL"}
        site = self.router.detect_site(url)
        try:
            info = self.router.get_info(url)
            return {
                "site": site,
                "filename": info.get("filename", info.get("title", "Unknown")),
                "file_size": format_size(info.get("file_size", 0)) if info.get("file_size") else "Unknown",
                "file_size_bytes": info.get("file_size", 0),
                "category": "Video/Audio" if site == "YouTube/Media" else DownloadCategory.from_extension(
                    info.get("filename", "")
                ).value if info.get("filename") else "Other",
            }
        except Exception as e:
            return {"site": site, "filename": "Unknown", "file_size": "Unknown", "category": "Other", "error": str(e)}

    def get_settings(self) -> dict:
        return {
            "default_save_path": self.default_save_path,
            "max_concurrent": self.max_concurrent,
            "default_segments": self.default_segments,
            "proxy": self.proxy,
            "user_agent": self.user_agent,
            "speed_limit_kb": self.speed_limit_kb,
        }

    def update_settings(self, req: SettingsRequest) -> dict:
        if req.default_save_path is not None:
            self.default_save_path = req.default_save_path
            os.makedirs(self.default_save_path, exist_ok=True)
        if req.max_concurrent is not None:
            self.max_concurrent = req.max_concurrent
        if req.default_segments is not None:
            self.default_segments = req.default_segments
        if req.proxy is not None:
            self.proxy = req.proxy
        if req.user_agent is not None:
            self.user_agent = req.user_agent
        if req.speed_limit_kb is not None:
            self.speed_limit_kb = req.speed_limit_kb
        return {"status": "saved", "settings": self.get_settings()}


# ──────────────────────────────────────────────
#  FastAPI App
# ──────────────────────────────────────────────

manager = DownloadManager()

app = FastAPI(
    title="Xdl Download Manager API",
    description="REST API + WebSocket for the Xdl download manager web frontend",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST API Endpoints ──

@app.get("/api/stats")
async def get_stats():
    return manager.get_stats()


@app.post("/api/downloads")
async def add_download(req: AddDownloadRequest):
    result = manager.add_download(req)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    await manager.broadcast_update()
    return result


@app.post("/api/downloads/batch")
async def batch_download(req: BatchDownloadRequest):
    results = []
    for url in req.urls:
        if is_url(url):
            r = manager.add_download(AddDownloadRequest(
                url=url, save_path=req.save_path or manager.default_save_path
            ))
            results.append(r)
    await manager.broadcast_update()
    return {"status": "batch_added", "count": len(results), "results": results}


@app.get("/api/downloads")
async def list_downloads(category: str = "All"):
    return {"downloads": manager.get_downloads(category)}


@app.get("/api/downloads/{item_id}")
async def get_download(item_id: str):
    result = manager.get_download(item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Download not found")
    return result


@app.post("/api/downloads/{item_id}/pause")
async def pause_download(item_id: str):
    result = manager.pause_download(item_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    await manager.broadcast_update()
    return result


@app.post("/api/downloads/{item_id}/resume")
async def resume_download(item_id: str):
    result = manager.resume_download(item_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    await manager.broadcast_update()
    return result


@app.post("/api/downloads/{item_id}/cancel")
async def cancel_download(item_id: str):
    result = manager.cancel_download(item_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    await manager.broadcast_update()
    return result


@app.delete("/api/downloads/{item_id}")
async def remove_download(item_id: str):
    result = manager.remove_download(item_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    await manager.broadcast_update()
    return result


@app.post("/api/detect")
async def detect_url(req: DetectRequest):
    return manager.detect_url(req.url)


@app.get("/api/settings")
async def get_settings():
    return manager.get_settings()


@app.put("/api/settings")
async def update_settings(req: SettingsRequest):
    return manager.update_settings(req)


@app.get("/api/sites")
async def supported_sites():
    return {"sites": manager.router.supported_sites}


# ── WebSocket for real-time updates ──

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    manager.add_ws_client(websocket)
    try:
        # Send initial state
        state = manager._get_full_state()
        await websocket.send_text(json.dumps(state))

        # Keep connection alive, listen for client messages
        while True:
            try:
                data = await websocket.receive_text()
                # Client can request manual refresh
                if data == "refresh":
                    state = manager._get_full_state()
                    await websocket.send_text(json.dumps(state))
            except WebSocketDisconnect:
                break
    finally:
        manager.remove_ws_client(websocket)


# ── Health check ──

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}


# ──────────────────────────────────────────────
#  Periodic WebSocket broadcast
# ──────────────────────────────────────────────

async def periodic_broadcast():
    """Broadcast download updates every 2 seconds."""
    while True:
        await asyncio.sleep(2)
        if manager._ws_clients:
            await manager.broadcast_update()


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_broadcast())


# Note: @app.on_event("startup") is deprecated in newer FastAPI versions.
# For FastAPI >= 0.100, consider using lifespan context managers instead:
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     task = asyncio.create_task(periodic_broadcast())
#     yield
#     task.cancel()
# app = FastAPI(lifespan=lifespan, ...)


# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Xdl Download Manager - API Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to run on (default: 8000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--ngrok", action="store_true", help="Start ngrok tunnel")
    parser.add_argument("--ngrok-token", type=str, default="", help="Ngrok auth token")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Xdl Download Manager - API Server")
    print("  Powered by FastAPI + WebSocket")
    print("=" * 60)
    print(f"\n  API: http://{args.host}:{args.port}")
    print(f"  Docs: http://{args.host}:{args.port}/docs")
    print(f"  WebSocket: ws://{args.host}:{args.port}/ws")

    if args.ngrok:
        try:
            from pyngrok import ngrok as ngrok_lib
            if args.ngrok_token:
                ngrok_lib.set_auth_token(args.ngrok_token)
            public_url = ngrok_lib.connect(args.port)
            print(f"\n  Ngrok tunnel: {public_url}")
            print(f"  Public API: {public_url}/api")
            print(f"  Public WebSocket: ws://{public_url.replace('https://', '').replace('http://', '')}/ws")
        except ImportError:
            print("\n  [WARNING] pyngrok not installed. Install with: pip install pyngrok")
        except Exception as e:
            print(f"\n  [WARNING] Ngrok failed: {e}")

    print("\n  Endpoints:")
    print("    GET  /api/stats            - Download statistics")
    print("    POST /api/downloads        - Add download")
    print("    GET  /api/downloads        - List downloads")
    print("    GET  /api/downloads/:id    - Get download details")
    print("    POST /api/downloads/:id/pause  - Pause download")
    print("    POST /api/downloads/:id/resume - Resume download")
    print("    POST /api/downloads/:id/cancel - Cancel download")
    print("    DELETE /api/downloads/:id  - Remove download")
    print("    POST /api/detect           - Detect URL info")
    print("    GET  /api/settings         - Get settings")
    print("    PUT  /api/settings         - Update settings")
    print("    WS   /ws                   - Real-time updates")
    print("=" * 60 + "\n")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
