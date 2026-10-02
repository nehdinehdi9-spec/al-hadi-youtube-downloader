import os
import re
import sys
import threading
import ctypes
import shutil
from pathlib import Path
from urllib.parse import urlparse
from tkinter import filedialog

import customtkinter as ctk
import yt_dlp
import winsound
import tkinter as tk


# =========================
# إعدادات التطبيق الأساسية
# =========================
WINDOW_WIDTH = 950
WINDOW_HEIGHT = 1050

DARK_BG = "#0b0f19"
DARK_PANEL = "#121a2a"
LIGHT_PANEL = "#171f2f"
GOLD = "#cca43b"
GOLD_DARK = "#a77e1f"
GOLD_SOFT = "#e4c977"
TEXT = "#f5f3ee"
MUTED = "#bab3a7"
SUCCESS = "#7ed89a"
DANGER = "#ff6b6b"
BORDER = "#2e364c"
BLUE = "#1d7bf2"
BLUE_DEEP = "#155fc9"
BLUE_LIGHT = "#63b3ff"


def play_click_sound():
    try:
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass


def get_desktop_path():
    try:
        return str(Path.home() / "Desktop")
    except Exception:
        return str(Path.home())


def ensure_download_folder(custom_path=None):
    if custom_path and os.path.isdir(custom_path):
        return custom_path

    desktop = Path(get_desktop_path())
    folder = desktop / "تنزيلات الهادي"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def get_clipboard_text():
    try:
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        try:
            text = root.clipboard_get()
            root.destroy()
            return text
        except tk.TclError:
            root.destroy()
            return ""
    except Exception:
        return ""


def is_valid_youtube_url(value):
    if not value or not isinstance(value, str):
        return False
    cleaned = value.strip()
    if not cleaned:
        return False

    patterns = [
        r"^(https?://)?(www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]+",
        r"^(https?://)?(www\.)?youtu\.be/[A-Za-z0-9_-]+",
        r"^(https?://)?m\.youtube\.com/watch\?v=[A-Za-z0-9_-]+",
        r"^(https?://)?music\.youtube\.com/watch\?v=[A-Za-z0-9_-]+",
    ]

    for pattern in patterns:
        if re.match(pattern, cleaned):
            return True

    try:
        parsed = urlparse(cleaned)
        if parsed.netloc and ("youtube" in parsed.netloc or "youtu.be" in parsed.netloc):
            return True
    except Exception:
        pass
    return False


def sanitize_filename(name):
    if not name:
        return "download"
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    name = name.strip().strip(".")
    return name[:180] or "download"


def find_ffmpeg():
    candidates = [
        "ffmpeg",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]
    for candidate in candidates:
        try:
            if shutil.which(candidate):
                return candidate
        except Exception:
            pass
    return None


def format_path_for_display(path, max_length=55):
    if not path:
        return "غير محدد"
    if len(path) <= max_length:
        return path
    return "..." + path[-max_length:]


def create_verification_badge(parent, width=22, height=22, text="✓"):
    badge = ctk.CTkFrame(
        parent,
        width=width,
        height=height,
        corner_radius=11,
        fg_color=BLUE,
        border_width=2,
        border_color=BLUE_LIGHT
    )
    badge.grid_propagate(False)
    badge_label = ctk.CTkLabel(
        badge,
        text=text,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        text_color="#f0f7ff",
        fg_color="transparent"
    )
    badge_label.place(relx=0.5, rely=0.5, anchor="center")
    return badge


