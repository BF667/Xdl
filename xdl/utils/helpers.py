"""
Utility helper functions for the download manager.
"""

import re
from urllib.parse import urlparse


def format_size(size_bytes: float) -> str:
    """Format bytes to human-readable size string."""
    if size_bytes < 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def format_speed(speed_bytes: float) -> str:
    """Format bytes per second to human-readable speed string."""
    if speed_bytes <= 0:
        return "0 B/s"
    return format_size(speed_bytes) + "/s"


def format_time(seconds: float) -> str:
    """Format seconds to human-readable time string."""
    if seconds <= 0:
        return "--:--"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    elif minutes > 0:
        return f"{minutes}m {secs:02d}s"
    else:
        return f"{secs}s"


def is_url(text: str) -> bool:
    """Check if text is a valid URL."""
    try:
        result = urlparse(text.strip())
        return all([result.scheme in ("http", "https", "ftp"), result.hostname])
    except Exception:
        return False


def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from a filename."""
    # Remove characters that are invalid in filenames
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    # Limit length
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        if ext:
            sanitized = name[:250] + '.' + ext
        else:
            sanitized = sanitized[:255]
    return sanitized or "download"


def get_domain_from_url(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""


def guess_filename_from_url(url: str) -> str:
    """Guess filename from URL path."""
    try:
        parsed = urlparse(url)
        path = parsed.path
        if path:
            filename = path.rstrip("/").rsplit("/", 1)[-1]
            if filename and "." in filename:
                return filename
        return "download"
    except Exception:
        return "download"
