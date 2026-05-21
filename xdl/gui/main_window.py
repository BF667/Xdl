"""
Main Window - IDM-like interface for the download manager.
Features: download list, categories, toolbar, status bar,
and all download controls.
"""

import os
import json
import time
import webbrowser
from typing import Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QToolBar, QAction, QStatusBar, QProgressBar, QMenu,
    QHeaderView, QAbstractItemView, QMessageBox, QInputDialog,
    QFileDialog, QLabel, QPushButton, QSystemTrayIcon, QApplication,
    QStyle, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette

from ..core.models import DownloadItem, DownloadStatus, DownloadCategory
from ..core.queue_manager import QueueManager
from ..downloaders.router import DownloadRouter
from ..utils.helpers import format_size, format_speed, format_time, is_url
from ..utils.clipboard_monitor import ClipboardMonitor
from .add_download_dialog import AddDownloadDialog
from .settings_dialog import SettingsDialog
from .about_dialog import AboutDialog
from .. import __version__, __app_name__


# Color scheme
COLORS = {
    "primary": "#2196F3",
    "primary_dark": "#1565C0",
    "success": "#4CAF50",
    "warning": "#FF9800",
    "error": "#F44336",
    "info": "#00BCD4",
    "bg_dark": "#263238",
    "bg_medium": "#37474F",
    "bg_light": "#ECEFF1",
    "text_primary": "#212121",
    "text_secondary": "#757575",
    "downloading": "#2196F3",
    "completed": "#4CAF50",
    "paused": "#FF9800",
    "error": "#F44336",
    "queued": "#9E9E9E",
}


class ProgressDelegate(QProgressBar):
    """Custom progress bar widget for table cells."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(True)
        self.setFormat("%p%")
        self.setFixedHeight(22)
        self.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: #f0f0f0;
                text-align: center;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 2px;
            }
        """)

    def set_status(self, status: DownloadStatus):
        """Update color based on download status."""
        color_map = {
            DownloadStatus.DOWNLOADING: COLORS["downloading"],
            DownloadStatus.COMPLETED: COLORS["completed"],
            DownloadStatus.PAUSED: COLORS["paused"],
            DownloadStatus.ERROR: COLORS["error"],
            DownloadStatus.QUEUED: COLORS["queued"],
        }
        color = color_map.get(status, COLORS["primary"])
        self.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: #f0f0f0;
                text-align: center;
                font-size: 11px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)


