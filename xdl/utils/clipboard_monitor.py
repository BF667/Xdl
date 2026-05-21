"""
Clipboard monitor - watches the system clipboard for URLs
and triggers download prompts automatically.
"""

import time
import threading
from typing import Optional, Callable
from urllib.parse import urlparse

try:
    import pyperclip
except ImportError:
    pyperclip = None


class ClipboardMonitor:
    """
    Monitors the system clipboard for URLs.
    When a new URL is detected, it can trigger a callback
    to add the URL as a download.
    """

    def __init__(self, check_interval: float = 1.0):
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_clipboard = ""
        self._stop_event = threading.Event()

        # Callbacks
        self.on_url_detected: Optional[Callable] = None

        # URL patterns to ignore (browser-specific)
        self._ignore_patterns = [
            "chrome://",
            "about:",
            "javascript:",
            "data:",
            "file:///",
        ]

    def start(self):
        """Start monitoring the clipboard."""
        if self._running or pyperclip is None:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop monitoring the clipboard."""
        self._running = False
        self._stop_event.set()

    def _monitor_loop(self):
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            try:
                current = pyperclip.paste()
                if current != self._last_clipboard:
                    self._last_clipboard = current
                    url = self._extract_url(current)
                    if url:
                        if self.on_url_detected:
                            self.on_url_detected(url)
            except Exception:
                pass

            self._stop_event.wait(self.check_interval)

    def _extract_url(self, text: str) -> Optional[str]:
        """Extract a valid URL from clipboard text."""
        text = text.strip()

        # Check if it's a direct URL
        if self._is_valid_url(text):
            return text

        # Try to extract URL from text
        words = text.split()
        for word in words:
            if self._is_valid_url(word):
                return word

        return None

    def _is_valid_url(self, text: str) -> bool:
        """Check if text is a valid download URL."""
        if not text or len(text) < 10:
            return False

        # Ignore non-download URLs
        for pattern in self._ignore_patterns:
            if text.startswith(pattern):
                return False

        try:
            parsed = urlparse(text)
            if parsed.scheme not in ("http", "https", "ftp"):
                return False
            if not parsed.hostname:
                return False
            return True
        except Exception:
            return False
