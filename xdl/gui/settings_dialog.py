"""
Settings Dialog - configure download manager preferences.
"""

import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QPushButton,
    QFileDialog, QGroupBox, QCheckBox, QComboBox,
    QTabWidget, QWidget, QMessageBox
)
from PyQt5.QtCore import Qt


class SettingsDialog(QDialog):
    """Settings dialog for configuring the download manager."""

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 450)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # === General Tab ===
        general_widget = QWidget()
        general_layout = QFormLayout(general_widget)

        self.default_path_input = QLineEdit(
            self.settings.get("default_save_path", "")
        )
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.default_path_input)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self._browse_path("default_path_input"))
        path_layout.addWidget(browse_btn)
        general_layout.addRow("Default Save Path:", path_layout)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setValue(self.settings.get("max_concurrent", 3))
        general_layout.addRow("Max Concurrent Downloads:", self.concurrent_spin)

        self.segments_spin = QSpinBox()
        self.segments_spin.setRange(1, 32)
        self.segments_spin.setValue(self.settings.get("default_segments", 8))
        general_layout.addRow("Default Segments:", self.segments_spin)

        self.start_on_boot_check = QCheckBox("Start with system")
        self.start_on_boot_check.setChecked(self.settings.get("start_on_boot", False))
        general_layout.addRow("", self.start_on_boot_check)

        self.show_tray_check = QCheckBox("Show system tray icon")
        self.show_tray_check.setChecked(self.settings.get("show_tray_icon", True))
        general_layout.addRow("", self.show_tray_check)

        tabs.addTab(general_widget, "General")

        # === Connection Tab ===
        connection_widget = QWidget()
        connection_layout = QFormLayout(connection_widget)

        self.proxy_input = QLineEdit(self.settings.get("proxy", ""))
        self.proxy_input.setPlaceholderText("http://proxy:port or socks5://proxy:port")
        connection_layout.addRow("Proxy Server:", self.proxy_input)

        self.user_agent_input = QLineEdit(self.settings.get("user_agent", ""))
        self.user_agent_input.setPlaceholderText("Custom User-Agent string (leave empty for default)")
        connection_layout.addRow("User-Agent:", self.user_agent_input)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setValue(self.settings.get("connection_timeout", 60))
        self.timeout_spin.setSuffix(" seconds")
        connection_layout.addRow("Connection Timeout:", self.timeout_spin)

        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 20)
        self.retry_spin.setValue(self.settings.get("max_retries", 5))
        connection_layout.addRow("Max Retries:", self.retry_spin)

        self.speed_limit_spin = QSpinBox()
        self.speed_limit_spin.setRange(0, 100000)
        self.speed_limit_spin.setValue(self.settings.get("speed_limit_kb", 0))
        self.speed_limit_spin.setSuffix(" KB/s (0 = unlimited)")
        connection_layout.addRow("Speed Limit:", self.speed_limit_spin)

        tabs.addTab(connection_widget, "Connection")

        # === Monitoring Tab ===
        monitor_widget = QWidget()
        monitor_layout = QFormLayout(monitor_widget)

        self.clipboard_check = QCheckBox("Monitor clipboard for URLs")
        self.clipboard_check.setChecked(self.settings.get("monitor_clipboard", True))
        monitor_layout.addRow("", self.clipboard_check)

        self.auto_add_check = QCheckBox("Auto-add detected URLs to queue")
        self.auto_add_check.setChecked(self.settings.get("auto_add_urls", False))
        monitor_layout.addRow("", self.auto_add_check)

        self.clipboard_interval_spin = QSpinBox()
        self.clipboard_interval_spin.setRange(500, 5000)
        self.clipboard_interval_spin.setValue(self.settings.get("clipboard_interval_ms", 1000))
        self.clipboard_interval_spin.setSuffix(" ms")
        monitor_layout.addRow("Clipboard Check Interval:", self.clipboard_interval_spin)

        # File type filters
        self.video_check = QCheckBox("Monitor video URLs")
        self.video_check.setChecked(self.settings.get("monitor_video", True))
        monitor_layout.addRow("", self.video_check)

        self.audio_check = QCheckBox("Monitor audio URLs")
        self.audio_check.setChecked(self.settings.get("monitor_audio", True))
        monitor_layout.addRow("", self.audio_check)

        tabs.addTab(monitor_widget, "Monitoring")

        # === Categories Tab ===
        categories_widget = QWidget()
        categories_layout = QFormLayout(categories_widget)

        for cat_name, default_sub in [
            ("Video", "Video"),
            ("Audio", "Audio"),
            ("Document", "Documents"),
            ("Compressed", "Compressed"),
            ("Program", "Programs"),
            ("Image", "Images"),
        ]:
            sub_input = QLineEdit(
                self.settings.get(f"cat_{cat_name.lower()}_subfolder", default_sub)
            )
            setattr(self, f"cat_{cat_name.lower()}_input", sub_input)
            categories_layout.addRow(f"{cat_name} Subfolder:", sub_input)

        tabs.addTab(categories_widget, "Categories")

        # === Buttons ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 24px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _browse_path(self, target_attr: str):
        """Open folder browser."""
        input_widget = getattr(self, target_attr)
        path = QFileDialog.getExistingDirectory(
            self, "Select Folder", input_widget.text()
        )
        if path:
            input_widget.setText(path)

    def _reset_defaults(self):
        """Reset all settings to defaults."""
        self.default_path_input.setText(
            os.path.join(os.path.expanduser("~"), "Downloads", "Xdl")
        )
        self.concurrent_spin.setValue(3)
        self.segments_spin.setValue(8)
        self.start_on_boot_check.setChecked(False)
        self.show_tray_check.setChecked(True)
        self.proxy_input.clear()
        self.user_agent_input.clear()
        self.timeout_spin.setValue(60)
        self.retry_spin.setValue(5)
        self.speed_limit_spin.setValue(0)
        self.clipboard_check.setChecked(True)
        self.auto_add_check.setChecked(False)

    def _save_settings(self):
        """Collect and save settings."""
        self.settings.update({
            "default_save_path": self.default_path_input.text(),
            "max_concurrent": self.concurrent_spin.value(),
            "default_segments": self.segments_spin.value(),
            "start_on_boot": self.start_on_boot_check.isChecked(),
            "show_tray_icon": self.show_tray_check.isChecked(),
            "proxy": self.proxy_input.text(),
            "user_agent": self.user_agent_input.text(),
            "connection_timeout": self.timeout_spin.value(),
            "max_retries": self.retry_spin.value(),
            "speed_limit_kb": self.speed_limit_spin.value(),
            "monitor_clipboard": self.clipboard_check.isChecked(),
            "auto_add_urls": self.auto_add_check.isChecked(),
            "clipboard_interval_ms": self.clipboard_interval_spin.value(),
            "monitor_video": self.video_check.isChecked(),
            "monitor_audio": self.audio_check.isChecked(),
        })
        self.accept()

    def get_settings(self) -> dict:
        """Get the updated settings."""
        return self.settings
