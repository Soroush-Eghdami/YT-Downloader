# YouTube Downloader

A simple desktop app for downloading YouTube videos (or audio) with a modern GUI, built with
[yt-dlp](https://github.com/yt-dlp/yt-dlp) and [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).

## Features

- Paste one or more URLs and download them as a batch, with live per-item progress
- Choose video quality (Best / 1080p / 720p / 480p) or extract audio only as MP3
- Thumbnail + title preview before downloading
- Friendly error messages for common failures (private/age-restricted/unavailable videos, network issues)
- Choose your own download folder

## Requirements

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/download.html) installed and available on your system PATH
  (required for merging video/audio and for MP3 extraction)

## Installation

1. Clone or download this project.
2. (Optional but recommended) Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install customtkinter yt-dlp pillow requests
   ```
4. Install ffmpeg:
   - **Mac:** `brew install ffmpeg`
   - **Ubuntu/Debian:** `sudo apt install ffmpeg`
   - **Windows:** download a build from ffmpeg.org and add its `bin` folder to your PATH

## Usage

```bash
python gui_downloader.py
```

1. Paste one or more video/playlist URLs into the text box (one per line).
2. Optionally click **Preview first URL** to confirm the title/thumbnail before downloading.
3. Pick a quality, or check **Audio only (MP3)**.
4. Choose a save folder (defaults to your `Downloads` folder).
5. Click **Download** and watch progress per item in the queue list below.

## Packaging as a standalone app (optional)

To share this with people who don't have Python installed:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --icon=icon.ico --name "YouTubeDownloader" gui_downloader.py
```

The executable will be in the `dist/` folder. Note that PyInstaller does **not** bundle ffmpeg —
either tell users to install it separately, or place an `ffmpeg` binary next to the executable and
set `opts["ffmpeg_location"]` in the code to point to it.

## Project structure

```
.
├── gui_downloader.py   # Main application
├── icon.ico             # Optional window/app icon (add your own)
└── README.md
```

## Notes

- This tool is intended for downloading content you have the right to download
  (e.g. your own uploads, public domain content, or videos where the creator permits downloads).
  Respect YouTube's Terms of Service and applicable copyright law.
- yt-dlp is updated frequently to keep up with YouTube changes — if downloads suddenly start
  failing, try `pip install -U yt-dlp`.
