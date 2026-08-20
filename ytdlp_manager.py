import os
import sys
import platform
import subprocess

import requests

GITHUB_API_LATEST = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _app_dir():
    """Folder the running app lives in — works both as a .py script and a frozen .exe."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _asset_name():
    system = platform.system()
    if system == "Windows":
        return "yt-dlp.exe"
    if system == "Darwin":
        return "yt-dlp_macos"
    return "yt-dlp"  # Linux


def get_ytdlp_path():
    return os.path.join(_app_dir(), _asset_name())


def get_installed_version():
    """Returns the installed binary's version string, or None if not present/runnable."""
    path = get_ytdlp_path()
    if not os.path.exists(path):
        return None
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True,
                              timeout=10, creationflags=_NO_WINDOW)
        return out.stdout.strip() or None
    except Exception:
        return None


def get_latest_release_info():
    """Returns (tag_name, download_url) for the current platform's asset."""
    resp = requests.get(GITHUB_API_LATEST, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    tag = data.get("tag_name", "")
    asset_name = _asset_name()
    for asset in data.get("assets", []):
        if asset.get("name") == asset_name:
            return tag, asset.get("browser_download_url")
    raise RuntimeError(f"Couldn't find asset '{asset_name}' in the latest yt-dlp release.")


def download_latest(progress_callback=None):
    """Download the latest yt-dlp binary, replacing the local copy. Returns the version tag."""
    tag, url = get_latest_release_info()
    dest = get_ytdlp_path()
    tmp_dest = dest + ".download"

    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(tmp_dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=262144):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(downloaded / total)

    if os.path.exists(dest):
        os.remove(dest)
    os.replace(tmp_dest, dest)

    if os.name != "nt":
        os.chmod(dest, 0o755)

    return tag


def ensure_ytdlp(progress_callback=None):
    """Call at startup: download yt-dlp only if it's missing. Returns True if it downloaded."""
    if os.path.exists(get_ytdlp_path()):
        return False
    download_latest(progress_callback)
    return True