#!/usr/bin/env python3
"""
Xdl Download Manager - Main Entry Point
An open-source alternative to Internet Download Manager (IDM)

Usage:
    python main.py              # Launch GUI
    python main.py --cli URL    # Download from command line
    python main.py --info URL   # Get URL info without downloading
"""

import sys
import os
import argparse


def check_dependencies():
    """Check and report missing dependencies."""
    missing = []
    try:
        import PyQt5
    except ImportError:
        missing.append("PyQt5")

    try:
        import yt_dlp
    except ImportError:
        missing.append("yt-dlp")

    try:
        import requests
    except ImportError:
        missing.append("requests")

    try:
        import bs4
    except ImportError:
        missing.append("beautifulsoup4")

    try:
        import tqdm
    except ImportError:
        missing.append("tqdm")

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        return False
    return True


def launch_gui():
    """Launch the graphical user interface."""
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt
    from xdl.gui.main_window import MainWindow
    from xdl import __app_name__, __version__

    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")

    # Apply global stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #FAFAFA;
        }
        QToolTip {
            background-color: #263238;
            color: white;
            border: 1px solid #546E7A;
            padding: 4px;
            font-size: 12px;
        }
        QScrollBar:vertical {
            background: #ECEFF1;
            width: 10px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #90A4AE;
            min-height: 30px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover {
            background: #78909C;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollBar:horizontal {
            background: #ECEFF1;
            height: 10px;
            margin: 0;
        }
        QScrollBar::handle:horizontal {
            background: #90A4AE;
            min-width: 30px;
            border-radius: 5px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #78909C;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0;
        }
    """)

    window = MainWindow()
    window.show()

    # Check for URL argument
    if len(sys.argv) > 1:
        url = sys.argv[1]
        if url.startswith(("http://", "https://")):
            window._on_add_download(url)

    sys.exit(app.exec_())


def cli_download(url: str, output: str = "", format_type: str = "",
                 quality: str = "", audio_only: bool = False):
    """Download from command line."""
    from xdl.downloaders.router import DownloadRouter
    from xdl.core.models import DownloadItem, DownloadCategory
    from xdl.utils.helpers import format_size

    router = DownloadRouter()
    print(f"\n{'='*60}")
    print(f"  Xdl Download Manager - CLI Mode")
    print(f"{'='*60}\n")

    # Get info
    print(f"Detecting: {url}")
    info = router.get_info(url)
    site = router.detect_site(url)
    print(f"Site: {site}")

    if info.get("title"):
        print(f"Title: {info['title']}")
    if info.get("filename"):
        print(f"Filename: {info['filename']}")
    if info.get("file_size"):
        print(f"Size: {format_size(info['file_size'])}")

    # Create download item
    save_path = output or os.path.join(os.path.expanduser("~"), "Downloads", "Xdl")
    os.makedirs(save_path, exist_ok=True)

    item = router.create_item(url=url, save_path=save_path)

    if audio_only:
        item.media_format = format_type or "mp3"
        item.category = DownloadCategory.AUDIO
    elif format_type:
        item.media_quality = quality or "best"

    print(f"\nStarting download: {item.filename}")
    print(f"Save to: {item.save_path}")
    print(f"Category: {item.category.value}\n")

    # Download with progress
    import time
    import threading

    stop_event = threading.Event()
    last_update = [time.time()]

    def progress_callback(dl_item):
        now = time.time()
        if now - last_update[0] >= 0.5:
            from xdl.utils.helpers import format_speed, format_time
            last_update[0] = now
            bar_len = 40
            filled = int(bar_len * dl_item.progress / 100)
            bar = '█' * filled + '░' * (bar_len - filled)
            print(
                f"\r  [{bar}] {dl_item.progress:.1f}% | "
                f"{format_speed(dl_item.speed)} | "
                f"ETA: {format_time(dl_item.eta)}",
                end='', flush=True
            )

    downloader = router.get_downloader(url)
    downloader.on_progress = progress_callback

    try:
        thread = downloader.start(item)
        thread.join()
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user.")
        downloader.stop(item.id)
        return

    if item.status == DownloadStatus.COMPLETED:
        print(f"\n\n✅ Download complete: {os.path.join(item.save_path, item.filename)}")
    elif item.status == DownloadStatus.ERROR:
        print(f"\n\n❌ Download failed: {item.error_message}")
    else:
        print(f"\n\n⚠ Download status: {item.status.value}")


def show_info(url: str):
    """Show URL information without downloading."""
    from xdl.downloaders.router import DownloadRouter
    from xdl.utils.helpers import format_size

    router = DownloadRouter()
    site = router.detect_site(url)
    info = router.get_info(url)

    print(f"\n{'='*50}")
    print(f"  URL Information")
    print(f"{'='*50}")
    print(f"  URL:    {url}")
    print(f"  Site:   {site}")

    for key, value in info.items():
        if key == "error":
            print(f"  Error:  {value}")
        elif key not in ("url",):
            display_val = format_size(value) if "size" in key.lower() and isinstance(value, (int, float)) else value
            print(f"  {key.replace('_', ' ').title()}: {display_val}")

    print(f"{'='*50}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Xdl Download Manager - Open-source IDM Alternative",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          Launch GUI
  python main.py --cli URL                Download from URL
  python main.py --cli URL -a             Download as audio (MP3)
  python main_dl.py --cli URL -f mp3      Download as MP3
  python main.py --cli URL -o /path/to    Save to specific folder
  python main.py --info URL               Show URL information
        """
    )

    parser.add_argument("--cli", metavar="URL", help="Download URL from command line")
    parser.add_argument("--info", metavar="URL", help="Show URL information")
    parser.add_argument("-o", "--output", default="", help="Output directory")
    parser.add_argument("-f", "--format", default="", help="Media format (mp3, aac, mp4, etc.)")
    parser.add_argument("-q", "--quality", default="best", help="Video quality (best, 720p, 480p, 360p)")
    parser.add_argument("-a", "--audio", action="store_true", help="Download as audio")
    parser.add_argument("--no-gui", action="store_true", help="Force CLI mode")

    args = parser.parse_args()

    if args.info:
        show_info(args.info)
    elif args.cli:
        cli_download(
            url=args.cli,
            output=args.output,
            format_type=args.format,
            quality=args.quality,
            audio_only=args.audio,
        )
    elif args.no_gui:
        print("No URL specified. Use --cli URL to download or --info URL to get info.")
    else:
        # Launch GUI
        if not check_dependencies():
            sys.exit(1)
        launch_gui()


if __name__ == "__main__":
    main()
