import os
import re
import sys
import threading
import time
import ctypes
import subprocess
import shutil
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from tkinter import filedialog

import customtkinter as ctk
import yt_dlp
import winsound
import tkinter as tk


# =========================
# إعدادات التطبيق
# =========================
APP_NAME = "الهادي"
WINDOW_WIDTH = 950
WINDOW_HEIGHT = 1050
DARK_BG = "#0b0f19"
DARK_PANEL = "#121a2a"
LIGHT_PANEL = "#171f2f"
GOLD = "#cca43b"
GOLD_DARK = "#a77e1f"
GOLD_SOFT = "#d9bb6f"
TEXT = "#f4f1ea"
MUTED = "#b8b3a8"
SUCCESS = "#7ed89a"
DANGER = "#ff6b6b"
BORDER = "#2b3246"

# =========================
# Helpers
# =========================
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
    """استخراج النص من الحافظة العام للنظام"""
    try:
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        try:
            clipboard_text = root.clipboard_get()
            root.destroy()
            return clipboard_text
        except tk.TclError:
            root.destroy()
            return ""
    except Exception:
        return ""


def set_clipboard_text(text):
    """كتابة النص إلى الحافظة"""
    try:
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
    except Exception:
        pass


def is_valid_youtube_url(value: str) -> bool:
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


def sanitize_filename(name: str) -> str:
    if not name:
        return "download"
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    name = name.strip().strip(".")
    return name[:180] or "download"


def find_ffmpeg():
    """البحث عن FFmpeg في المسارات الشائعة"""
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


def format_path_for_display(path: str, max_length: int = 60) -> str:
    """تنسيق المسار للعرض"""
    if not path:
        return "غير محدد"
    if len(path) <= max_length:
        return path
    return "..." + path[-max_length:]


# =========================
# Downloader Thread
# =========================
class DownloadWorker:
    def __init__(self, app, url, file_type, download_path):
        self.app = app
        self.url = url
        self.file_type = file_type
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
            if not os.path.isdir(download_dir):
                os.makedirs(download_dir, exist_ok=True)

            # Configure yt-dlp options
            ydl_opts = {
                "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "quiet": False,
                "no_warnings": False,
                "ignoreerrors": False,
                "progress_hooks": [self._progress_hook],
                "extract_flat": False,
                "socket_timeout": 30,
                "retries": {"DEFAULT": 3, "http": 5, "https": 5},
            }

            # Set format based on file type
            if self.file_type == "video":
                ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                ydl_opts["merge_output_format"] = "mp4"
                ydl_opts["postprocessors"] = []
            else:  # audio/MP3
                ydl_opts["format"] = "bestaudio/best"
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ]

            ffmpeg_location = find_ffmpeg()
            if ffmpeg_location:
                ydl_opts["ffmpeg_location"] = ffmpeg_location

            if self._stop_event.is_set():
                self.app.set_status("تم إلغاء العملية.")
                self.app.update_progress(0, "تم إلغاء العملية.")
                return

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.app.set_status("جارٍ معالجة الفيديو...")
                self.app.update_progress(5, "جارٍ معالجة الفيديو...")
                
                ydl.download([self.url])

            self.app.set_status("اكتمل التحميل بنجاح.")
            self.app.update_progress(100, "اكتمل التحميل بنجاح.")
            self.app.on_download_finished()
        except Exception as exc:
            error_msg = str(exc)[:250]
            print(f"[ERROR] {error_msg}")
            self.app.set_status(f"حدث خطأ: {error_msg}")
            self.app.update_progress(0, f"فشل التحميل: {error_msg}")
            self.app.on_download_failed()

    def _progress_hook(self, d):
        if self._stop_event.is_set():
            raise Exception("Download cancelled by user")

        if d.get("status") == "downloading":
            try:
                percent_str = d.get("_percent_str", "0%").strip()
                percent_value = float(percent_str.rstrip("%")) if "%" in percent_str else 0
                percent_value = max(0, min(percent_value, 100))
            except (ValueError, AttributeError):
                percent_value = 0

            speed = d.get("_speed_str", "...").strip() if d.get("_speed_str") else "..."
            self.app.update_progress(int(percent_value), f"جارٍ التنزيل: {percent_str} - {speed}")

        elif d.get("status") == "finished":
            self.app.update_progress(95, "جارٍ معالجة الملف...")

        elif d.get("status") == "error":
            error = d.get("error", "Unknown error")
            self.app.set_status(f"خطأ في التنزيل: {str(error)[:100]}")
            self.app.update_progress(0, f"خطأ في التنزيل: {str(error)[:100]}")


