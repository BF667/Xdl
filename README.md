# Xdl Download Manager

**An open-source alternative to Internet Download Manager (IDM)** — built with Python and PyQt5.

Xdl is a powerful, feature-rich download manager that supports video/audio downloads from 1000+ sites, cloud storage services, and generic HTTP/HTTPS file downloads with multi-threaded segmented downloading, resume support, and an IDM-like graphical interface.

---

## Features

### Multi-Threaded Downloads
- **Segmented downloading** — Split files into up to 32 segments for maximum download speed
- **Resume support** — Pause and resume downloads at any time, even after restarting the application
- **Smart file detection** — Automatically detects file size, name, and resume capability from server headers

### Video & Audio Downloads (1000+ Sites)
Powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp), Xdl supports downloading from virtually any video/audio platform:

| Site | Video | Audio | Playlists |
|------|:-----:|:-----:|:---------:|
| YouTube | ✅ | ✅ | ✅ |
| Vimeo | ✅ | ✅ | ✅ |
| Dailymotion | ✅ | ✅ | ✅ |
| TikTok | ✅ | ✅ | — |
| Twitter/X | ✅ | ✅ | — |
| Facebook | ✅ | ✅ | — |
| Instagram | ✅ | ✅ | — |
| Twitch | ✅ | ✅ | ✅ |
| Reddit | ✅ | ✅ | — |
| SoundCloud | — | ✅ | ✅ |
| Bandcamp | — | ✅ | ✅ |
| Bilibili | ✅ | ✅ | ✅ |
| Rumble | ✅ | ✅ | — |
| Odysee | ✅ | ✅ | ✅ |
| 900+ more sites | ✅ | ✅ | varies |

**Video quality options:** Best, 720p, 480p, 360p, 240p

**Audio format options:** MP3, AAC, FLAC, Opus, WAV (with automatic FFmpeg conversion)

### Cloud Storage Downloads
| Service | Features |
|---------|----------|
| **Google Drive** | Direct download, file ID extraction, confirmation page handling, cookie support |
| **MediaFire** | Direct link extraction, progress tracking |
| **Pixeldrain** | API-based download, file info retrieval |
| **HuggingFace** | Model/dataset downloads, URL resolution |
| **Generic HTTP/HTTPS** | Any direct download link, HEAD-based file detection |

### IDM-Like Graphical Interface
- **Category sidebar** — Auto-organize downloads by type (Video, Audio, Documents, Compressed, Programs, Images)
- **Download table** — Real-time progress bars, speed, ETA, status, site name, and date
- **Toolbar** — Quick access to Add, Resume, Pause, Cancel, Delete, Resume All, Pause All, Schedule, Batch, Open File, Open Folder, Settings
- **Right-click context menu** — Quick actions on any download item
- **System tray icon** — Minimize to tray, tray notifications on download completion
- **Color-coded status** — Blue (downloading), Green (completed), Orange (paused), Red (error), Gray (queued)

### Download Management
- **Queue system** — Priority-based download queue with concurrent download limiting (1-10 simultaneous)
- **Batch download** — Add multiple URLs at once from a text list
- **Scheduling** — Schedule downloads to start at a specific time
- **Clipboard monitoring** — Automatically detect URLs copied to the clipboard

### Settings & Configuration
- **General** — Default save path, max concurrent downloads, default segments, startup options
- **Connection** — Proxy server, custom User-Agent, timeout, retries, speed limit
- **Monitoring** — Clipboard monitoring toggle, auto-add URLs, check interval, file type filters
- **Categories** — Custom subfolder names for each file category

### CLI Mode
Use Xdl from the command line without the GUI:
```bash
python3 main.py --cli URL                 # Download with default settings
python3 main.py --cli URL -a              # Download as audio (MP3)
python3 main.py --cli URL -f mp3          # Download as MP3 audio
python3 main.py --cli URL -q 720p         # Download video in 720p
python3 main.py --cli URL -o /path/to     # Save to specific folder
python3 main.py --info URL                # Show URL information only
```

### Gradio Web Demo
Launch a full-featured web interface powered by **Gradio 6+**:
```bash
python3 gradio_demo.py                    # Launch on http://localhost:7860
python3 gradio_demo.py --share            # Launch with public share link
python3 gradio_demo.py --port 8080        # Launch on custom port
python3 gradio_demo.py --no-browser       # Don't open browser automatically
```

