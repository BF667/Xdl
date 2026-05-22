"""
About Dialog - shows application information.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QTextBrowser
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from .. import __version__, __app_name__


class AboutDialog(QDialog):
    """About dialog for the download manager."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {__app_name__}")
        self.setMinimumSize(450, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # App name
        name_label = QLabel(__app_name__)
        name_label.setFont(QFont("Arial", 20, QFont.Bold))
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        # Version
        version_label = QLabel(f"Version {__version__}")
        version_label.setFont(QFont("Arial", 12))
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #666;")
        layout.addWidget(version_label)

        # Description
        desc = QTextBrowser()
        desc.setOpenExternalLinks(True)
        desc.setHtml("""
        <div style="padding: 10px; font-family: Arial;">
            <p><b>Xdl Download Manager</b> is a powerful, open-source alternative to
            Internet Download Manager (IDM) built with Python.</p>

            <h3>Features:</h3>
            <ul>
                <li><b>Multi-threaded Downloads</b> - Up to 32 segments for maximum speed</li>
                <li><b>Resume Support</b> - Pause and resume downloads anytime</li>
                <li><b>1000+ Video Sites</b> - YouTube, Vimeo, TikTok, Twitter, and more</li>
                <li><b>Audio Extraction</b> - Convert videos to MP3, AAC, FLAC, etc.</li>
                <li><b>Cloud Storage</b> - Google Drive, MediaFire, Pixeldrain, HuggingFace</li>
                <li><b>Smart Queue</b> - Priority-based download scheduling</li>
                <li><b>Clipboard Monitor</b> - Auto-detect URLs from clipboard</li>
                <li><b>Category Management</b> - Auto-organize by file type</li>
                <li><b>Browser Integration</b> - Catch download links automatically</li>
            </ul>

            <h3>Supported Sites:</h3>
            <p>YouTube, Vimeo, Dailymotion, Twitter/X, Facebook, Instagram,
            TikTok, Twitch, Reddit, SoundCloud, Bandcamp, Bilibili,
            Google Drive, MediaFire, Pixeldrain, HuggingFace, and
            <b>1000+ more</b> via yt-dlp!</p>

            <h3>Powered By:</h3>
            <ul>
                <li>Python + PyQt5</li>
                <li>yt-dlp (video/audio extraction)</li>
                <li>requests (HTTP downloads)</li>
            </ul>

            <p style="color: #666;">Based on the original Xdl project by BF667</p>
        </div>
        """)
        layout.addWidget(desc)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 24px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