# =========================
# Main App
# =========================
class HadiApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("الهادي")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.configure(fg_color=DARK_BG)

        self.download_worker = None
        self.current_format = "video"
        self.custom_download_path = ensure_download_folder(None)

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
        main.grid_rowconfigure(12, weight=1)

        # Header
        self.title_label = ctk.CTkLabel(
            main,
            text="🔵 الهَادِي",
            font=ctk.CTkFont(family="Segoe UI", size=42, weight="bold"),
            text_color=GOLD,
            fg_color="transparent"
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(30, 10), sticky="n")

        self.pulse_animation()

        # URL Entry Label
        url_label = ctk.CTkLabel(
            main,
            text="رابط الفيديو على يوتيوب",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=TEXT,
            anchor="w"
        )
        url_label.grid(row=1, column=0, padx=28, pady=(18, 8), sticky="w")

        # URL Entry with Paste Button Row
        entry_row = ctk.CTkFrame(main, fg_color="transparent")
        entry_row.grid(row=2, column=0, padx=28, pady=(0, 6), sticky="ew")
        entry_row.grid_columnconfigure(0, weight=1)
        entry_row.grid_columnconfigure(1, weight=0)

        self.url_entry = ctk.CTkEntry(
            entry_row,
            width=600,
            height=52,
            border_width=1,
            fg_color=DARK_PANEL,
            border_color=BORDER,
            text_color=TEXT,
            placeholder_text="https://www.youtube.com/watch?v=...",
            font=ctk.CTkFont(family="Segoe UI", size=17),
        )
        self.url_entry.grid(row=0, column=0, padx=(0, 12), pady=0, sticky="ew")

        # Paste Button
        self.paste_btn = ctk.CTkButton(
            entry_row,
            text="📋 لصق الرابط",
            width=120,
            height=52,
            fg_color=GOLD,
            hover_color=GOLD_DARK,
            text_color="#101419",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            corner_radius=12,
            command=self.paste_from_clipboard
        )
        self.paste_btn.grid(row=0, column=1, padx=0, pady=0, sticky="e")

        # Download Path Display
        path_text = "📂 مسار حفظ الملفات: سطح المكتب ➔ مجلد (تنزيلات الهادي)"
        
        self.path_label = ctk.CTkLabel(
            main,
            text=path_text,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=GOLD_SOFT,
            anchor="w",
            wraplength=750
        )
        self.path_label.grid(row=3, column=0, padx=28, pady=(2, 6), sticky="w")

        # Active Download Path with Change Button Row
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
        self.active_path_label.grid(row=0, column=0, padx=(0, 12), pady=0, sticky="w")

        self.change_path_btn = ctk.CTkButton(
            path_row,
            text="📂 تغيير المجلد",
            width=130,
            height=40,
            fg_color=GOLD,
            hover_color=GOLD_DARK,
            text_color="#101419",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            corner_radius=10,
            command=self.change_download_path
        )
        self.change_path_btn.grid(row=0, column=1, padx=0, pady=0, sticky="e")

        # Format switch
        format_frame = ctk.CTkFrame(main, fg_color=LIGHT_PANEL, corner_radius=20)
        format_frame.grid(row=5, column=0, padx=28, pady=(6, 12), sticky="ew")

        format_frame.grid_columnconfigure(0, weight=1)
        format_frame.grid_columnconfigure(1, weight=1)

        self.video_btn = ctk.CTkButton(
            format_frame,
            text="🎞️ فيديو بأعلى جودة (MP4)",
            height=58,
            fg_color=GOLD,
            hover_color=GOLD_DARK,
            text_color="#101419",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            corner_radius=18,
            command=self.select_video_format
        )
        self.video_btn.grid(row=0, column=0, padx=12, pady=12, sticky="ew")

        self.audio_btn = ctk.CTkButton(
            format_frame,
            text="🎵 صوت نقي (MP3)",
            height=58,
            fg_color=LIGHT_PANEL,
            hover_color="#1d2638",
            text_color=TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            corner_radius=18,
            border_width=1,
            border_color=BORDER,
            command=self.select_audio_format
        )
        self.audio_btn.grid(row=0, column=1, padx=12, pady=12, sticky="ew")

        # Status + progress
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
            wraplength=750
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

        # Download button
        self.download_btn = ctk.CTkButton(
            main,
            text="⬇️ تنزيل الآن",
            height=64,
            fg_color=GOLD,
            hover_color=GOLD_DARK,
            text_color="#101419",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            corner_radius=18,
            command=self.start_download
        )
        self.download_btn.grid(row=9, column=0, padx=28, pady=(10, 10), sticky="ew")

        # Spacer
        spacer = ctk.CTkLabel(main, text="", fg_color="transparent")
        spacer.grid(row=12, column=0, sticky="nsew")

        # Footer badge
        self.footer_badge = ctk.CTkLabel(
            main,
            text="المطور: mehdi 🔵",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=GOLD,
            anchor="e"
        )
        self.footer_badge.grid(row=13, column=0, padx=28, pady=(6, 18), sticky="e")

        # Set initial format
        self.select_video_format()

    def pulse_animation(self):
        """تأثير نبض الذهب على العنوان"""
        try:
            if not self.winfo_exists():
                return
            current_color = self.title_label.cget("text_color")
            if current_color == GOLD:
                self.title_label.configure(text_color=GOLD_SOFT)
            else:
                self.title_label.configure(text_color=GOLD)
            self.after(650, self.pulse_animation)
        except Exception:
            pass

    def paste_from_clipboard(self):
        """لصق النص من الحافظة إلى حقل الإدخال"""
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
        """تغيير مسار التنزيل المخصص"""
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
                self.set_status(f"تم تغيير المجلد بنجاح إلى: {format_path_for_display(selected_path, 40)}")
                self.status_label.configure(text_color=SUCCESS)
            else:
                self.set_status("لم يتم اختيار مجلد صحيح.")
                self.status_label.configure(text_color=MUTED)
        except Exception as e:
            self.set_status(f"خطأ في اختيار المجلد: {str(e)[:100]}")
            self.status_label.configure(text_color=DANGER)

    def select_video_format(self):
        play_click_sound()
        self.current_format = "video"
        self.video_btn.configure(fg_color=GOLD, text_color="#101419", hover_color=GOLD_DARK, border_width=0)
        self.audio_btn.configure(fg_color=LIGHT_PANEL, text_color=TEXT, hover_color="#1d2638", border_width=1, border_color=BORDER)
        self.status_var.set("تم تحديد: فيديو بأعلى جودة (MP4)")
        self.status_label.configure(text_color=SUCCESS)

    def select_audio_format(self):
        play_click_sound()
        self.current_format = "audio"
        self.audio_btn.configure(fg_color=GOLD, text_color="#101419", hover_color=GOLD_DARK, border_width=0)
        self.video_btn.configure(fg_color=LIGHT_PANEL, text_color=TEXT, hover_color="#1d2638", border_width=1, border_color=BORDER)
        self.status_var.set("تم تحديد: صوت نقي (MP3)")
        self.status_label.configure(text_color=SUCCESS)

    def set_status(self, msg):
        if not self.winfo_exists():
            return
        self.status_var.set(msg)
        self.status_label.configure(text_color=TEXT if "خطأ" not in msg and "فشل" not in msg else DANGER)

    def update_progress(self, percent, status=None):
        """تحديث شريط التقدم والنسبة المئوية"""
        try:
            if not self.winfo_exists():
                return
            percent = max(0, min(percent, 100))
            self.progress_var.set(percent / 100)
            self.progress_percent_label.configure(text=f"{percent}%")
            if status:
                self.set_status(status)
        except Exception:
            pass

    def on_download_finished(self):
        """استدعاء عند انتهاء التحميل بنجاح"""
        try:
            if self.winfo_exists():
                self.download_btn.configure(state="normal", text="⬇️ تنزيل الآن")
                self.status_var.set("اكتمل التحميل بنجاح ✓")
                self.status_label.configure(text_color=SUCCESS)
        except Exception:
            pass

    def on_download_failed(self):
        """استدعاء عند فشل التحميل"""
        try:
            if self.winfo_exists():
                self.download_btn.configure(state="normal", text="⬇️ تنزيل الآن")
        except Exception:
            pass

    def start_download(self):
        """بدء عملية التحميل"""
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
        self.download_worker = DownloadWorker(self, url, self.current_format, self.custom_download_path)
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
