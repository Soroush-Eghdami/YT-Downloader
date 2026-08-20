import os
import re
import sys
import json
import subprocess
import threading
import queue
from io import BytesIO

import customtkinter as ctk
import requests
from PIL import Image

import ytdlp_manager

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_PROGRESS_RE = re.compile(r"\[download\]\s+([\d.]+)% of.*?at\s+(\S+)")


def friendly_error(text: str) -> str:
    msg = text.lower()
    if "unsupported url" in msg or "is not a valid url" in msg:
        return "That doesn't look like a valid video URL."
    if "sign in" in msg or "age" in msg:
        return "This video is age-restricted or requires sign-in."
    if "private video" in msg:
        return "This video is private."
    if "unavailable" in msg or "removed" in msg:
        return "This video is unavailable or has been removed."
    if "403" in msg or "forbidden" in msg:
        return "YouTube blocked this request (403). Try updating yt-dlp."
    if "network" in msg or "timed out" in msg or "connection" in msg:
        return "Network error — check your internet connection."
    if "ffmpeg" in msg:
        return "ffmpeg isn't installed or isn't on your PATH — needed for audio/merging."
    return f"Something went wrong ({text[:200]})."


class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Downloader")
        self.geometry("640x700")
        self.resizable(True, True)
        self.minsize(560, 500)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.progress_queue = queue.Queue()
        self.output_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self.queue_row_labels = {}
        self._thumb_image = None

        self._build_ui()
        self.after(100, self._poll_queue)

        # Make sure yt-dlp exists before anything else runs.
        threading.Thread(target=self._startup_check, daemon=True).start()

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        pad = {"padx": 20, "pady": 8}

        self.grid_rowconfigure(7, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="YouTube Downloader",
                     font=("Segoe UI", 22, "bold")).grid(row=0, column=0, pady=(20, 4))

        # --- yt-dlp version / update row ---
        version_frame = ctk.CTkFrame(self, fg_color="transparent")
        version_frame.grid(row=1, column=0, pady=(0, 10))
        self.version_label = ctk.CTkLabel(version_frame, text="yt-dlp: checking...",
                                           font=("Segoe UI", 10), text_color="gray")
        self.version_label.pack(side="left", padx=(0, 10))
        self.update_btn = ctk.CTkButton(version_frame, text="Check for updates", width=140,
                                         height=24, font=("Segoe UI", 10),
                                         command=self._manual_update)
        self.update_btn.pack(side="left")

        # --- URL / preview card ---
        url_frame = ctk.CTkFrame(self, corner_radius=12)
        url_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")

        self.thumbnail_label = ctk.CTkLabel(url_frame, text="", width=160, height=90)
        self.thumbnail_label.pack(side="left", padx=10, pady=10)

        entry_col = ctk.CTkFrame(url_frame, fg_color="transparent")
        entry_col.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)

        ctk.CTkLabel(entry_col, text="URLs (one per line):", anchor="w",
                     font=("Segoe UI", 11)).pack(fill="x")
        self.urls_box = ctk.CTkTextbox(entry_col, height=70)
        self.urls_box.pack(fill="x", pady=(4, 4))

        self.video_title_label = ctk.CTkLabel(entry_col, text="",
                                               font=("Segoe UI", 11),
                                               text_color="gray", anchor="w")
        self.video_title_label.pack(fill="x")

        ctk.CTkButton(entry_col, text="Preview first URL", width=140,
                      command=self._fetch_preview).pack(anchor="e", pady=(6, 0))

        # --- Options row ---
        options_frame = ctk.CTkFrame(self, fg_color="transparent")
        options_frame.grid(row=3, column=0, sticky="ew", **pad)

        self.quality_var = ctk.StringVar(value="Best")
        ctk.CTkLabel(options_frame, text="Quality:").pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(options_frame, values=["Best", "1080", "720", "480"],
                          variable=self.quality_var, width=100).pack(side="left")

        self.audio_only_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(options_frame, text="Audio only (MP3)",
                         variable=self.audio_only_var).pack(side="left", padx=20)

        self.no_playlist_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(options_frame, text="Single video only (ignore playlist/mix)",
                         variable=self.no_playlist_var).pack(side="left")

        # --- Output folder ---
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.grid(row=4, column=0, sticky="ew", **pad)

        self.folder_label = ctk.CTkLabel(folder_frame, text=f"Save to: {self.output_dir}",
                                          font=("Segoe UI", 11))
        self.folder_label.pack(side="left")
        ctk.CTkButton(folder_frame, text="Change", width=80,
                      command=self._choose_folder).pack(side="right")

        # --- Download button ---
        self.download_btn = ctk.CTkButton(self, text="Download", height=40,
                                           font=("Segoe UI", 14, "bold"),
                                           command=self._start_download)
        self.download_btn.grid(row=5, column=0, pady=(10, 10))

        # --- Overall progress ---
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.grid(row=6, column=0, sticky="ew", **pad)
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, sticky="ew")

        self.status_label = ctk.CTkLabel(self, text="Idle", font=("Segoe UI", 11))
        self.status_label.grid(row=6, column=0, pady=(36, 0), sticky="w", padx=24)

        # --- Queue (resizes with the window) ---
        queue_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        queue_wrapper.grid(row=7, column=0, padx=20, pady=(4, 20), sticky="nsew")
        queue_wrapper.grid_rowconfigure(1, weight=1)
        queue_wrapper.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(queue_wrapper, text="Queue:", anchor="w",
                     font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.queue_list_frame = ctk.CTkScrollableFrame(queue_wrapper)
        self.queue_list_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

    # ---------------------------------------------------- yt-dlp lifecycle ---
    def _startup_check(self):
        try:
            downloaded = ytdlp_manager.ensure_ytdlp(
                progress_callback=lambda p: self.progress_queue.put(("ytdlp_dl_progress", p))
            )
            version = ytdlp_manager.get_installed_version() or "unknown"
            self.progress_queue.put(("ytdlp_ready", version, downloaded))
        except Exception as e:
            self.progress_queue.put(("ytdlp_error", str(e)))

    def _manual_update(self):
        self.update_btn.configure(state="disabled", text="Checking...")
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self):
        try:
            current = ytdlp_manager.get_installed_version()
            tag, _ = ytdlp_manager.get_latest_release_info()
            # yt-dlp's own --version output matches its release tag (e.g. 2026.07.15)
            if current and tag and current.strip() == tag.strip():
                self.progress_queue.put(("update_result", f"Already up to date ({current})."))
                return
            ytdlp_manager.download_latest(
                progress_callback=lambda p: self.progress_queue.put(("ytdlp_dl_progress", p))
            )
            new_version = ytdlp_manager.get_installed_version() or tag
            self.progress_queue.put(("update_result", f"Updated to {new_version}."))
        except Exception as e:
            self.progress_queue.put(("update_result", f"Update check failed: {e}"))

    # --------------------------------------------------------- folder pick ---
    def _choose_folder(self):
        folder = ctk.filedialog.askdirectory()
        if folder:
            self.output_dir = folder
            self.folder_label.configure(text=f"Save to: {self.output_dir}")

    # ------------------------------------------------------------ preview ---
    def _fetch_preview(self):
        urls = self._get_urls()
        if not urls:
            self.status_label.configure(text="Paste at least one URL first.")
            return
        threading.Thread(target=self._preview_worker, args=(urls[0],), daemon=True).start()

    def _preview_worker(self, url):
        ytdlp_path = ytdlp_manager.get_ytdlp_path()
        if not os.path.exists(ytdlp_path):
            self.progress_queue.put(("preview_error", "yt-dlp isn't ready yet — try again in a moment."))
            return

        cmd = [ytdlp_path, "--dump-json", "--skip-download"]
        if self.no_playlist_var.get():
            cmd.append("--no-playlist")
        cmd.append(url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                     creationflags=_NO_WINDOW)
            if result.returncode != 0:
                self.progress_queue.put(("preview_error", friendly_error(result.stderr)))
                return
            info = json.loads(result.stdout.splitlines()[0])
            self.progress_queue.put(("preview", info.get("title", ""), info.get("thumbnail")))
        except Exception as e:
            self.progress_queue.put(("preview_error", friendly_error(str(e))))

    def _set_thumbnail(self, thumb_url):
        try:
            resp = requests.get(thumb_url, timeout=5)
            img = Image.open(BytesIO(resp.content)).resize((160, 90))
            self._thumb_image = ctk.CTkImage(light_image=img, dark_image=img, size=(160, 90))
            self.thumbnail_label.configure(image=self._thumb_image, text="")
        except Exception:
            pass

    # --------------------------------------------------------- URL parsing ---
    def _get_urls(self):
        raw = self.urls_box.get("1.0", "end").strip()
        return [u.strip() for u in raw.splitlines() if u.strip().startswith(("http://", "https://"))]

    # ------------------------------------------------------------- command ---
    def _build_ytdlp_cmd(self, url):
        ytdlp_path = ytdlp_manager.get_ytdlp_path()
        outtmpl = os.path.join(self.output_dir, "%(title)s.%(ext)s")
        cmd = [ytdlp_path, "-o", outtmpl, "--newline"]

        if self.no_playlist_var.get():
            cmd.append("--no-playlist")

        if self.audio_only_var.get():
            cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "192K"]
        else:
            q = self.quality_var.get()
            fmt = "bestvideo+bestaudio/best" if q == "Best" else f"bestvideo[height<={q}]+bestaudio/best"
            cmd += ["-f", fmt]

        cmd.append(url)
        return cmd

    # ------------------------------------------------------------ download ---
    def _start_download(self):
        if not os.path.exists(ytdlp_manager.get_ytdlp_path()):
            self.status_label.configure(text="yt-dlp isn't ready yet — try again in a moment.")
            return

        urls = self._get_urls()
        if not urls:
            self.status_label.configure(text="Please paste at least one valid URL.")
            return

        for widget in self.queue_list_frame.winfo_children():
            widget.destroy()
        self.queue_row_labels = {}

        for url in urls:
            row = ctk.CTkLabel(self.queue_list_frame, text=f"⏳ Queued — {url[:60]}", anchor="w")
            row.pack(fill="x", pady=2, padx=4)
            self.queue_row_labels[url] = row

        self.progress_bar.set(0)
        self.download_btn.configure(state="disabled", text="Downloading...")
        threading.Thread(target=self._batch_worker, args=(urls,), daemon=True).start()

    def _batch_worker(self, urls):
        total = len(urls)
        for i, url in enumerate(urls):
            self.progress_queue.put(("batch_status", url, "downloading", None))
            cmd = self._build_ytdlp_cmd(url)

            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, bufsize=1, creationflags=_NO_WINDOW)
                last_lines = []
                for line in proc.stdout:
                    last_lines.append(line)
                    if len(last_lines) > 20:
                        last_lines.pop(0)
                    match = _PROGRESS_RE.search(line)
                    if match:
                        pct = float(match.group(1)) / 100
                        speed = match.group(2)
                        self.progress_queue.put(("item_progress", url, pct, speed))
                    elif "Merging" in line or "Extracting audio" in line or "Destination" in line:
                        self.progress_queue.put(("batch_status", url, "processing", None))

                proc.wait()
                if proc.returncode == 0:
                    self.progress_queue.put(("batch_status", url, "done", None))
                else:
                    err_text = "".join(last_lines)
                    self.progress_queue.put(("batch_status", url, "error", friendly_error(err_text)))
            except Exception as e:
                self.progress_queue.put(("batch_status", url, "error", friendly_error(str(e))))

            self.progress_queue.put(("overall_progress", (i + 1) / total))

        self.progress_queue.put(("batch_complete", f"Finished {total} download(s)."))

    # --------------------------------------------------------- queue poll ---
    def _poll_queue(self):
        try:
            while True:
                item = self.progress_queue.get_nowait()
                kind = item[0]

                if kind == "ytdlp_ready":
                    _, version, downloaded = item
                    self.version_label.configure(text=f"yt-dlp: {version}")
                    if downloaded:
                        self.status_label.configure(text="Downloaded yt-dlp for the first time.")

                elif kind == "ytdlp_error":
                    self.version_label.configure(text="yt-dlp: setup failed")
                    self.status_label.configure(text=f"Couldn't set up yt-dlp: {item[1]}")

                elif kind == "ytdlp_dl_progress":
                    self.version_label.configure(text=f"yt-dlp: downloading... {item[1]*100:.0f}%")

                elif kind == "update_result":
                    self.update_btn.configure(state="normal", text="Check for updates")
                    self.status_label.configure(text=item[1])
                    version = ytdlp_manager.get_installed_version()
                    if version:
                        self.version_label.configure(text=f"yt-dlp: {version}")

                elif kind == "preview":
                    _, title, thumb_url = item
                    self.video_title_label.configure(text=title[:70])
                    if thumb_url:
                        self._set_thumbnail(thumb_url)

                elif kind == "preview_error":
                    self.video_title_label.configure(text=item[1])

                elif kind == "batch_status":
                    _, url, state, error_msg = item
                    label = self.queue_row_labels.get(url)
                    if label:
                        icon = {"downloading": "⬇️", "processing": "🔄", "done": "✅"}.get(state, "❌")
                        text = f"{icon} {url[:60]}"
                        text += f" — {error_msg}" if state == "error" else f" — {state}"
                        label.configure(text=text)

                elif kind == "item_progress":
                    _, url, pct, speed = item
                    label = self.queue_row_labels.get(url)
                    if label:
                        label.configure(text=f"⬇️ {url[:50]} — {pct*100:.0f}% ({speed})")

                elif kind == "overall_progress":
                    self.progress_bar.set(item[1])

                elif kind == "batch_complete":
                    self.status_label.configure(text=item[1])
                    self.download_btn.configure(state="normal", text="Download")

        except queue.Empty:
            pass

        self.after(100, self._poll_queue)


if __name__ == "__main__":
    app = DownloaderApp()
    app.mainloop()