class MainWindow(QMainWindow):
    """Main application window with IDM-like interface."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.setMinimumSize(1000, 650)

        # Initialize core components
        self.router = DownloadRouter()
        self.queue_manager = QueueManager(
            engine=self.router._fallback._engine if hasattr(self.router._fallback, '_engine') else None,
            max_concurrent=3
        )
        self.clipboard_monitor = ClipboardMonitor()
        self.settings = self._load_settings()

        # Download storage
        self._downloads: dict = {}  # id -> DownloadItem
        self._current_filter = None  # Category filter

        # Setup UI
        self.setup_ui()
        self.setup_toolbar()
        self.setup_statusbar()
        self.setup_tray_icon()
        self.setup_connections()
        self.setup_timers()

        # Apply saved settings
        self._apply_settings()

    def setup_ui(self):
        """Set up the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Splitter for categories and download list
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # === Left Panel: Categories ===
        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderLabel("Categories")
        self.category_tree.setFixedWidth(200)
        self.category_tree.setIndentation(10)
        self.category_tree.setAnimated(True)
        self.category_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #263238;
                color: #ECEFF1;
                border: none;
                font-size: 13px;
                padding: 4px;
            }
            QTreeWidget::item {
                padding: 8px 4px;
                border-bottom: 1px solid #37474F;
            }
            QTreeWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
            QTreeWidget::item:hover {
                background-color: #37474F;
            }
            QHeaderView::section {
                background-color: #1a2327;
                color: #ECEFF1;
                padding: 8px;
                border: none;
                font-weight: bold;
                font-size: 13px;
            }
        """)

        # Add category items
        self._cat_all = QTreeWidgetItem(self.category_tree, ["All Downloads", "📥"])
        self._cat_video = QTreeWidgetItem(self.category_tree, ["Video", "🎬"])
        self._cat_audio = QTreeWidgetItem(self.category_tree, ["Audio", "🎵"])
        self._cat_document = QTreeWidgetItem(self.category_tree, ["Documents", "📄"])
        self._cat_compressed = QTreeWidgetItem(self.category_tree, ["Compressed", "📦"])
        self._cat_program = QTreeWidgetItem(self.category_tree, ["Programs", "💿"])
        self._cat_image = QTreeWidgetItem(self.category_tree, ["Images", "🖼"])
        self._cat_other = QTreeWidgetItem(self.category_tree, ["Other", "📁"])
        self._cat_completed = QTreeWidgetItem(self.category_tree, ["Completed", "✅"])
        self._cat_queued = QTreeWidgetItem(self.category_tree, ["Queue", "⏳"])

        self.category_tree.expandAll()
        self._cat_all.setSelected(True)

        splitter.addWidget(self.category_tree)

        # === Right Panel: Download List ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Download table
        self.download_table = QTableWidget()
        self.download_table.setColumnCount(9)
        self.download_table.setHorizontalHeaderLabels([
            "Filename", "Size", "Progress", "Speed",
            "ETA", "Status", "Site", "Category", "Date"
        ])
        self.download_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.download_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.download_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.download_table.setAlternatingRowColors(True)
        self.download_table.setShowGrid(False)
        self.download_table.verticalHeader().setVisible(False)
        self.download_table.setContextMenuPolicy(Qt.CustomContextMenu)

        # Column widths
        header = self.download_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Filename
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Size
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Progress
        self.download_table.setColumnWidth(2, 150)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Speed
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # ETA
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Site
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Category
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Date

        self.download_table.setStyleSheet("""
            QTableWidget {
                background-color: #FAFAFA;
                alternate-background-color: #F5F5F5;
                border: none;
                font-size: 12px;
                gridline-color: #E0E0E0;
            }
            QTableWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #EEEEEE;
            }
            QTableWidget::item:selected {
                background-color: #E3F2FD;
                color: #1565C0;
            }
            QHeaderView::section {
                background-color: #ECEFF1;
                padding: 6px 8px;
                border: none;
                border-bottom: 2px solid #2196F3;
                font-weight: bold;
                font-size: 12px;
                color: #37474F;
            }
        """)

        right_layout.addWidget(self.download_table)
        splitter.addWidget(right_widget)

        # Set splitter sizes
        splitter.setSizes([200, 800])

        # Speed display at bottom of right panel
        self.speed_panel = QLabel("Total Speed: 0 B/s | Active: 0 | Queue: 0")
        self.speed_panel.setStyleSheet("""
            QLabel {
                background-color: #263238;
                color: #ECEFF1;
                padding: 6px 12px;
                font-size: 12px;
            }
        """)
        right_layout.addWidget(self.speed_panel)

    def setup_toolbar(self):
        """Set up the main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #37474F;
                border: none;
                padding: 4px;
                spacing: 4px;
            }
            QToolBar QToolButton {
                background-color: transparent;
                color: #ECEFF1;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QToolBar QToolButton:hover {
                background-color: #2196F3;
            }
            QToolBar QToolButton:pressed {
                background-color: #1565C0;
            }
            QToolBar::separator {
                width: 1px;
                background-color: #546E7A;
                margin: 4px 8px;
            }
        """)
        self.addToolBar(toolbar)

        # Add Download
        self.action_add = QAction("➕ Add URL", self)
        self.action_add.setToolTip("Add a new download (Ctrl+N)")
        self.action_add.setShortcut("Ctrl+N")
        self.action_add.triggered.connect(self._on_add_download)
        toolbar.addAction(self.action_add)

        toolbar.addSeparator()

        # Resume
        self.action_resume = QAction("▶ Resume", self)
        self.action_resume.setToolTip("Resume selected download")
        self.action_resume.triggered.connect(self._on_resume)
        toolbar.addAction(self.action_resume)

        # Pause
        self.action_pause = QAction("⏸ Pause", self)
        self.action_pause.setToolTip("Pause selected download")
        self.action_pause.triggered.connect(self._on_pause)
        toolbar.addAction(self.action_pause)

        # Cancel
        self.action_cancel = QAction("⏹ Cancel", self)
        self.action_cancel.setToolTip("Cancel selected download")
        self.action_cancel.triggered.connect(self._on_cancel)
        toolbar.addAction(self.action_cancel)

        # Delete
        self.action_delete = QAction("🗑 Delete", self)
        self.action_delete.setToolTip("Remove selected download from list")
        self.action_delete.triggered.connect(self._on_delete)
        toolbar.addAction(self.action_delete)

        toolbar.addSeparator()

        # Resume All
        self.action_resume_all = QAction("⏩ Resume All", self)
        self.action_resume_all.setToolTip("Resume all paused downloads")
        self.action_resume_all.triggered.connect(self._on_resume_all)
        toolbar.addAction(self.action_resume_all)

        # Pause All
        self.action_pause_all = QAction("⏸ Pause All", self)
        self.action_pause_all.setToolTip("Pause all active downloads")
        self.action_pause_all.triggered.connect(self._on_pause_all)
        toolbar.addAction(self.action_pause_all)

        toolbar.addSeparator()

        # Schedule
        self.action_schedule = QAction("⏰ Schedule", self)
        self.action_schedule.setToolTip("Schedule download for later")
        self.action_schedule.triggered.connect(self._on_schedule)
        toolbar.addAction(self.action_schedule)

        # Batch Download
        self.action_batch = QAction("📋 Batch", self)
        self.action_batch.setToolTip("Add multiple URLs at once")
        self.action_batch.triggered.connect(self._on_batch_download)
        toolbar.addAction(self.action_batch)

        toolbar.addSeparator()

        # Open File
        self.action_open_file = QAction("📂 Open File", self)
        self.action_open_file.setToolTip("Open the downloaded file")
        self.action_open_file.triggered.connect(self._on_open_file)
        toolbar.addAction(self.action_open_file)

        # Open Folder
        self.action_open_folder = QAction("📁 Open Folder", self)
        self.action_open_folder.setToolTip("Open the download folder")
        self.action_open_folder.triggered.connect(self._on_open_folder)
        toolbar.addAction(self.action_open_folder)

        toolbar.addSeparator()

        # Settings
        self.action_settings = QAction("⚙ Settings", self)
        self.action_settings.setToolTip("Configure download settings")
        self.action_settings.triggered.connect(self._on_settings)
        toolbar.addAction(self.action_settings)

        # About
        self.action_about = QAction("ℹ About", self)
        self.action_about.triggered.connect(self._on_about)
        toolbar.addAction(self.action_about)

    def setup_statusbar(self):
        """Set up the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.setStyleSheet("""
            QStatusBar {
                background-color: #263238;
                color: #ECEFF1;
                font-size: 12px;
                padding: 2px;
            }
        """)
        self.statusbar.showMessage("Ready. Add a URL to start downloading!")

    def setup_tray_icon(self):
        """Set up system tray icon."""
        try:
            self.tray_icon = QSystemTrayIcon(self)
            # Use application icon
            icon = self.style().standardIcon(QStyle.SP_DriveHDIcon)
            self.tray_icon.setIcon(icon)
            self.tray_icon.setToolTip(__app_name__)

            tray_menu = QMenu()
            tray_menu.addAction("Show", self.show)
            tray_menu.addAction("Add Download", self._on_add_download)
            tray_menu.addSeparator()
            tray_menu.addAction("Resume All", self._on_resume_all)
            tray_menu.addAction("Pause All", self._on_pause_all)
            tray_menu.addSeparator()
            tray_menu.addAction("Quit", self.close)

            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.show()
        except Exception:
            pass

    def setup_connections(self):
        """Set up signal-slot connections."""
        # Category selection
        self.category_tree.itemClicked.connect(self._on_category_changed)

        # Table context menu
        self.download_table.customContextMenuRequested.connect(self._show_context_menu)
        self.download_table.itemDoubleClicked.connect(self._on_double_click)

        # Clipboard monitor
        self.clipboard_monitor.on_url_detected = self._on_clipboard_url

        # Router callbacks
        self.router.on_progress = self._on_progress_update
        self.router.on_complete = self._on_download_complete
        self.router.on_error = self._on_download_error

    def setup_timers(self):
        """Set up periodic update timers."""
        # UI refresh timer
        self._ui_timer = QTimer()
        self._ui_timer.timeout.connect(self._refresh_ui)
        self._ui_timer.start(500)  # Refresh every 500ms

        # Stats timer
        self._stats_timer = QTimer()
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start(1000)

    # === Download Actions ===

    def _on_add_download(self, url: str = ""):
        """Open the Add Download dialog."""
        dialog = AddDownloadDialog(
            router=self.router,
            default_path=self.settings.get("default_save_path", ""),
            clipboard_url=url,
            parent=self
        )
        if dialog.exec_() == AddDownloadDialog.Accepted:
            item = dialog.get_download_item()
            if item:
                self._add_item(item, dialog.should_start_immediately())

    def _add_item(self, item: DownloadItem, start_immediately: bool = True):
        """Add a download item to the list and optionally start it."""
        self._downloads[item.id] = item
        self._add_table_row(item)

        if start_immediately:
            self.router.start_download(item)

        self._update_stats()
        self.statusbar.showMessage(
            f"Added: {item.filename} ({item.site_name})"
        )

    def _add_table_row(self, item: DownloadItem):
        """Add a row to the download table for an item."""
        row = self.download_table.rowCount()
        self.download_table.insertRow(row)

        # Filename
        name_item = QTableWidgetItem(item.filename)
        name_item.setData(Qt.UserRole, item.id)
        self.download_table.setItem(row, 0, name_item)

        # Size
        size_item = QTableWidgetItem(format_size(item.file_size) if item.file_size else "Unknown")
        size_item.setTextAlignment(Qt.AlignCenter)
        self.download_table.setItem(row, 1, size_item)

        # Progress bar
        progress = ProgressDelegate()
        progress.setValue(int(item.progress))
        progress.set_status(item.status)
        self.download_table.setCellWidget(row, 2, progress)

        # Speed
        speed_item = QTableWidgetItem(format_speed(item.speed))
        speed_item.setTextAlignment(Qt.AlignCenter)
        self.download_table.setItem(row, 3, speed_item)

        # ETA
        eta_item = QTableWidgetItem(format_time(item.eta))
        eta_item.setTextAlignment(Qt.AlignCenter)
        self.download_table.setItem(row, 4, eta_item)

        # Status
        status_item = QTableWidgetItem(item.status.value.title())
        status_item.setTextAlignment(Qt.AlignCenter)
        self._color_status(status_item, item.status)
        self.download_table.setItem(row, 5, status_item)

        # Site
        site_item = QTableWidgetItem(item.site_name)
        site_item.setTextAlignment(Qt.AlignCenter)
        self.download_table.setItem(row, 6, site_item)

        # Category
        cat_item = QTableWidgetItem(item.category.value)
        cat_item.setTextAlignment(Qt.AlignCenter)
        self.download_table.setItem(row, 7, cat_item)

        # Date
        date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(item.created_at))
        date_item = QTableWidgetItem(date_str)
        date_item.setTextAlignment(Qt.AlignCenter)
        self.download_table.setItem(row, 8, date_item)

    def _update_table_row(self, item: DownloadItem):
        """Update an existing table row with current item data."""
        for row in range(self.download_table.rowCount()):
            name_item = self.download_table.item(row, 0)
            if name_item and name_item.data(Qt.UserRole) == item.id:
                # Size
                size_item = self.download_table.item(row, 1)
                if size_item and item.file_size > 0:
                    size_item.setText(format_size(item.file_size))

                # Progress
                progress = self.download_table.cellWidget(row, 2)
                if progress:
                    progress.setValue(int(item.progress))
                    progress.set_status(item.status)

                # Speed
                speed_item = self.download_table.item(row, 3)
                if speed_item:
                    speed_item.setText(format_speed(item.speed))

                # ETA
                eta_item = self.download_table.item(row, 4)
                if eta_item:
                    eta_item.setText(format_time(item.eta))

                # Status
                status_item = self.download_table.item(row, 5)
                if status_item:
                    status_item.setText(item.status.value.title())
                    self._color_status(status_item, item.status)

                # Site
                site_item = self.download_table.item(row, 6)
                if site_item and item.site_name:
                    site_item.setText(item.site_name)

                # Category
                cat_item = self.download_table.item(row, 7)
                if cat_item:
                    cat_item.setText(item.category.value)

                break

    def _color_status(self, item: QTableWidgetItem, status: DownloadStatus):
        """Color-code a status item."""
        color_map = {
            DownloadStatus.DOWNLOADING: QColor(COLORS["downloading"]),
            DownloadStatus.COMPLETED: QColor(COLORS["completed"]),
            DownloadStatus.PAUSED: QColor(COLORS["paused"]),
            DownloadStatus.ERROR: QColor(COLORS["error"]),
            DownloadStatus.QUEUED: QColor(COLORS["queued"]),
            DownloadStatus.PENDING: QColor(COLORS["info"]),
        }
        color = color_map.get(status, QColor("#333"))
        item.setForeground(color)

    def _get_selected_item(self) -> Optional[DownloadItem]:
        """Get the currently selected download item."""
        rows = self.download_table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            name_item = self.download_table.item(row, 0)
            if name_item:
                item_id = name_item.data(Qt.UserRole)
                return self._downloads.get(item_id)
        return None

    def _on_resume(self):
        """Resume the selected download."""
        item = self._get_selected_item()
        if item and item.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
            item.status = DownloadStatus.PENDING
            item.error_message = ""
            self.router.resume_download(item)
            self.statusbar.showMessage(f"Resuming: {item.filename}")
            self._update_table_row(item)

    def _on_pause(self):
        """Pause the selected download."""
        item = self._get_selected_item()
        if item and item.status == DownloadStatus.DOWNLOADING:
            self.router.pause_download(item.id)
            item.status = DownloadStatus.PAUSED
            self._update_table_row(item)
            self.statusbar.showMessage(f"Paused: {item.filename}")

    def _on_cancel(self):
        """Cancel the selected download."""
        item = self._get_selected_item()
        if item and item.status in (DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED, DownloadStatus.PAUSED):
            self.router.cancel_download(item.id)
            item.status = DownloadStatus.CANCELLED
            item.speed = 0.0
            self._update_table_row(item)
            self.statusbar.showMessage(f"Cancelled: {item.filename}")

    def _on_delete(self):
        """Remove the selected download from the list."""
        item = self._get_selected_item()
        if not item:
            return

        if item.status == DownloadStatus.DOWNLOADING:
            self.router.cancel_download(item.id)

        # Remove from table
        for row in range(self.download_table.rowCount()):
            name_item = self.download_table.item(row, 0)
            if name_item and name_item.data(Qt.UserRole) == item.id:
                self.download_table.removeRow(row)
                break

        # Remove from storage
        self._downloads.pop(item.id, None)
        self.statusbar.showMessage(f"Removed: {item.filename}")
        self._update_stats()

    def _on_resume_all(self):
        """Resume all paused/errored downloads."""
        for item in self._downloads.values():
            if item.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
                item.status = DownloadStatus.PENDING
                item.error_message = ""
                self.router.resume_download(item)
                self._update_table_row(item)
        self.statusbar.showMessage("Resumed all downloads")

    def _on_pause_all(self):
        """Pause all active downloads."""
        for item in self._downloads.values():
            if item.status == DownloadStatus.DOWNLOADING:
                self.router.pause_download(item.id)
                item.status = DownloadStatus.PAUSED
                self._update_table_row(item)
        self.statusbar.showMessage("Paused all downloads")

    def _on_schedule(self):
        """Schedule a download for later."""
        item = self._get_selected_item()
        if item:
            time_str, ok = QInputDialog.getText(
                self, "Schedule Download",
                "Enter time to start (HH:MM format, e.g., 22:30):"
            )
            if ok and time_str:
                try:
                    h, m = map(int, time_str.split(":"))
                    if 0 <= h < 24 and 0 <= m < 60:
                        item.status = DownloadStatus.SCHEDULING
                        self._update_table_row(item)
                        self.statusbar.showMessage(
                            f"Scheduled: {item.filename} at {time_str}"
                        )
                    else:
                        QMessageBox.warning(self, "Invalid Time", "Please enter valid time (00:00 - 23:59)")
                except ValueError:
                    QMessageBox.warning(self, "Invalid Format", "Please use HH:MM format")

    def _on_batch_download(self):
        """Add multiple URLs at once."""
        text, ok = QInputDialog.getMultiLineText(
            self, "Batch Download",
            "Enter URLs (one per line):",
            ""
        )
        if ok and text.strip():
            urls = [u.strip() for u in text.strip().split("\n") if is_url(u.strip())]
            for url in urls:
                item = self.router.create_item(
                    url=url,
                    save_path=self.settings.get("default_save_path", ""),
                )
                self._add_item(item)
            self.statusbar.showMessage(f"Added {len(urls)} downloads")

    def _on_open_file(self):
        """Open the downloaded file."""
        item = self._get_selected_item()
        if item and item.status == DownloadStatus.COMPLETED:
            filepath = os.path.join(item.save_path, item.filename)
            if os.path.exists(filepath):
                webbrowser.open(f"file://{filepath}")
            else:
                QMessageBox.information(self, "File Not Found",
                                        f"File not found: {filepath}")

    def _on_open_folder(self):
        """Open the download folder."""
        item = self._get_selected_item()
        if item:
            path = item.save_path
        else:
            path = self.settings.get("default_save_path", "")

        if os.path.isdir(path):
            webbrowser.open(f"file://{path}")

    def _on_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_() == SettingsDialog.Accepted:
            self.settings = dialog.get_settings()
            self._save_settings()
            self._apply_settings()
            self.statusbar.showMessage("Settings saved")

    def _on_about(self):
        """Open about dialog."""
        dialog = AboutDialog(self)
        dialog.exec_()

    def _on_double_click(self, item: QTableWidgetItem):
        """Handle double-click on a download item."""
        dl_item = self._get_selected_item()
        if dl_item:
            if dl_item.status == DownloadStatus.COMPLETED:
                self._on_open_file()
            elif dl_item.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
                self._on_resume()
            elif dl_item.status == DownloadStatus.DOWNLOADING:
                self._on_pause()

    def _on_category_changed(self, item: QTreeWidgetItem, column: int):
        """Filter downloads by selected category."""
        cat_map = {
            self._cat_all: None,
            self._cat_video: DownloadCategory.VIDEO,
            self._cat_audio: DownloadCategory.AUDIO,
            self._cat_document: DownloadCategory.DOCUMENT,
            self._cat_compressed: DownloadCategory.COMPRESSED,
            self._cat_program: DownloadCategory.PROGRAM,
            self._cat_image: DownloadCategory.IMAGE,
            self._cat_other: DownloadCategory.OTHER,
            self._cat_completed: "completed",
            self._cat_queued: "queued",
        }

        self._current_filter = cat_map.get(item)
        self._apply_filter()

    def _apply_filter(self):
        """Apply the current category filter to the download list."""
        for row in range(self.download_table.rowCount()):
            name_item = self.download_table.item(row, 0)
            if not name_item:
                continue

            item_id = name_item.data(Qt.UserRole)
            item = self._downloads.get(item_id)
            if not item:
                continue

            visible = True
            if self._current_filter is None:
                visible = True
            elif self._current_filter == "completed":
                visible = item.status == DownloadStatus.COMPLETED
            elif self._current_filter == "queued":
                visible = item.status in (DownloadStatus.QUEUED, DownloadStatus.PENDING, DownloadStatus.SCHEDULING)
            elif isinstance(self._current_filter, DownloadCategory):
                visible = item.category == self._current_filter

            self.download_table.setRowHidden(row, not visible)

    def _show_context_menu(self, pos):
        """Show right-click context menu."""
        item = self._get_selected_item()
        if not item:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ddd;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background-color: #E3F2FD;
                color: #1565C0;
            }
        """)

        if item.status in (DownloadStatus.PAUSED, DownloadStatus.ERROR):
            menu.addAction("▶ Resume", self._on_resume)
        elif item.status == DownloadStatus.DOWNLOADING:
            menu.addAction("⏸ Pause", self._on_pause)

        if item.status != DownloadStatus.COMPLETED:
            menu.addAction("⏹ Cancel", self._on_cancel)

        menu.addAction("🗑 Delete from List", self._on_delete)
        menu.addSeparator()

        if item.status == DownloadStatus.COMPLETED:
            menu.addAction("📂 Open File", self._on_open_file)

        menu.addAction("📁 Open Folder", self._on_open_folder)
        menu.addSeparator()
        menu.addAction("📋 Copy URL", lambda: self._copy_url(item))
        menu.addAction("🔄 Refresh Info", lambda: self._refresh_info(item))

        menu.exec_(self.download_table.viewport().mapToGlobal(pos))

    def _copy_url(self, item: DownloadItem):
        """Copy download URL to clipboard."""
        try:
            import pyperclip
            pyperclip.copy(item.url)
            self.statusbar.showMessage("URL copied to clipboard")
        except Exception:
            pass

    def _refresh_info(self, item: DownloadItem):
        """Refresh item info from the source."""
        info = self.router.get_info(item.url)
        if info:
            if info.get("filename") and item.filename == "unknown":
                item.filename = info["filename"]
            if info.get("file_size") and not item.file_size:
                item.file_size = info["file_size"]
            self._update_table_row(item)
            self.statusbar.showMessage(f"Info refreshed: {item.filename}")

    # === Callback Handlers ===

    def _on_progress_update(self, item: DownloadItem):
        """Handle download progress update."""
        # Updates are handled by the UI refresh timer
        pass

    def _on_download_complete(self, item: DownloadItem):
        """Handle download completion."""
        self._update_table_row(item)
        self.statusbar.showMessage(f"Download complete: {item.filename}")
        self._update_stats()

        # Show notification
        try:
            if self.tray_icon:
                self.tray_icon.showMessage(
                    "Download Complete",
                    f"{item.filename}\nSize: {format_size(item.file_size)}",
                    QSystemTrayIcon.Information,
                    3000
                )
        except Exception:
            pass

    def _on_download_error(self, item: DownloadItem):
        """Handle download error."""
        self._update_table_row(item)
        self.statusbar.showMessage(
            f"Download error: {item.filename} - {item.error_message}"
        )
        self._update_stats()

    def _on_clipboard_url(self, url: str):
        """Handle URL detected in clipboard."""
        if self.settings.get("auto_add_urls", False):
            item = self.router.create_item(
                url=url,
                save_path=self.settings.get("default_save_path", ""),
            )
            self._add_item(item)
        else:
            self.statusbar.showMessage(f"URL detected: {url}")
            # Highlight the Add button or show a notification
            try:
                if self.tray_icon:
                    self.tray_icon.showMessage(
                        "URL Detected",
                        f"Click to add download: {url[:50]}...",
                        QSystemTrayIcon.Information,
                        3000
                    )
            except Exception:
                pass

    # === UI Updates ===

    def _refresh_ui(self):
        """Periodic UI refresh."""
        for item in self._downloads.values():
            if item.status == DownloadStatus.DOWNLOADING:
                self._update_table_row(item)

    def _update_stats(self):
        """Update download statistics display."""
        active = sum(1 for i in self._downloads.values() if i.status == DownloadStatus.DOWNLOADING)
        queued = sum(1 for i in self._downloads.values() if i.status in (DownloadStatus.QUEUED, DownloadStatus.PENDING))
        completed = sum(1 for i in self._downloads.values() if i.status == DownloadStatus.COMPLETED)
        total_speed = sum(i.speed for i in self._downloads.values() if i.status == DownloadStatus.DOWNLOADING)

        self.speed_panel.setText(
            f"Total Speed: {format_speed(total_speed)} | "
            f"Active: {active} | Queue: {queued} | Completed: {completed}"
        )

        # Update category counts
        counts = {}
        for item in self._downloads.values():
            cat = item.category.value
            counts[cat] = counts.get(cat, 0) + 1

        for cat_item, cat_key in [
            (self._cat_video, "Video"),
            (self._cat_audio, "Audio"),
            (self._cat_document, "Document"),
            (self._cat_compressed, "Compressed"),
            (self._cat_program, "Program"),
            (self._cat_image, "Image"),
            (self._cat_other, "Other"),
        ]:
            count = counts.get(cat_key, 0)
            cat_item.setText(0, f"{cat_key} ({count})" if count else cat_key)

        self._cat_all.setText(0, f"All Downloads ({len(self._downloads)})")
        self._cat_completed.setText(0, f"Completed ({completed})")
        self._cat_queued.setText(0, f"Queue ({queued})")

    # === Settings ===

    def _load_settings(self) -> dict:
        """Load settings from file."""
        settings_path = os.path.join(
            os.path.expanduser("~"), ".xdl", "settings.json"
        )
        try:
            if os.path.exists(settings_path):
                with open(settings_path) as f:
                    return json.load(f)
        except Exception:
            pass

        # Defaults
        return {
            "default_save_path": os.path.join(
                os.path.expanduser("~"), "Downloads", "Xdl"
            ),
            "max_concurrent": 3,
            "default_segments": 8,
            "start_on_boot": False,
            "show_tray_icon": True,
            "proxy": "",
            "user_agent": "",
            "connection_timeout": 60,
            "max_retries": 5,
            "speed_limit_kb": 0,
            "monitor_clipboard": True,
            "auto_add_urls": False,
            "clipboard_interval_ms": 1000,
            "monitor_video": True,
            "monitor_audio": True,
        }

    def _save_settings(self):
        """Save settings to file."""
        settings_dir = os.path.join(os.path.expanduser("~"), ".xdl")
        os.makedirs(settings_dir, exist_ok=True)
        settings_path = os.path.join(settings_dir, "settings.json")
        try:
            with open(settings_path, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def _apply_settings(self):
        """Apply current settings to the application."""
        # Update router/engine settings
        if self.settings.get("proxy"):
            for downloader in [self.router._fallback]:
                if hasattr(downloader, '_engine'):
                    downloader._engine.proxy = self.settings["proxy"]

        if self.settings.get("monitor_clipboard"):
            self.clipboard_monitor.start()
        else:
            self.clipboard_monitor.stop()

        if self.settings.get("clipboard_interval_ms"):
            self.clipboard_monitor.check_interval = self.settings["clipboard_interval_ms"] / 1000.0

    def closeEvent(self, event):
        """Handle window close event."""
        # Check for active downloads
        active = sum(1 for i in self._downloads.values() if i.status == DownloadStatus.DOWNLOADING)
        if active > 0:
            reply = QMessageBox.question(
                self, "Active Downloads",
                f"You have {active} active downloads. Minimize to tray instead?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                event.ignore()
                self.hide()
                return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return

        # Stop clipboard monitor
        self.clipboard_monitor.stop()

        # Save settings
        self._save_settings()

        event.accept()
