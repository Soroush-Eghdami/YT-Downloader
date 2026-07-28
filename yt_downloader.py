import os
import sys
import threading
import queue
from io import BytesIO

import customtkinter as ctk
import yt_dlp
import requests
from PIL import Image

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def friendly_error(exc: Exception) -> str:
    """Map common yt-dlp exceptions to short, human-readable messages."""
    msg = str(exc).lower()
    if "unsupported url" in msg or "is not a valid url" in msg:
        return "That doesn't look like a valid video URL."
    if "sign in" in msg or "age" in msg:
        return "This video is age-restricted or requires sign-in."
    if "private video" in msg:
        return "This video is private."
    if "unavailable" in msg or "removed" in msg:
        return "This video is unavailable or has been removed."
    if "network" in msg or "timed out" in msg or "connection" in msg:
        return "Network error — check your internet connection."
    if "ffmpeg" in msg:
        return "ffmpeg isn't installed or isn't on your PATH — needed for audio/merging."
    return f"Something went wrong ({exc})."


class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Downloader")
        self.geometry("620x620")
        self.resizable(False, False)

        # Optional window icon
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

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        pad = {"padx": 20, "pady": 8}

        ctk.CTkLabel(self, text="YouTube Downloader",
                     font=("Segoe UI", 22, "bold")).pack(pady=(20, 10))

        # --- URL / preview card -------------------------------------------------
        url_frame = ctk.CTkFrame(self, corner_radius=12)
        url_frame.pack(padx=20, pady=(0, 10), fill="x")

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

        # --- Options row ----------------------------------------------------
        options_frame = ctk.CTkFrame(self, fg_color="transparent")
        options_frame.pack(**pad, fill="x")

        self.quality_var = ctk.StringVar(value="Best")
        ctk.CTkLabel(options_frame, text="Quality:").pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(options_frame, values=["Best", "1080", "720", "480"],
                          variable=self.quality_var, width=100).pack(side="left")

        self.audio_only_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(options_frame, text="Audio only (MP3)",
                         variable=self.audio_only_var).pack(side="left", padx=20)

        # --- Output folder ----------------------------------------------------
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.pack(**pad, fill="x")

        self.folder_label = ctk.CTkLabel(folder_frame, text=f"Save to: {self.output_dir}",
                                          font=("Segoe UI", 11))
        self.folder_label.pack(side="left")
        ctk.CTkButton(folder_frame, text="Change", width=80,
                      command=self._choose_folder).pack(side="right")

        # --- Download button ----------------------------------------------------
        self.download_btn = ctk.CTkButton(self, text="Download", height=40,
                                           font=("Segoe UI", 14, "bold"),
                                           command=self._start_download)
        self.download_btn.pack(pady=(10, 10))

        # --- Overall progress ----------------------------------------------------
        self.progress_bar = ctk.CTkProgressBar(self, width=560)
        self.progress_bar.set(0)
        self.progress_bar.pack(**pad)

        self.status_label = ctk.CTkLabel(self, text="Idle", font=("Segoe UI", 11))
        self.status_label.pack(pady=(0, 10))

        # --- Per-item queue status ----------------------------------------------------
        ctk.CTkLabel(self, text="Queue:", anchor="w",
                     font=("Segoe UI", 12, "bold")).pack(padx=20, fill="x")
        self.queue_list_frame = ctk.CTkScrollableFrame(self, height=140)
        self.queue_list_frame.pack(padx=20, pady=(4, 20), fill="both", expand=True)

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
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            title = info.get("title", "")
            thumb_url = info.get("thumbnail")
            self.progress_queue.put(("preview", title, thumb_url))
        except Exception as e:
            self.progress_queue.put(("preview_error", friendly_error(e)))

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

    # ------------------------------------------------------------ options ---
    def _build_ydl_opts(self, progress_hook=None):
        outtmpl = os.path.join(self.output_dir, "%(title)s.%(ext)s")
        opts = {
            "outtmpl": outtmpl,
            "noplaylist": False,
        }
        if progress_hook:
            opts["progress_hooks"] = [progress_hook]

        if self.audio_only_var.get():
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            q = self.quality_var.get()
            opts["format"] = ("bestvideo+bestaudio/best" if q == "Best"
                               else f"bestvideo[height<={q}]+bestaudio/best")
        return opts

    # ------------------------------------------------------------ download ---
    def _start_download(self):
        urls = self._get_urls()
        if not urls:
            self.status_label.configure(text="Please paste at least one valid URL.")
            return

        # Reset queue display
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

            def hook(d, url=url):
                if d["status"] == "downloading":
                    pct_str = d.get("_percent_str", "0%").strip().replace("%", "")
                    try:
                        pct = float(pct_str) / 100
                    except ValueError:
                        pct = 0
                    speed = d.get("_speed_str", "").strip()
                    self.progress_queue.put(("item_progress", url, pct, speed))
                elif d["status"] == "finished":
                    self.progress_queue.put(("batch_status", url, "processing", None))

            opts = self._build_ydl_opts(progress_hook=hook)
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                self.progress_queue.put(("batch_status", url, "done", None))
            except Exception as e:
                self.progress_queue.put(("batch_status", url, "error", friendly_error(e)))

            self.progress_queue.put(("overall_progress", (i + 1) / total))

        self.progress_queue.put(("batch_complete", f"Finished {total} download(s)."))

    # --------------------------------------------------------- queue poll ---
    def _poll_queue(self):
        try:
            while True:
                item = self.progress_queue.get_nowait()
                kind = item[0]

                if kind == "preview":
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
                        if state == "error":
                            text += f" — {error_msg}"
                        else:
                            text += f" — {state}"
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