# YouTube Downloader

A simple desktop app for downloading YouTube videos (or audio) with a modern GUI, built with
[yt-dlp](https://github.com/yt-dlp/yt-dlp) and [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).

## Features

- Paste one or more URLs and download them as a batch, with live per-item progress
- Choose video quality (Best / 1080p / 720p / 480p) or extract audio only as MP3
- Thumbnail + title preview before downloading
- "Single video only" toggle to avoid accidentally downloading an entire playlist/Mix
- Friendly error messages for common failures (private/age-restricted/unavailable videos, network issues)
- Choose your own download folder
- **Self-updating yt-dlp** — the app manages its own standalone `yt-dlp` binary and can fetch
  the latest version on demand, without needing a new app release

## How the yt-dlp updater works

YouTube changes frequently, and yt-dlp needs regular updates to keep working. Instead of bundling
the yt-dlp Python library inside the app (which would freeze its version at build time), this app
downloads the official standalone `yt-dlp` binary from
[GitHub Releases](https://github.com/yt-dlp/yt-dlp/releases) and stores it next to the app itself.
On first run it's downloaded automatically; after that, click **"Check for updates"** in the app
any time to fetch the newest version — no reinstall of the app required.

This means:
- The app's own `.exe` doesn't need to be rebuilt just because YouTube changed something
- `yt-dlp.exe` (or `yt-dlp` / `yt-dlp_macos` on other platforms) lives as a plain file next to
  the app, not baked into it — see `ytdlp_manager.py`
- An internet connection is required the first time the app runs, to fetch yt-dlp

## Requirements

- Python 3.9+ (only needed if running from source — not needed for the packaged `.exe`)
- [ffmpeg](https://ffmpeg.org/download.html) installed and available on your system PATH
  (required for merging video/audio and for MP3 extraction)
- Internet access on first run, to download the yt-dlp binary

## Installation & Usage

There are two ways to run this app — pick whichever fits you.

### Option A: Download the prebuilt .exe (no Python needed)

This is the easiest way if you just want to use the app.

1. Go to the [Releases page](../../releases) and download `YouTubeDownloader.exe` from the
   latest release.
2. Install [ffmpeg](https://ffmpeg.org/download.html) and make sure it's on your system PATH —
   required for merging video/audio and for MP3 extraction. (See "Requirements" above for
   platform-specific install commands.)
3. Double-click `YouTubeDownloader.exe` to run it. No installer, no Python required.
4. **First launch will pause briefly** — the app downloads the latest `yt-dlp` binary
   automatically and saves it next to the `.exe`. This needs an internet connection; after
   that first download, `yt-dlp` stays on disk and doesn't need to re-download unless you
   click "Check for updates."
5. Paste one or more video/playlist URLs into the text box (one per line).
6. Optionally click **Preview first URL** to confirm the title/thumbnail before downloading.
7. Pick a quality, or check **Audio only (MP3)**.
8. Leave **"Single video only"** checked unless you actually want to download a full playlist —
   this avoids accidentally pulling in an entire auto-generated YouTube "Mix".
9. Choose a save folder (defaults to your `Downloads` folder).
10. Click **Download** and watch progress per item in the queue list below.
11. If downloads start failing, click **Check for updates** to fetch the latest yt-dlp.

> **Note:** Windows may show a "Windows protected your PC" SmartScreen warning the first time,
> since the .exe isn't code-signed. Click **More info → Run anyway** to proceed.

### Option B: Run from source

Use this if you want to modify the code or aren't on Windows.

1. Clone or download this project.
2. (Optional but recommended) Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install customtkinter requests pillow
   ```
   Note: the `yt-dlp` Python package is **not** required — the app downloads and runs the
   standalone `yt-dlp` binary itself.
4. Install ffmpeg (see "Requirements" above).
5. Run it:
   ```bash
   python yt_downloader.py
   ```
   Usage from here is identical to steps 4–11 in Option A above.

## Packaging as a standalone app

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --icon=icon.ico --name "YouTubeDownloader" yt_downloader.py
```

The executable will be in the `dist/` folder. `yt-dlp.exe` itself is **not** bundled by
PyInstaller — it gets downloaded next to the packaged `.exe` the first time someone runs it.
ffmpeg also isn't bundled; either tell users to install it separately, or place an `ffmpeg`
binary next to the executable and set `ffmpeg_location` accordingly.

## Project structure

```
.
├── yt_downloader.py      # Main application
├── ytdlp_manager.py      # Downloads/updates the standalone yt-dlp binary
├── icon.ico              # Optional window/app icon (add your own)
├── yt-dlp.exe            # Downloaded automatically at runtime — not committed to git
└── README.md
```

## Notes

- This tool is intended for downloading content you have the right to download
  (e.g. your own uploads, public domain content, or videos where the creator permits downloads).
  Respect YouTube's Terms of Service and applicable copyright law.
- GitHub's API for checking the latest yt-dlp release is rate-limited to 60 requests/hour per IP
  for unauthenticated requests — plenty for manual "Check for updates" clicks, but avoid wiring
  this to run automatically on every launch if distributing to many users behind one shared IP.