class DownloadWorker:
    def __init__(self, app, url, download_format, download_path):
        self.app = app
        self.url = url
        self.download_format = download_format
        self.download_path = download_path
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            self.app.set_status("جارٍ تجهيز الوسائط...")
            self.app.update_progress(2, "جارٍ تجهيز الوسائط...")

            download_dir = ensure_download_folder(self.download_path)
            os.makedirs(download_dir, exist_ok=True)

            ydl_opts = {
                "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": True,
                "progress_hooks": [self._progress_hook],
                "extract_flat": False,
                "socket_timeout": 30,
            }

            if self.download_format == "mp3":
                ydl_opts["format"] = "bestaudio/best"
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ]
            else:
                ydl_opts["format"] = "best[ext=mp4]/best"
                ydl_opts["postprocessors"] = []

            ffmpeg = find_ffmpeg()
            if ffmpeg:
                ydl_opts["ffmpeg_location"] = ffmpeg

            if self._stop_event.is_set():
                self.app.set_status("تم إلغاء العملية.")
                self.app.update_progress(0, "تم إلغاء العملية.")
                return

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.app.set_status("جارٍ معالجة الفيديو...")
                self.app.update_progress(5, "جارٍ معالجة الفيديو...")
                ydl.download([self.url])

            self.app.set_status("اكتمل التحميل بنجاح ✓")
            self.app.update_progress(100, "اكتمل التحميل بنجاح ✓")
            self.app.on_download_finished()

        except Exception as exc:
            error_msg = str(exc)[:220]
            print(f"[ERROR] Download failed: {error_msg}")
            self.app.set_status(f"حدث خطأ: {error_msg}")
            self.app.update_progress(0, f"فشل التحميل: {error_msg}")
            self.app.on_download_failed()

    def _progress_hook(self, d):
        if self._stop_event.is_set():
            raise Exception("Download cancelled by user")

        try:
            if d.get("status") == "downloading":
                percent_str = d.get("_percent_str", "0%").strip()
                percent_value = 0
                if "%" in percent_str:
                    try:
                        percent_value = float(percent_str.replace("%", "").strip())
                        percent_value = max(0, min(percent_value, 100))
                    except (ValueError, TypeError):
                        percent_value = 0

                speed = d.get("_speed_str", "...")
                self.app.update_progress(int(percent_value), f"جارٍ التنزيل: {percent_str} - {speed}")

            elif d.get("status") == "finished":
                self.app.update_progress(95, "جارٍ إنهاء الملف...")

            elif d.get("status") == "error":
                error = d.get("error", "Unknown error")
                self.app.set_status(f"خطأ في التنزيل: {str(error)[:100]}")
                self.app.update_progress(0, f"خطأ: {str(error)[:100]}")
        except Exception as e:
            print(f"[Progress Hook Error] {str(e)}")


class HadiApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("الهادي")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.configure(fg_color=DARK_BG)

        self.download_worker = None
        self.current_format = "video"
        self.custom_download_path = ensure_download_folder()

        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        outer = ctk.CTkFrame(self, fg_color=DARK_BG, corner_radius=30)
        outer.grid(row=0, column=0, sticky="nsew", padx=24, pady=18)

        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=1)

        main = ctk.CTkFrame(outer, fg_color=DARK_BG, corner_radius=30)
        main.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        main.grid_columnconfigure(0, weight=1)
        for i in range(15):
            main.grid_rowconfigure(i, weight=0)
        main.grid_rowconfigure(14, weight=1)

        # =========================
        # Header: title + blue badge
        # =========================
        title_row = ctk.CTkFrame(main, fg_color="transparent")
        title_row.grid(row=0, column=0, pady=(26, 8), sticky="n")

        self.title_shadow = ctk.CTkLabel(
            title_row,
            text="الهادي",
            font=ctk.CTkFont(family="Segoe UI", size=60, weight="bold"),
            text_color="#5d430e",
            fg_color="transparent"
        )
        self.title_shadow.grid(row=0, column=0, padx=(0, 0), pady=(5, 0), sticky="n")

        self.title_label = ctk.CTkLabel(
            title_row,
            text="الهادي",
            font=ctk.CTkFont(family="Segoe UI", size=60, weight="bold"),
            text_color=GOLD,
            fg_color="transparent"
        )
        self.title_label.grid(row=0, column=0, padx=(0, 0), pady=(0, 0), sticky="n")

        self.verification_badge = create_verification_badge(title_row, width=30, height=30, text="✓")
        self.verification_badge.grid(row=0, column=1, padx=(14, 0), pady=(10, 0), sticky="n")

        self.pulse_animation()

        # =========================
        # URL row
        # =========================
        url_label = ctk.CTkLabel(
            main,
            text="رابط الفيديو على يوتيوب",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=TEXT,
            anchor="w"
        )
        url_label.grid(row=1, column=0, padx=28, pady=(18, 8), sticky="w")

        entry_row = ctk.CTkFrame(main, fg_color="transparent")
        entry_row.grid(row=2, column=0, padx=28, pady=(0, 8), sticky="ew")
        entry_row.grid_columnconfigure(0, weight=1)
        entry_row.grid_columnconfigure(1, weight=0)

        self.url_entry = ctk.CTkEntry(
            entry_row,
            width=600,
            height=54,
            border_width=1,
            fg_color=DARK_PANEL,
            border_color=BORDER,
            text_color=TEXT,
            placeholder_text="https://www.youtube.com/watch?v=...",
            font=ctk.CTkFont(family="Segoe UI", size=17),
        )
        self.url_entry.grid(row=0, column=0, padx=(0, 12), sticky="ew")

        self.paste_btn = ctk.CTkButton(
            entry_row,
            text="📋 لصق الرابط",
            width=130,
            height=54,
            fg_color=GOLD,
            hover_color=GOLD_DARK,
            text_color="#101419",
            border_color="#f5d27a",
            border_width=2,
            corner_radius=16,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            command=self.paste_from_clipboard
        )
        self.paste_btn.grid(row=0, column=1, sticky="e")
        self._bind_hover_glow(self.paste_btn)

        # =========================
        # Download path block
        # =========================
        path_text = "📂 مسار حفظ الملفات: سطح المكتب ➔ مجلد (تنزيلات الهادي)"
        self.path_label = ctk.CTkLabel(
            main,
            text=path_text,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=GOLD_SOFT,
            anchor="w",
            wraplength=760
        )
        self.path_label.grid(row=3, column=0, padx=28, pady=(4, 4), sticky="w")

        path_row = ctk.CTkFrame(main, fg_color="transparent")
        path_row.grid(row=4, column=0, padx=28, pady=(0, 12), sticky="ew")
        path_row.grid_columnconfigure(0, weight=1)
        path_row.grid_columnconfigure(1, weight=0)

        self.active_path_label = ctk.CTkLabel(
            path_row,
            text=f"مسار التنزيل الحالي: {format_path_for_display(self.custom_download_path, 50)}",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=MUTED,
            anchor="w",
            wraplength=700
        )
        self.active_path_label.grid(row=0, column=0, padx=(0, 12), sticky="w")

        self.change_path_btn = ctk.CTkButton(
            path_row,
            text="📂 تغيير المجلد",
            width=140,
            height=42,
            fg_color=GOLD,
            hover_color=GOLD_DARK,
            text_color="#101419",
            border_color="#f5d27a",
            border_width=2,
            corner_radius=14,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self.change_download_path
        )
        self.change_path_btn.grid(row=0, column=1, sticky="e")
        self._bind_hover_glow(self.change_path_btn)

        # =========================
        # Format selection
        # =========================
        format_frame = ctk.CTkFrame(main, fg_color=LIGHT_PANEL, corner_radius=24)
        format_frame.grid(row=5, column=0, padx=28, pady=(8, 12), sticky="ew")

        format_frame.grid_columnconfigure(0, weight=1)
        format_frame.grid_columnconfigure(1, weight=1)

        self.video_btn = ctk.CTkButton(
            format_frame,
            text="🎞️ فيديو بأعلى جودة (MP4)",
            height=58,
            fg_color=GOLD,
            hover_color=GOLD_DARK,
            text_color="#101419",
            border_color="#f5d27a",
            border_width=2,
            corner_radius=18,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            command=self.select_video_format
        )
        self.video_btn.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        self._bind_hover_glow(self.video_btn)

        self.audio_btn = ctk.CTkButton(
            format_frame,
            text="🎵 صوت نقي (MP3)",
            height=58,
            fg_color=LIGHT_PANEL,
            hover_color="#1f2b3a",
            text_color=TEXT,
            border_color=BORDER,
            border_width=2,
            corner_radius=18,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            command=self.select_audio_format
        )
        self.audio_btn.grid(row=0, column=1, padx=12, pady=12, sticky="ew")
        self._bind_hover_glow(self.audio_btn)

        # =========================
        # Status and progress
        # =========================
        status_title = ctk.CTkLabel(
            main,
            text="حالة التشغيل",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=TEXT,
            anchor="w"
        )
        status_title.grid(row=6, column=0, padx=28, pady=(10, 4), sticky="w")

        self.status_var = ctk.StringVar(value="جاهز للاستقبال")
        self.status_label = ctk.CTkLabel(
            main,
            textvariable=self.status_var,
            font=ctk.CTkFont(family="Segoe UI", size=16),
            text_color=MUTED,
            anchor="w",
            wraplength=760
        )
        self.status_label.grid(row=7, column=0, padx=28, pady=(0, 8), sticky="w")

        self.progress_var = ctk.DoubleVar(value=0)
        self.progress_bar = ctk.CTkProgressBar(
            main,
            variable=self.progress_var,
            mode="determinate",
            width=700,
            height=18,
            progress_color=GOLD,
            border_color=BORDER,
            fg_color="#1a2334",
        )
        self.progress_bar.grid(row=8, column=0, padx=28, pady=(8, 12), sticky="ew")

        self.progress_percent_label = ctk.CTkLabel(
            main,
            text="0%",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=GOLD_SOFT,
            anchor="e"
        )
        self.progress_percent_label.grid(row=8, column=0, padx=28, pady=(8, 12), sticky="e")

        # =========================
        # Main download button
        # =========================
        self.download_btn = ctk.CTkButton(
            main,
            text="⬇️ تنزيل الآن",
            height=64,
            fg_color=GOLD,
            hover_color=GOLD_DARK,
            text_color="#101419",
            border_color="#f5d27a",
            border_width=2,
            corner_radius=18,
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            command=self.start_download
        )
        self.download_btn.grid(row=9, column=0, padx=28, pady=(10, 10), sticky="ew")
        self._bind_hover_glow(self.download_btn)

        # footer spacer
        spacer = ctk.CTkLabel(main, text="", fg_color="transparent")
        spacer.grid(row=12, column=0, sticky="nsew")

        # =========================
        # Footer: exact Arabic brand
        # =========================
        footer_row = ctk.CTkFrame(main, fg_color="transparent")
        footer_row.grid(row=13, column=0, padx=28, pady=(8, 18), sticky="ew")

        footer_row.grid_columnconfigure(0, weight=1)
        footer_row.grid_columnconfigure(1, weight=0)
        footer_row.grid_columnconfigure(2, weight=0)

        footer_label = ctk.CTkLabel(
            footer_row,
            text="تم صنع هذا البرنامج بواسطة المطور",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#f1e9d9",
            anchor="e"
        )
        footer_label.grid(row=0, column=0, sticky="e")

        badge = create_verification_badge(footer_row, width=24, height=24, text="✓")
        badge.grid(row=0, column=1, padx=(8, 6), sticky="e")

        mehdi_label = ctk.CTkLabel(
            footer_row,
            text="MEHDI",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=BLUE_LIGHT,
            anchor="e"
        )
        mehdi_label.grid(row=0, column=2, sticky="e")

        self.select_video_format()

    def _bind_hover_glow(self, button):
        original_fg = button.cget("fg_color")
        original_border = button.cget("border_color")
        original_text = button.cget("text_color")

        def on_enter(event=None):
            try:
                button.configure(fg_color=button.cget("hover_color"))
                button.configure(border_color="#fff0b3")
                button.configure(text_color="#101419")
                try:
                    button.lift()
                except Exception:
                    pass
            except Exception:
                pass

        def on_leave(event=None):
            try:
                button.configure(fg_color=original_fg)
                button.configure(border_color=original_border)
                button.configure(text_color=original_text)
            except Exception:
                pass

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

    def pulse_animation(self):
        try:
            if not self.winfo_exists():
                return
            current = self.title_label.cget("text_color")
            next_color = GOLD_SOFT if current == GOLD else GOLD
            self.title_label.configure(text_color=next_color)
            self.title_shadow.configure(text_color="#5d430e")
            self.after(700, self.pulse_animation)
        except Exception:
            pass

    def paste_from_clipboard(self):
        play_click_sound()
        clipboard_content = get_clipboard_text()
        if clipboard_content:
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, clipboard_content)
            self.set_status("تم لصق الرابط من الحافظة بنجاح.")
            self.status_label.configure(text_color=SUCCESS)
        else:
            self.set_status("الحافظة فارغة أو لا تحتوي على نص.")
            self.status_label.configure(text_color=MUTED)

    def change_download_path(self):
        play_click_sound()
        try:
            selected_path = filedialog.askdirectory(
                title="اختر مجلد التنزيل",
                initialdir=self.custom_download_path
            )

            if selected_path and os.path.isdir(selected_path):
                self.custom_download_path = selected_path
                self.active_path_label.configure(
                    text=f"مسار التنزيل الحالي: {format_path_for_display(selected_path, 50)}"
                )
                self.set_status("تم تغيير المجلد بنجاح")
                self.status_label.configure(text_color=SUCCESS)
            else:
                self.set_status("لم يتم اختيار مجلد صحيح.")
                self.status_label.configure(text_color=MUTED)
        except Exception as e:
            self.set_status(f"خطأ في اختيار المجلد: {str(e)[:80]}")
            self.status_label.configure(text_color=DANGER)

    def select_video_format(self):
        play_click_sound()
        self.current_format = "video"
        self.video_btn.configure(
            fg_color=GOLD,
            text_color="#101419",
            hover_color=GOLD_DARK,
            border_color="#f5d27a",
            border_width=2
        )
        self.audio_btn.configure(
            fg_color=LIGHT_PANEL,
            text_color=TEXT,
            hover_color="#1d2638",
            border_color=BORDER,
            border_width=2
        )
        self.status_var.set("تم تحديد: فيديو بأعلى جودة (MP4)")
        self.status_label.configure(text_color=SUCCESS)

    def select_audio_format(self):
        play_click_sound()
        self.current_format = "audio"
        self.audio_btn.configure(
            fg_color=GOLD,
            text_color="#101419",
            hover_color=GOLD_DARK,
            border_color="#f5d27a",
            border_width=2
        )
        self.video_btn.configure(
            fg_color=LIGHT_PANEL,
            text_color=TEXT,
            hover_color="#1d2638",
            border_color=BORDER,
            border_width=2
        )
        self.status_var.set("تم تحديد: صوت نقي (MP3)")
        self.status_label.configure(text_color=SUCCESS)

    def set_status(self, msg):
        if not self.winfo_exists():
            return
        self.status_var.set(msg)
        is_error = "خطأ" in msg or "فشل" in msg
        self.status_label.configure(text_color=DANGER if is_error else TEXT)

    def update_progress(self, percent, status=None):
        try:
            if not self.winfo_exists():
                return
            percent = max(0, min(percent, 100))
            self.progress_var.set(percent / 100)
            self.progress_percent_label.configure(text=f"{int(percent)}%")
            if status:
                self.set_status(status)
        except Exception:
            pass

    def on_download_finished(self):
        try:
            if self.winfo_exists():
                self.download_btn.configure(state="normal", text="⬇️ تنزيل الآن")
                self.status_label.configure(text_color=SUCCESS)
        except Exception:
            pass

    def on_download_failed(self):
        try:
            if self.winfo_exists():
                self.download_btn.configure(state="normal", text="⬇️ تنزيل الآن")
        except Exception:
            pass

    def start_download(self):
        play_click_sound()

        url = self.url_entry.get().strip()
        if not is_valid_youtube_url(url):
            self.set_status("يرجى إدخال رابط YouTube صحيح.")
            self.status_label.configure(text_color=DANGER)
            self.update_progress(0, "يرجى إدخال رابط YouTube صحيح.")
            return

        if self.download_worker is not None and self.download_worker._thread is not None and self.download_worker._thread.is_alive():
            self.set_status("هناك عملية تنزيل جارية بالفعل.")
            self.status_label.configure(text_color=MUTED)
            return

        self.download_btn.configure(state="disabled", text="جارٍ التحميل...")
        self.update_progress(0, "جارٍ التحقق من الرابط...")

        download_format = "mp3" if self.current_format == "audio" else "mp4"
        self.download_worker = DownloadWorker(
            self,
            url,
            download_format,
            self.custom_download_path
        )
        self.download_worker.start()


if __name__ == "__main__":
    try:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        app = HadiApp()
        app.mainloop()
    except Exception as e:
        message = f"فشل تشغيل التطبيق: {str(e)}"
        print(message)
        try:
            ctypes.windll.user32.MessageBoxW(0, message, "الهادي", 0x10)
        except Exception:
            pass
        sys.exit(1)
