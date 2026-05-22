"""
Add Download Dialog - prompts user for URL and download options.
"""

import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QPushButton,
    QFileDialog, QGroupBox, QCheckBox, QMessageBox,
    QTabWidget, QWidget, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QIcon

from ..core.models import DownloadItem, DownloadCategory
from ..downloaders.router import DownloadRouter
from ..utils.helpers import is_url


class InfoFetcherThread(QThread):
    """Background thread to fetch URL info."""
    info_ready = pyqtSignal(dict)

    def __init__(self, router: DownloadRouter, url: str):
        super().__init__()
        self.router = router
        self.url = url

    def run(self):
        try:
            info = self.router.get_info(self.url)
            info["site"] = self.router.detect_site(self.url)
            self.info_ready.emit(info)
        except Exception as e:
            self.info_ready.emit({"error": str(e)})


class AddDownloadDialog(QDialog):
    """Dialog for adding a new download with URL detection and format selection."""

    def __init__(self, router: DownloadRouter, default_path: str = "",
                 clipboard_url: str = "", parent=None):
        super().__init__(parent)
        self.router = router
        self.default_path = default_path or os.path.join(
            os.path.expanduser("~"), "Downloads", "Xdl"
        )
        self.download_item = None
        self._info_thread = None

        self.setWindowTitle("Add Download")
        self.setMinimumSize(550, 500)
        self.setup_ui()

        # Pre-fill clipboard URL
        if clipboard_url and is_url(clipboard_url):
            self.url_input.setText(clipboard_url)
            self._on_url_changed(clipboard_url)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # === URL Input ===
        url_group = QGroupBox("Download URL")
        url_layout = QHBoxLayout(url_group)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "Paste URL here (YouTube, Google Drive, MediaFire, any direct link...)"
        )
        self.url_input.textChanged.connect(self._on_url_changed)
        url_layout.addWidget(self.url_input)

        self.detect_btn = QPushButton("Detect")
        self.detect_btn.clicked.connect(self._detect_url)
        self.detect_btn.setToolTip("Auto-detect site and file info")
        url_layout.addWidget(self.detect_btn)

        layout.addWidget(url_group)

        # === Site Detection Label ===
        self.site_label = QLabel("Site: Not detected")
        self.site_label.setStyleSheet("color: #666; font-style: italic; padding: 4px;")
        layout.addWidget(self.site_label)

        # === File Info ===
        info_group = QGroupBox("File Information")
        info_layout = QFormLayout(info_group)

        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Auto-detected from URL")
        info_layout.addRow("Filename:", self.filename_input)

        self.size_label = QLabel("Unknown")
        info_layout.addRow("File Size:", self.size_label)

        layout.addWidget(info_group)

        # === Download Options ===
        options_group = QGroupBox("Download Options")
        options_layout = QFormLayout(options_group)

        # Save path
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit(self.default_path)
        path_layout.addWidget(self.path_input)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(self.browse_btn)
        options_layout.addRow("Save to:", path_layout)

        # Category
        self.category_combo = QComboBox()
        for cat in DownloadCategory:
            self.category_combo.addItem(cat.value, cat)
        self.category_combo.setCurrentText("Other")
        options_layout.addRow("Category:", self.category_combo)

        # Segments
        self.segments_spin = QSpinBox()
        self.segments_spin.setRange(1, 32)
        self.segments_spin.setValue(8)
        self.segments_spin.setToolTip("Number of download segments (more = faster for large files)")
        options_layout.addRow("Segments:", self.segments_spin)

        # Start immediately
        self.start_now_check = QCheckBox("Start downloading immediately")
        self.start_now_check.setChecked(True)
        options_layout.addRow("", self.start_now_check)

        layout.addWidget(options_group)

        # === Media Options (for video/audio sites) ===
        self.media_group = QGroupBox("Media Options (Video/Audio Sites)")
        media_layout = QFormLayout(self.media_group)

        self.download_type_combo = QComboBox()
        self.download_type_combo.addItems(["Video", "Audio"])
        self.download_type_combo.currentTextChanged.connect(self._on_type_changed)
        media_layout.addRow("Download Type:", self.download_type_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "Best Quality", "720p", "480p", "360p", "240p"
        ])
        media_layout.addRow("Video Quality:", self.quality_combo)

        self.audio_format_combo = QComboBox()
        self.audio_format_combo.addItems([
            "Best Quality", "MP3", "AAC", "FLAC", "Opus", "WAV"
        ])
        self.audio_format_combo.setEnabled(False)
        media_layout.addRow("Audio Format:", self.audio_format_combo)

        layout.addWidget(self.media_group)

        # === Buttons ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.add_btn = QPushButton("Add Download")
        self.add_btn.setDefault(True)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 24px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.add_btn.clicked.connect(self._add_download)
        btn_layout.addWidget(self.add_btn)

        layout.addLayout(btn_layout)

    def _on_url_changed(self, text: str):
        """Handle URL text changes."""
        if is_url(text.strip()):
            self.detect_btn.setEnabled(True)
            self.site_label.setText("Site: Click 'Detect' to analyze URL")
            self.site_label.setStyleSheet("color: #666; font-style: italic; padding: 4px;")
        else:
            self.detect_btn.setEnabled(False)
            self.site_label.setText("Site: Invalid URL")
            self.site_label.setStyleSheet("color: #E53935; font-style: italic; padding: 4px;")

    def _detect_url(self):
        """Auto-detect site and file information."""
        url = self.url_input.text().strip()
        if not is_url(url):
            return

        self.detect_btn.setEnabled(False)
        self.detect_btn.setText("Detecting...")
        self.site_label.setText("Site: Detecting...")
        self.site_label.setStyleSheet("color: #FF9800; font-style: italic; padding: 4px;")

        # Start background info fetch
        self._info_thread = InfoFetcherThread(self.router, url)
        self._info_thread.info_ready.connect(self._on_info_ready)
        self._info_thread.start()

    def _on_info_ready(self, info: dict):
        """Handle info fetch completion."""
        self.detect_btn.setEnabled(True)
        self.detect_btn.setText("Detect")

        if "error" in info:
            self.site_label.setText(f"Site: Detection failed - {info['error']}")
            self.site_label.setStyleSheet("color: #E53935; font-style: italic; padding: 4px;")
            return

        site = info.get("site", "Unknown")
        self.site_label.setText(f"Site: {site}")
        self.site_label.setStyleSheet("color: #4CAF50; font-weight: bold; padding: 4px;")

        if info.get("filename"):
            self.filename_input.setText(info["filename"])

        if info.get("file_size"):
            from ..utils.helpers import format_size
            self.size_label.setText(format_size(info["file_size"]))

        # Show/hide media options based on site
        is_media = site in ["YouTube/Media"]
        self.media_group.setVisible(True)  # Always visible but context-aware

    def _on_type_changed(self, text: str):
        """Handle download type change (video/audio)."""
        is_audio = text == "Audio"
        self.quality_combo.setEnabled(not is_audio)
        self.audio_format_combo.setEnabled(is_audio)

    def _browse_path(self):
        """Open folder browser dialog."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", self.path_input.text()
        )
        if path:
            self.path_input.setText(path)

    def _add_download(self):
        """Create and return the download item."""
        url = self.url_input.text().strip()
        if not is_url(url):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid URL.")
            return

        save_path = self.path_input.text().strip()
        if not save_path:
            save_path = self.default_path

        os.makedirs(save_path, exist_ok=True)

        # Create download item
        item = self.router.create_item(
            url=url,
            save_path=save_path,
        )

        # Override with user settings
        filename = self.filename_input.text().strip()
        if filename and filename != "unknown":
            item.filename = filename

        item.category = self.category_combo.currentData()
        item.num_segments = self.segments_spin.value()
        item.save_path = save_path

        # Media settings
        if self.download_type_combo.currentText() == "Audio":
            item.category = DownloadCategory.AUDIO
            item.is_media = True
            fmt = self.audio_format_combo.currentText()
            item.media_format = fmt if fmt != "Best Quality" else "bestaudio"
        else:
            if item.category != DownloadCategory.AUDIO:
                item.category = DownloadCategory.VIDEO
            item.is_media = True
            quality = self.quality_combo.currentText()
            quality_map = {
                "Best Quality": "best",
                "720p": "720p",
                "480p": "480p",
                "360p": "360p",
                "240p": "240p",
            }
            item.media_quality = quality_map.get(quality, "best")

        self.download_item = item
        self.accept()

    def get_download_item(self) -> DownloadItem:
        """Get the created download item."""
        return self.download_item

    def should_start_immediately(self) -> bool:
        """Check if download should start immediately."""
        return self.start_now_check.isChecked()
