"""
Data models for the download manager.
"""

import uuid
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class DownloadStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"
    SCHEDULING = "scheduling"


class DownloadCategory(Enum):
    VIDEO = "Video"
    AUDIO = "Audio"
    DOCUMENT = "Document"
    COMPRESSED = "Compressed"
    PROGRAM = "Program"
    IMAGE = "Image"
    OTHER = "Other"

    @classmethod
    def from_extension(cls, filename: str) -> "DownloadCategory":
        """Determine category from file extension."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        video_exts = {
            "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v",
            "mpg", "mpeg", "3gp", "ts", "vob", "ogv", "m2ts"
        }
        audio_exts = {
            "mp3", "wav", "flac", "aac", "ogg", "wma", "m4a", "opus",
            "aiff", "ape", "alac", "wv", "tta"
        }
        doc_exts = {
            "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
            "txt", "rtf", "odt", "ods", "odp", "csv", "epub", "mobi"
        }
        compressed_exts = {
            "zip", "rar", "7z", "tar", "gz", "bz2", "xz", "lzma",
            "cab", "iso", "dmg", "pkg", "deb", "rpm"
        }
        program_exts = {
            "exe", "msi", "apk", "app", "bat", "sh", "jar", "deb"
        }
        image_exts = {
            "jpg", "jpeg", "png", "gif", "bmp", "svg", "webp",
            "ico", "tiff", "tif", "psd", "raw", "heic"
        }

        if ext in video_exts:
            return cls.VIDEO
        elif ext in audio_exts:
            return cls.AUDIO
        elif ext in doc_exts:
            return cls.DOCUMENT
        elif ext in compressed_exts:
            return cls.COMPRESSED
        elif ext in program_exts:
            return cls.PROGRAM
        elif ext in image_exts:
            return cls.IMAGE
        else:
            return cls.OTHER


@dataclass
class DownloadItem:
    """Represents a single download task."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    url: str = ""
    filename: str = "unknown"
    save_path: str = ""
    status: DownloadStatus = DownloadStatus.PENDING
    category: DownloadCategory = DownloadCategory.OTHER

    # Progress tracking
    file_size: int = 0
    downloaded: int = 0
    speed: float = 0.0  # bytes per second
    progress: float = 0.0  # 0-100

    # Download settings
    num_segments: int = 8
    resume_supported: bool = True

    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    eta: float = 0.0  # seconds remaining

    # Error info
    error_message: str = ""

    # Site-specific metadata
    site_name: str = ""
    thumbnail_url: str = ""
    format_info: str = ""
    quality: str = ""

    # For video/audio downloads
    is_media: bool = False
    media_format: str = ""
    media_quality: str = ""

    def update_progress(self, downloaded: int, speed: float = 0.0):
        """Update download progress."""
        self.downloaded = downloaded
        self.speed = speed

        if self.file_size > 0:
            self.progress = min(100.0, (downloaded / self.file_size) * 100)
            if speed > 0:
                remaining = self.file_size - downloaded
                self.eta = remaining / speed
            else:
                self.eta = 0.0
        else:
            self.progress = 0.0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "url": self.url,
            "filename": self.filename,
            "save_path": self.save_path,
            "status": self.status.value,
            "category": self.category.value,
            "file_size": self.file_size,
            "downloaded": self.downloaded,
            "speed": self.speed,
            "progress": self.progress,
            "num_segments": self.num_segments,
            "resume_supported": self.resume_supported,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "site_name": self.site_name,
            "format_info": self.format_info,
            "quality": self.quality,
            "is_media": self.is_media,
            "media_format": self.media_format,
            "media_quality": self.media_quality,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DownloadItem":
        """Deserialize from dictionary."""
        item = cls()
        for key, value in data.items():
            if key == "status":
                item.status = DownloadStatus(value)
            elif key == "category":
                item.category = DownloadCategory(value)
            else:
                setattr(item, key, value)
        return item