The Gradio web demo provides all download manager features through a browser:
- Add single or batch downloads
- URL auto-detection and site identification
- Video/Audio quality and format selection
- Real-time progress tracking with auto-refresh (3-second intervals)
- Pause/Resume/Cancel/Remove controls
- Download details viewer
- Category filtering
- Connection settings (proxy, user-agent, speed limit)
- About page with feature overview

---

## Installation

### Prerequisites
- **Python 3.8+**
- **FFmpeg** (required for audio extraction and video merging) — [Download](https://ffmpeg.org/download.html)

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install PyQt5 yt-dlp requests beautifulsoup4 tqdm pyperclip lxml gradio
```

### Run

```bash
# GUI Mode (PyQt5 Desktop)
python3 main.py

# Gradio Web Demo (Browser)
python3 gradio_demo.py

# CLI Mode
python3 main.py --cli https://youtube.com/watch?v=dQw4w9WgXcQ

# Get URL info
python3 main.py --info https://youtube.com/watch?v=dQw4w9WgXcQ
```

---

## Project Structure

```
Xdl/
├── main.py                          # Entry point (GUI + CLI modes)
├── gradio_demo.py                   # Gradio 6+ web interface
├── requirements.txt                 # Python dependencies
├── setup.py                         # Package setup
├── LICENSE                          # Unlicense (Public Domain)
│
└── xdl/
    ├── __init__.py                  # Package metadata
    │
    ├── core/                        # Core download engine
    │   ├── __init__.py
    │   ├── engine.py                # Multi-threaded segmented download engine
    │   ├── models.py                # Data models (DownloadItem, Status, Category)
    │   └── queue_manager.py         # Queue with scheduling & priority management
    │
    ├── downloaders/                 # Site-specific download handlers
    │   ├── __init__.py
    │   ├── base.py                  # Abstract base downloader class
    │   ├── youtube.py               # YouTube + 50+ video sites (via yt-dlp)
    │   ├── gdrive.py                # Google Drive downloader
    │   ├── mediafire.py             # MediaFire downloader
    │   ├── pixeldrain.py            # Pixeldrain downloader
    │   ├── huggingface.py           # HuggingFace model/dataset downloader
    │   ├── generic.py               # Generic HTTP/HTTPS fallback downloader
    │   └── router.py                # Auto site detection & downloader routing
    │
    ├── gui/                         # PyQt5 graphical interface
    │   ├── __init__.py
    │   ├── main_window.py           # IDM-like main window
    │   ├── add_download_dialog.py   # Add URL dialog with format/quality options
    │   ├── settings_dialog.py       # Settings dialog (4 tabs)
    │   └── about_dialog.py          # About dialog
    │
    └── utils/                       # Utility modules
        ├── __init__.py
        ├── clipboard_monitor.py     # Clipboard URL detection
        └── helpers.py               # Format helpers (size, speed, time, URL validation)
```

---

## Usage Guide

### Adding a Download
1. Click **"➕ Add URL"** on the toolbar (or press `Ctrl+N`)
2. Paste the URL into the input field
3. Click **"Detect"** to auto-analyze the URL (site, filename, file size)
4. Choose download options:
   - **Save path** — Where to save the file
   - **Category** — Auto-detected or manually selected
   - **Segments** — Number of download threads (1-32, more = faster for large files)
   - **Download type** — Video or Audio (for media sites)
   - **Video quality** — Best, 720p, 480p, 360p, 240p
   - **Audio format** — MP3, AAC, FLAC, Opus, WAV
5. Click **"Add Download"** to start

### Managing Downloads
| Action | How |
|--------|-----|
| **Pause** | Select download → Click "⏸ Pause" or right-click → Pause |
| **Resume** | Select paused download → Click "▶ Resume" or double-click |
| **Cancel** | Select download → Click "⏹ Cancel" |
| **Delete** | Select download → Click "🗑 Delete" |
| **Pause All** | Click "⏸ Pause All" on toolbar |
| **Resume All** | Click "⏩ Resume All" on toolbar |
| **Open File** | Select completed download → Click "📂 Open File" or double-click |
| **Open Folder** | Click "📁 Open Folder" to open the download directory |
| **Copy URL** | Right-click download → "📋 Copy URL" |

### Filtering by Category
Click any category in the left sidebar to filter the download list:
- **All Downloads** — Show everything
- **Video / Audio / Documents / Compressed / Programs / Images / Other** — Filter by file type
- **Completed** — Show only finished downloads
- **Queue** — Show pending/scheduled downloads

### Batch Download
1. Click **"📋 Batch"** on the toolbar
2. Enter one URL per line
3. Click OK — all valid URLs will be added to the queue

### Scheduling a Download
1. Select a download from the list
2. Click **"⏰ Schedule"** on the toolbar
3. Enter the start time in `HH:MM` format (e.g., `22:30`)

### Clipboard Monitoring
When enabled, Xdl watches your clipboard for URLs:
- **Auto-detect** — URLs copied to clipboard are detected automatically
- **Notification** — A system tray notification appears when a URL is found
- **Auto-add** — Optionally add detected URLs to the queue automatically (enable in Settings → Monitoring)

### Settings
Open settings via **"⚙ Settings"** on the toolbar:

| Tab | Options |
|-----|---------|
| **General** | Default save path, max concurrent downloads, default segments, startup options, tray icon |
| **Connection** | Proxy server (HTTP/SOCKS5), custom User-Agent, connection timeout, max retries, speed limit |
| **Monitoring** | Clipboard monitoring toggle, auto-add URLs, check interval, video/audio URL filters |
| **Categories** | Custom subfolder names for each file category |

Settings are saved to `~/.xdl/settings.json` and persist between sessions.

---

## CLI Reference

```
usage: main.py [-h] [--cli URL] [--info URL] [-o OUTPUT] [-f FORMAT] 
               [-q QUALITY] [-a] [--no-gui]

Xdl Download Manager - Open-source IDM Alternative

optional arguments:
  -h, --help            Show help message and exit
  --cli URL             Download URL from command line
  --info URL            Show URL information without downloading
  -o, --output OUTPUT   Output directory for downloaded file
  -f, --format FORMAT   Media format (mp3, aac, mp4, flac, opus, wav)
  -q, --quality QUALITY Video quality (best, 720p, 480p, 360p, 240p)
  -a, --audio           Download as audio (MP3)
  --no-gui              Force CLI mode (no GUI)
```

### CLI Examples

```bash
# Download a YouTube video in best quality
python3 main.py --cli https://youtube.com/watch?v=dQw4w9WgXcQ

# Download a YouTube video as MP3 audio
python3 main.py --cli https://youtube.com/watch?v=dQw4w9WgXcQ -a

# Download as FLAC audio
python3 main.py --cli https://youtube.com/watch?v=dQw4w9WgXcQ -f flac

# Download a video in 720p
python3 main.py --cli https://youtube.com/watch?v=dQw4w9WgXcQ -q 720p

# Download to a specific folder
python3 main.py --cli https://example.com/file.zip -o /home/user/Downloads

# Download from Google Drive
python3 main.py --cli https://drive.google.com/file/d/FILE_ID/view

# Download from MediaFire
python3 main.py --cli https://www.mediafire.com/file/FILE_ID/filename.zip/file

# Get info about a URL without downloading
python3 main.py --info https://youtube.com/watch?v=dQw4w9WgXcQ
```

---

## Supported Sites (Full List)

### Video Platforms
YouTube, Vimeo, Dailymotion, Twitch, TikTok, Rumble, Odysee, BitChute, Brighteon, Bilibili, NicoNico, Streamable, LiveLeak, Veoh, Metacafe, Coub, and many more.

### Social Media
Twitter/X, Facebook, Instagram, Reddit, Tumblr, Pinterest, Snapchat, Periscope.

### Audio Platforms
SoundCloud, Bandcamp, Audiomack, Epidemic Sound, Art19, Podbean, Simplecast, Mixcloud.

### Educational
TED, Udemy, Skillshare, Coursera, Pluralsight, Panopto, Echo360.

### Anime/Streaming
Crunchyroll, Funimation.

### Cloud Storage
Google Drive, MediaFire, Pixeldrain, HuggingFace.

### Generic
Any direct HTTP/HTTPS download link (ZIP, EXE, ISO, PDF, etc.)

> **Note:** Full yt-dlp supported site list: [https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

## How It Works

### Segmented Downloading
When a server supports range requests, Xdl splits the file into multiple segments and downloads them simultaneously. Each segment runs in its own thread and writes to a temporary file. Once all segments complete, they are merged into the final output file. This can significantly increase download speeds, especially for large files on high-latency connections.

```
File (100 MB)
├── Segment 0: bytes 0-12.5 MB     ── Thread 0
├── Segment 1: bytes 12.5-25 MB    ── Thread 1
├── Segment 2: bytes 25-37.5 MB    ── Thread 2
├── Segment 3: bytes 37.5-50 MB    ── Thread 3
├── Segment 4: bytes 50-62.5 MB    ── Thread 4
├── Segment 5: bytes 62.5-75 MB    ── Thread 5
├── Segment 6: bytes 75-87.5 MB    ── Thread 6
└── Segment 7: bytes 87.5-100 MB   ── Thread 7
```

### Resume Support
If a download is paused or interrupted, Xdl records the last downloaded byte position. When resuming, it sends a `Range: bytes=N-` header to the server to continue from where it left off, avoiding re-downloading already completed data.

### Site Detection
The `DownloadRouter` automatically detects which site a URL belongs to by checking against known domain patterns. It then routes the download to the appropriate specialized downloader:

```
URL Input → DownloadRouter → Site Detection
  ├── youtube.com, vimeo.com, tiktok.com, etc.  → YouTubeDownloader (yt-dlp)
  ├── drive.google.com                           → GDriveDownloader
  ├── mediafire.com                              → MediaFireDownloader
  ├── pixeldrain.com                             → PixeldrainDownloader
  ├── huggingface.co                             → HuggingFaceDownloader
  └── any other http/https URL                   → GenericDownloader
```

### Category Auto-Detection
Files are automatically categorized based on their extension:

| Category | Extensions |
|----------|-----------|
| Video | mp4, mkv, avi, mov, wmv, flv, webm, m4v, mpg, mpeg, 3gp, ts, vob |
| Audio | mp3, wav, flac, aac, ogg, wma, m4a, opus, aiff, ape, alac |
| Document | pdf, doc, docx, xls, xlsx, ppt, pptx, txt, rtf, csv, epub |
| Compressed | zip, rar, 7z, tar, gz, bz2, xz, iso, dmg, deb, rpm |
| Program | exe, msi, apk, app, jar, bat, sh |
| Image | jpg, png, gif, bmp, svg, webp, ico, tiff, psd, heic |

---

## Configuration

Settings are stored in `~/.xdl/settings.json`:

```json
{
  "default_save_path": "/home/user/Downloads/Xdl",
  "max_concurrent": 3,
  "default_segments": 8,
  "start_on_boot": false,
  "show_tray_icon": true,
  "proxy": "",
  "user_agent": "",
  "connection_timeout": 60,
  "max_retries": 5,
  "speed_limit_kb": 0,
  "monitor_clipboard": true,
  "auto_add_urls": false,
  "clipboard_interval_ms": 1000,
  "monitor_video": true,
  "monitor_audio": true
}
```

### Proxy Configuration
Xdl supports HTTP, HTTPS, and SOCKS5 proxies:
```
http://proxy-server:port
https://proxy-server:port
socks5://proxy-server:port
```

Set the proxy in **Settings → Connection → Proxy Server**, or it will be applied to all downloaders automatically.

---

## Troubleshooting

### "Could not extract video info"
- Make sure yt-dlp is up to date: `pip install --upgrade yt-dlp`
- Some sites may require authentication cookies

### "Download speed is slow"
- Increase the number of segments in download options (up to 32)
- Check if a speed limit is set in Settings → Connection
- Try using a proxy if your ISP throttles downloads

### "Resume not working"
- The server must support range requests (`Accept-Ranges: bytes`)
- Some sites (especially video platforms) don't support resumable downloads
- For these sites, the download will restart from the beginning

### "FFmpeg not found" (audio extraction)
- Install FFmpeg and ensure it's in your system PATH
- Download from: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)

### "Clipboard monitoring not working"
- Make sure `pyperclip` is installed: `pip install pyperclip`
- Some Linux desktop environments may require additional packages (e.g., `xclip` or `xsel`)

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -am 'Add new feature'`
4. Push the branch: `git push origin feature/my-feature`
5. Create a Pull Request

---

## License

This is free and unencumbered software released into the **public domain** under the [Unlicense](https://unlicense.org/).

Anyone is free to copy, modify, publish, use, compile, sell, or distribute this software, either in source code form or as a compiled binary, for any purpose, commercial or non-commercial.

---

## Credits

- **yt-dlp** — [https://github.com/yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) (video/audio extraction engine)
- **Gradio 6** — [https://gradio.app](https://gradio.app) (web interface framework)
- **PyQt5** — [https://www.riverbankcomputing.com/software/pyqt/](https://www.riverbankcomputing.com/software/pyqt/) (desktop GUI framework)
- **requests** — [https://docs.python-requests.org/](https://docs.python-requests.org/) (HTTP library)
- **BeautifulSoup** — [https://www.crummy.com/software/BeautifulSoup/](https://www.crummy.com/software/BeautifulSoup/) (HTML parsing)

---

**Xdl Download Manager** — Fast. Powerful. Open Source.
