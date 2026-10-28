# -*- coding: utf-8 -*-
"""Media Downloader v0.3 - TikTok / YouTube / Spotify"""
import os
import re
import sys
import queue
import shutil
import ctypes
import threading
import subprocess
import io
import tempfile
import urllib.request
import json
import hashlib
from urllib.parse import urlsplit
import tkinter as tk

CREATE_NO_WINDOW = 0x08000000
_startupinfo = subprocess.STARTUPINFO()
_startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
_startupinfo.wShowWindow = 0  # SW_HIDE

import requests
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageOps

APP_TITLE = "Media Downloader"
APP_VER = "v0.3"
BG = "#242933"
CARD = "#292f39"
CARD_HOVER = "#343c49"
TEXT = "#e8eaf2"
MUTED = "#8b91a7"
ACCENT = "#5277b5"
SEL_BG = "#153257"
GREEN = "#68bd94"
RED = "#f66"
SPOTIFY = "#1db954"
TIKTOK = "#111111"
YOUTUBE = "#ff0033"

MAX_THREADS = 1  # one progress bar and one status label — parallel jobs fight over them


def res_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def exe(name):
    # frozen: binaries are extracted next to the app; source: they live in build_bin/
    for folder in (res_dir(), os.path.join(res_dir(), "build_bin")):
        p = os.path.join(folder, name)
        if os.path.exists(p):
            return p
    raise RuntimeError("Не знайдено %s (поклади у build_bin або поруч із програмою)." % name)


DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads") if getattr(sys, "frozen", False) else os.path.join(res_dir(), "Downloads")
THUMBS = os.path.join(tempfile.gettempdir(), "mediadl_thumbs")
os.makedirs(THUMBS, exist_ok=True)


def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|]+', "", name or "media").strip()[:120].strip(" .")
    return name or "media"


def asset(name):
    return os.path.join(res_dir(), "assets", name)


def saved_text(dest):
    return "Готово! Файли в папці %s." % (os.path.basename(os.path.normpath(dest)) or dest)


def platform_for(url):
    try:
        host = (urlsplit(url.strip()).hostname or "").lower()
    except ValueError:
        return None
    for domain, platform in (("spotify.com", "spotify"), ("tiktok.com", "tiktok"),
                             ("youtube.com", "youtube"), ("youtu.be", "youtube")):
        if host == domain or host.endswith("." + domain):
            return platform
    return None


def publish_file(staged, dest, name):
    """Publish a complete staged file without replacing existing Windows files."""
    stem, ext = os.path.splitext(name)
    index = 0
    while True:
        target = os.path.join(dest, name if not index else "%s (%d)%s" % (stem, index, ext))
        try:
            # Windows rename is atomic and fails if the destination already exists.
            os.rename(staged, target)
            return target
        except FileExistsError:
            index += 1


def download_file(url, dest, name):
    with tempfile.TemporaryDirectory(prefix=".mediadl-", dir=dest) as work:
        staged = os.path.join(work, name)
        content = http_get(url, binary=True)
        with open(staged, "wb") as fh:
            fh.write(content)
        return publish_file(staged, dest, name)


# ---------------------------------------------------------------- utilities

def http_get(url, timeout=30, binary=False):
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    if binary:
        return r.content
    return r.text


def extract_embedded_cover(mp3_path, out_png):
    try:
        import mutagen
        from mutagen.id3 import ID3
        tags = ID3(mp3_path)
        for key in tags.getall("APIC"):
            data = key.data
            img = Image.open(io.BytesIO(data))
            img.thumbnail((200, 200))
            img.convert("RGB").save(out_png)
            return True
    except Exception:
        pass
    return False


def make_placeholder(kind, color, size=(200, 200)):
    """Flat placeholder drawn with shapes (font glyphs are not reliable)."""
    img = Image.new("RGB", size, color)
    d = ImageDraw.Draw(img)
    w, h = size
    fg = "#5d6684"
    if kind == "music":
        r = int(w * 0.032)
        for cx, cy, top in ((0.44, 0.60, 0.38), (0.60, 0.55, 0.33)):
            d.ellipse([w * cx - r, h * cy - r, w * cx + r, h * cy + r], fill=fg)
            d.rectangle([w * cx + r * 0.55, h * top, w * cx + r * 1.3, h * cy], fill=fg)
        d.polygon([(w * 0.47, h * 0.40), (w * 0.62, h * 0.36), (w * 0.62, h * 0.42),
                   (w * 0.47, h * 0.46)], fill=fg)
    else:
        d.polygon([(w * 0.45, h * 0.36), (w * 0.45, h * 0.64), (w * 0.62, h * 0.50)],
                  fill=fg)
    return img


def load_thumbnail(path, url=None):
    """Load a PIL thumbnail in a worker; this function never touches Tk."""
    stat = os.stat(path)
    identity = "v4:%s:%s:%s" % (os.path.abspath(path), stat.st_size, stat.st_mtime_ns)
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    png = os.path.join(THUMBS, key + ".png")
    if not os.path.exists(png):
        ext = os.path.splitext(path)[1].lower()
        done = False
        if url and url.startswith("http"):
            try:
                img = Image.open(io.BytesIO(http_get(url, binary=True)))
                img.thumbnail((200, 200))
                img.convert("RGB").save(png)
                done = True
            except Exception:
                pass
        if not done and ext == ".mp3":
            done = extract_embedded_cover(path, png)
        if not done and ext in (".jpg", ".jpeg", ".png", ".webp"):
            try:
                img = Image.open(path)
                img.thumbnail((200, 200))
                img.convert("RGB").save(png)
                done = True
            except Exception:
                pass
        if not done and ext in (".mp4", ".mkv", ".webm"):
            try:
                result = subprocess.run(
                    [exe("ffmpeg.exe"), "-y", "-ss", "0", "-i", path,
                     "-frames:v", "1", "-vf", "scale=200:-1", png],
                    capture_output=True, timeout=10,
                    startupinfo=_startupinfo, creationflags=CREATE_NO_WINDOW)
                done = result.returncode == 0 and os.path.isfile(png)
            except Exception:
                pass
        if not done:
            make_placeholder("music" if ext == ".mp3" else "video", CARD_HOVER).save(png)
    try:
        with Image.open(png) as source:
            return tile_preview(source)
    except Exception:
        return None


def tile_preview(source):
    """Uniform crop and a legible play badge, composited without Tk backgrounds."""
    im = ImageOps.fit(source.convert("RGBA"), (CARD_W * 2, CARD_H * 2), Image.LANCZOS)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=14, fill=255)
    im.putalpha(mask)
    overlay = Image.new("RGBA", im.size)
    draw = ImageDraw.Draw(overlay)
    cx, cy, radius = im.width // 2, im.height // 2, 20
    draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=(9, 15, 24, 155))
    draw.polygon(((cx-5, cy-9), (cx-5, cy+9), (cx+9, cy)), fill=(245, 248, 255, 240))
    return Image.alpha_composite(im, overlay)


class DownloadEngine:
    """Runs downloads in background threads, pushes events to a queue."""

    def __init__(self, events: queue.Queue):
        self.events = events
        self.busy = 0
        self.lock = threading.Lock()

    def send(self, **kv):
        kv["type"] = kv.get("type", "status")
        self.events.put(kv)

    def start(self, url, mp3, dest):
        url = url.strip()
        if not url:
            return
        if not url.lower().startswith(("http://", "https://")):
            self.send(type="status", text="Потрібне http(s)-посилання.", color=RED)
            return
        with self.lock:
            if self.busy >= MAX_THREADS:
                self.send(type="status", text="Зачекай — ще виконується завантаження.", color=RED)
                return
            self.busy += 1
        threading.Thread(target=self._run, args=(url, mp3, dest), daemon=True).start()

    def _run(self, url, mp3, dest):
        try:
            os.makedirs(dest, exist_ok=True)
            platform = platform_for(url)
            if platform == "spotify":
                self._spotify(url, dest)
            elif platform == "tiktok" and "/video/" not in urlsplit(url).path:
                self._tiktok_photo(url, dest, mp3)
            else:
                self._ytdlp(url, dest, mp3)
        except subprocess.CalledProcessError:
            self.send(type="done", ok=False, text="Помилка при завантаженні. Спробуй ще раз.")
        except Exception as e:
            self.send(type="done", ok=False, text="Помилка: %s" % str(e)[:120])
        finally:
            with self.lock:
                self.busy -= 1

    # -- yt-dlp (youtube, tiktok video, etc.)
    def _ytdlp(self, url, dest, mp3):
        yt_exe = exe("yt-dlp.exe")
        auto_name = os.path.join(dest, "%(title)s.%(ext)s")
        cmd = [yt_exe, "--ffmpeg-location", exe("ffmpeg.exe"),
               "--js-runtimes", "deno:" + exe("deno.exe"),
               "--newline", "--no-playlist",
               "-o", auto_name]
        if mp3:
            cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0",
                    "--embed-thumbnail", "--add-metadata"]
        else:
            cmd += ["-f", "bv*+ba/b", "--merge-output-format", "mp4"]
        cmd.append(url)
        self.send(type="status", text="З'єднання..." if not mp3 else "Конвертація в MP3...", color=MUTED)
        self._pipe_ytdlp(cmd, url, dest)

    def _pipe_ytdlp(self, cmd, url, dest):
        before = set(self._scan(dest))
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                startupinfo=_startupinfo, creationflags=CREATE_NO_WINDOW)
        last_error = None
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("ERROR:"):
                last_error = line[6:].strip()
            m = re.search(r"\[download\]\s+Destination:\s+(.*)", line)
            if m:
                self.send(type="progress", value=0)
            m = re.search(r"\[download\]\s+([\d.]+)%", line)
            if m:
                self.send(type="progress", value=float(m.group(1)))
        proc.wait()
        proc.stdout.close()
        new = [f for f in self._scan(dest) if f not in before]
        if proc.returncode == 0:
            thumb = self._ytdlp_thumb(url)
            self.send(type="done", ok=True, text=saved_text(dest), files=[(os.path.join(dest, f), thumb) for f in new], dest=dest)
        else:
            self.send(type="done", ok=False,
                      text="Помилка: %s" % (last_error or "код %d" % proc.returncode)[:160])

    def _scan(self, dest):
        """Media files currently in dest, ignoring yt-dlp partial artefacts."""
        try:
            return {f for f in os.listdir(dest)
                    if f.lower().endswith((".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".opus",
                                           ".jpg", ".jpeg", ".png", ".webp"))}
        except OSError:
            return set()

    def _ytdlp_thumb(self, url):
        m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url or "")
        if m:
            return "https://i.ytimg.com/vi/%s/mqdefault.jpg" % m.group(1)
        return None

    # -- spotify
    def _spotify(self, url, dest):
        self.send(type="status", text="Spotify: шукаю та завантажую...", color=MUTED)
        cmd = [exe("spotdl.exe"), "download", url, "--output", dest,
               "--threads", "3", "--ffmpeg", exe("ffmpeg.exe")]
        before = set(self._scan(dest))
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                startupinfo=_startupinfo, creationflags=CREATE_NO_WINDOW)
        total = None
        pos = 0
        for line in proc.stdout:
            line = line.strip()
            if not total and re.search(r"Found\s+(\d+)\s+song", line):
                total = int(re.search(r"Found\s+(\d+)", line).group(1))
            m = re.search(r"Downloading\s+(?:\"|\u201c)?", line)
            if m:
                pos += 1
                if total:
                    self.send(type="progress", value=100.0 * pos / total)
                    self.send(type="status", text="Spotify: %d з %d..." % (pos, total), color=MUTED)
            m = re.search(r"Already\s+downloaded", line)
            if m:
                pos += 1
        proc.wait()
        proc.stdout.close()
        new = [f for f in self._scan(dest) if f not in before]
        self.send(type="done", ok=proc.returncode == 0,
                  text=saved_text(dest) if proc.returncode == 0 else "Помилка Spotify (див. журнал).",
                  files=[(os.path.join(dest, f), None) for f in new], dest=dest)

    # -- tiktok slideshow
    def _tiktok_photo(self, url, dest, mp3=False):
        self.send(type="status", text="TikTok: отримую фото...", color=MUTED)
        r = requests.get("https://www.tikwm.com/api/", params={"url": url}, timeout=30,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0 or not data.get("data"):
            raise RuntimeError("TikTok: " + str(data.get("msg", "не вдалось")))
        d = data["data"]
        # Shared TikTok links can resolve to videos. Keep yt-dlp's format handling.
        if not d.get("images"):
            return self._ytdlp(url, dest, mp3)
        title = sanitize(d.get("title"))
        files = []
        try:
            images = d["images"]
            if not mp3:
                for i, img_url in enumerate(images, 1):
                    self.send(type="progress", value=100.0 * i / len(images))
                    self.send(type="status", text="TikTok: фото %d з %d..." % (i, len(images)), color=MUTED)
                    match = re.search(r"\.(png|jpeg|webp)(\?|$)", img_url or "")
                    ext = match.group(1) if match else "jpg"
                    files.append(download_file(img_url, dest, "%s_%02d.%s" % (title, i, ext)))
                if d.get("play"):
                    files.append(download_file(d["play"], dest, title + ".mp4"))
            if d.get("music"):
                with tempfile.TemporaryDirectory(prefix=".mediadl-", dir=dest) as work:
                    tmp = os.path.join(work, "source.audio")
                    with open(tmp, "wb") as fh:
                        fh.write(http_get(d["music"], binary=True))
                    name = title + " (audio).mp3"
                    audio = os.path.join(work, name)
                    conv = subprocess.run([exe("ffmpeg.exe"), "-y", "-i", tmp, "-q:a", "0", audio],
                                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                                          startupinfo=_startupinfo, creationflags=CREATE_NO_WINDOW)
                    if conv.returncode != 0:
                        detail = (conv.stderr or "FFmpeg: код %d" % conv.returncode).strip()[-180:]
                        raise RuntimeError("Не вдалося створити MP3: " + detail)
                    files.append(publish_file(audio, dest, name))
            elif mp3:
                raise RuntimeError("TikTok: у цьому дописі немає аудіо.")
            if not files:
                raise RuntimeError("TikTok: файлів для завантаження не знайдено.")
        except Exception as error:
            prefix = "Збережено %d файл(ів), але " % len(files) if files else ""
            self.send(type="done", ok=False, text=prefix + str(error)[:180],
                      files=[(f, None) for f in files], dest=dest)
            return
        self.send(type="done", ok=True, text=saved_text(dest), files=[(f, None) for f in files], dest=dest)

# ---------------------------------------------------------------- UI

FONT = "Segoe UI"
BORDER = "#414956"
SEG_ACTIVE = SEL_BG
CARD_W, CARD_H = 84, 53


def icon_image(size, draw_fn):
    """Draw a small icon at 4x and downscale so the edges stay smooth."""
    s = 4
    img = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(img), s, size * s)
    img = img.resize((size, size), Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


def search_icon(color=MUTED, size=15):
    def draw(d, s, S):
        w = max(2, int(1.5 * s))
        r = int(S * 0.30)
        c = int(S * 0.44)
        d.ellipse([c - r, c - r, c + r, c + r], outline=color, width=w)
        d.line([c + int(r * 0.70), c + int(r * 0.70), S - int(3 * s), S - int(3 * s)],
               fill=color, width=w)
    return icon_image(size, draw)


def check_icon(color=GREEN, size=17):
    def draw(d, s, S):
        w = max(2, int(1.1 * s))
        d.ellipse([w, w, S - w - 1, S - w - 1], outline=color, width=w)
        d.line([int(S * .27), int(S * .52), int(S * .44), int(S * .68), int(S * .73), int(S * .33)],
               fill=color, width=w, joint="curve")
    return icon_image(size, draw)


def dot_icon(color=MUTED, size=17):
    def draw(d, s, S):
        r = int(S * 0.22)
        d.ellipse([S // 2 - r, S // 2 - r, S // 2 + r, S // 2 + r], fill=color)
    return icon_image(size, draw)


def warn_icon(color="#ff8d8d", size=17):
    def draw(d, s, S):
        w = max(2, int(1.1 * s))
        d.ellipse([w, w, S - w - 1, S - w - 1], outline=color, width=w)
        d.line([S // 2, int(S * .30), S // 2, int(S * .58)], fill=color, width=w)
        d.ellipse([S // 2 - w // 2, int(S * .70), S // 2 + w // 2 + 1, int(S * .70) + w],
                  fill=color)
    return icon_image(size, draw)


def white_icon(name, size=(24, 24)):
    """Recolor a dark-on-transparent asset to white, keeping its alpha."""
    png = os.path.join(THUMBS, "uiw_" + name)
    im = Image.open(asset(name)).convert("RGBA")
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            px[x, y] = (255, 255, 255, px[x, y][3])
    im.save(png)
    return ctk.CTkImage(light_image=im, dark_image=im, size=size)


def format_icon(music=False):
    def draw(d, s, S):
        if music:
            for x, height in ((.15, .18), (.32, .42), (.5, .72), (.68, .5), (.85, .24)):
                cx, half = int(S * x), int(S * height / 2)
                d.line((cx, S // 2 - half, cx, S // 2 + half), fill="#c9d3e3", width=2*s)
        else:
            d.rounded_rectangle((s, 4*s, S-s-1, S-4*s), radius=4*s,
                                outline="#b4c8e6", width=2*s)
            font = ImageFont.truetype("segoeuib.ttf", 12*s)
            d.text((S/2, S/2), "HD", fill="#d5e3f7", font=font, anchor="mm")
    return icon_image(30, draw)


def folder_action_icon():
    def draw(d, s, S):
        d.line([(2*s, 5*s), (2*s, 3*s), (6*s, 3*s), (8*s, 5*s),
                (12*s, 5*s), (12*s, 11*s), (2*s, 11*s), (2*s, 5*s), (12*s, 5*s)],
               fill="#e3eaf5", width=max(1, int(1.3*s)), joint="curve")
    return icon_image(14, draw)


class Tooltip:
    """Small hover label used for full file names and the download path."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry("+%d+%d" % (x, y))
        tk.Label(self.tip, text=self.text, bg="#2c3244", fg=TEXT, padx=8, pady=4,
                 font=(FONT, 9), wraplength=340, justify="left").pack()

    def hide(self, event=None):
        if self.tip:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None


class GradientButton(ctk.CTkFrame):
    """Pill button with the mockup's blue→purple gradient.

    Rendered with Pillow, but focusable: Tab/Shift+Tab reach it, Enter and
    Space activate it, and keyboard focus draws a light ring around the pill.
    """

    def __init__(self, master, text, command, width=232, height=44):
        super().__init__(master, fg_color="transparent", width=width, height=height,
                         cursor="hand2")
        tk.Frame.configure(self, takefocus=1)  # CTkFrame does not accept takefocus itself
        self.pack_propagate(False)
        self._command = command
        self._btn_w, self._btn_h = width, height
        self._text = text
        self._enabled = True
        self._pressed = False
        self._state = "normal"
        self._cache = {}
        self._label = ctk.CTkLabel(self, image=self._image("normal"), text="",
                                   fg_color="transparent", cursor="hand2")
        self._label.pack(fill="both", expand=True)

        self._label.bind("<Enter>", self._on_enter)
        self._label.bind("<Leave>", self._on_leave)
        self._label.bind("<ButtonPress-1>", self._on_press)
        self._label.bind("<ButtonRelease-1>", self._on_release)
        # CTkFrame.bind() only reaches the internal canvas, so frame-level events
        # (focus, keys) must be bound on the tk.Frame widget itself.
        tk.Frame.bind(self, "<FocusIn>", lambda e: self._set_state("focus"))
        tk.Frame.bind(self, "<FocusOut>", lambda e: self._set_state("normal"))
        for seq in ("<Return>", "<KP_Enter>", "<space>"):
            tk.Frame.bind(self, seq, self._invoke)
        self.bind("<Button-1>", self._on_press)  # canvas = the visible pill surface

    # -- public
    def set_enabled(self, enabled, text=None):
        self._enabled = enabled
        self._pressed = False
        tk.Frame.configure(self, takefocus=1 if enabled else 0)
        if text is not None:
            self._text = text
        self._label.configure(cursor="hand2" if enabled else "arrow")
        self.configure(cursor="hand2" if enabled else "arrow")
        state = "disabled" if not enabled else ("focus" if self._has_focus() else "normal")
        self._set_state(state)

    # -- state
    def _has_focus(self):
        try:
            return self.focus_get() is self
        except Exception:
            return False

    def _set_state(self, state):
        self._state = state
        self._label.configure(image=self._image(state))

    def _image(self, state):
        if not self._enabled:
            state = "disabled"
        key = (self._text, state)
        img = self._cache.get(key)
        if img is None:
            img = self._cache[key] = self._render(self._text, state)
        return img

    def _on_enter(self, event=None):
        if self._enabled:
            self._set_state("hover")

    def _on_leave(self, event=None):
        if self._enabled:
            self._set_state("focus" if self._has_focus() else "normal")

    def _on_press(self, event=None):
        self.focus_set()
        if self._enabled:
            self._pressed = True
            self._set_state("press")

    def _on_release(self, event=None):
        pressed, self._pressed = self._pressed, False
        inside = event is None or (0 <= event.x < self._label.winfo_width()
                                   and 0 <= event.y < self._label.winfo_height())
        if self._enabled and pressed and inside:
            self._set_state("focus" if self._has_focus() else "hover")
            self._command()
        elif self._enabled:
            self._set_state("focus" if self._has_focus() else "normal")

    def _invoke(self, event=None):
        if self._enabled:
            self._command()
        return "break"

    # -- rendering
    def _render(self, text, state):
        s = 3  # supersample so the pill edge stays smooth
        w, h = self._btn_w * s, self._btn_h * s
        left, right = ((25, 78, 144), (105, 58, 145))
        if state == "hover":
            left, right = ((35, 94, 165), (123, 72, 164))
        elif state == "press":
            left, right = ((20, 63, 123), (88, 46, 126))
        elif state == "disabled":
            left, right = ((58, 64, 88), (84, 76, 110))

        strip = Image.new("RGB", (w, 1))
        px = strip.load()
        for x in range(w):
            t = x / (w - 1)
            px[x, 0] = tuple(int(left[i] + (right[i] - left[i]) * t) for i in range(3))
        grad = strip.resize((w, h))

        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=255)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        img.paste(grad, (0, 0), mask)

        if state == "focus":
            ring = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(ring).rounded_rectangle(
                [2 * s, 2 * s, w - 2 * s - 1, h - 2 * s - 1],
                radius=h // 2, outline=(226, 232, 255, 255), width=2 * s)
            img = Image.alpha_composite(img, ring)

        draw = ImageDraw.Draw(img)
        font = None
        for fname in ("seguisb.ttf", "segoeuib.ttf"):
            try:
                font = ImageFont.truetype(fname, 15 * s)
                break
            except Exception:
                pass
        if font is None:
            font = ImageFont.load_default()

        tint = (255, 255, 255, 255) if state != "disabled" else (176, 181, 202, 255)
        icon = None
        try:
            src = Image.open(asset("download.png")).convert("RGBA")
            icon = Image.new("RGBA", src.size, tint)
            icon.putalpha(src.getchannel("A"))
            icon = icon.resize((18 * s, 18 * s), Image.LANCZOS)
        except Exception:
            pass

        gap = 8 * s
        tw = draw.textlength(text, font=font)
        total = (icon.width + gap if icon else 0) + tw
        x = (w - total) / 2
        cy = h / 2
        if icon:
            img.paste(icon, (int(x), int(cy - icon.height / 2)), icon)
            x += icon.width + gap
        draw.text((x, cy), text, font=font, fill=tint, anchor="lm")
        return ctk.CTkImage(light_image=img, dark_image=img, size=(self._btn_w, self._btn_h))


class App(ctk.CTk):
    CONTENT_MAX = 570

    def __init__(self):
        super().__init__(fg_color=BG)
        self.title("%s %s" % (APP_TITLE, APP_VER))
        self.geometry("1024x600")
        self.minsize(520, 500)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self.events = queue.Queue()
        self.engine = DownloadEngine(self.events)
        self.selected_format = "video"
        self._status_ok = False
        self._tiles = []
        self._tile_paths = set()
        self._thumbnail_tasks = queue.Queue()
        self._result_dest = DOWNLOADS
        self._cols = 0
        self._pad = -1

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        try:
            self.iconbitmap(asset("app.ico"))
        except Exception:
            pass
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MediaDownloader.v03")
        except Exception:
            pass

        # --- header: compact folder label + settings gear (title is in the window bar)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(4, 0))

        self._settings_popup = None
        self.settings_button = ctk.CTkButton(header, text="⚙", width=32, height=28, corner_radius=8,
                      fg_color=CARD, hover_color=CARD_HOVER, text_color=MUTED,
                      font=(FONT, 17), command=self._open_settings)
        self.settings_button.pack(side="right")

        self.lbl_folder = ctk.CTkLabel(header, text="", font=(FONT, 11), text_color="#6b7186",
                                       cursor="hand2")
        self.lbl_folder.pack(side="right", padx=(0, 10))
        self.lbl_folder.bind("<Button-1>", lambda e: self._open_downloads(True))
        self._folder_tip = Tooltip(self.lbl_folder, DOWNLOADS)
        self._refresh_folder()

        # --- centred content column: max 570 px, shrinks on narrow windows
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="ew", pady=(0, 24))
        self.content.grid_columnconfigure(0, weight=1)
        self.bind("<Configure>", self._on_window_configure)

        # platform switcher: one pill, active platform gets a rounded background
        pill = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        pill.grid(row=0, column=0, pady=(0, 6))
        inner = ctk.CTkFrame(pill, fg_color="transparent")
        inner.pack(padx=5, pady=5)
        self._badges = {}
        self._badge_active = "#465163"
        for fname, key in (("yt.png", "youtube"), ("sp.png", "spotify"), ("tt.png", "tiktok")):
            png = os.path.join(THUMBS, "badge_" + fname)
            try:
                shutil.copy(asset(fname), png)
            except Exception:
                if not os.path.exists(png):
                    continue
            with Image.open(png) as source_image:
                badge_image = source_image.convert("RGBA")
            img = ctk.CTkImage(light_image=badge_image, dark_image=badge_image, size=(24, 24))
            box = ctk.CTkFrame(inner, fg_color="transparent", width=38, height=30,
                               corner_radius=8, cursor="hand2")
            box.pack(side="left", padx=2)
            box.pack_propagate(False)
            lbl = ctk.CTkLabel(box, image=img, text="", cursor="hand2")
            lbl.place(relx=0.5, rely=0.5, anchor="center")
            self._badges[key] = box
            for w in (box, lbl):
                w.bind("<Button-1>", lambda e: self._refocus())
                w.bind("<Enter>", lambda e, k=key: self._paint_badge(hover=k))
                w.bind("<Leave>", lambda e, k=key: self._paint_badge())
                w.bind("<ButtonPress-1>", lambda e, k=key: self._paint_badge(press=k))
                w.bind("<ButtonRelease-1>", lambda e, k=key: self._paint_badge(hover=k))
        self._active_platform = None

        # url field
        urlrow = ctk.CTkFrame(self.content, fg_color="#343b47", corner_radius=11,
                              border_width=1, border_color="#4b5361")
        urlrow.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(urlrow, image=search_icon(), text="").pack(side="left", padx=(14, 8))
        self.entry = ctk.CTkEntry(urlrow, placeholder_text="https://...", border_width=0,
                                  height=42, fg_color="transparent", font=(FONT, 15))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 20), pady=1)
        # hotkeys: CustomTkinter eats clipboard ones; operate on the real tk entry
        def sel_all(e):
            w = self.entry._entry
            w.select_range(0, "end")
            w.icursor("end")
            return "break"

        def paste(e):
            w = self.entry._entry
            try:
                data = self.clipboard_get()
            except Exception:
                return "break"
            try:
                if w.selection_present():
                    w.delete("sel.first", "sel.last")
            except Exception:
                pass
            w.insert("insert", data)
            w.xview("insert")
            self.after_idle(self._detect_source)
            return "break"

        def copy_(e):
            w = self.entry._entry
            try:
                if w.selection_present():
                    self.clipboard_clear()
                    self.clipboard_append(w.selection_get())
            except Exception:
                pass
            return "break"

        def cut(e):
            copy_(e)
            w = self.entry._entry
            try:
                if w.selection_present():
                    w.delete("sel.first", "sel.last")
                    self.after_idle(self._detect_source)
            except Exception:
                pass
            return "break"

        self.entry.bind("<Control-a>", sel_all)
        self.entry.bind("<Control-A>", sel_all)
        self.entry._entry.bind("<Control-a>", sel_all)
        self.entry._entry.bind("<Control-A>", sel_all)
        # explicit widget-level intercepts (fire BEFORE tk class bindings -> no double paste)
        self.entry._entry.bind("<Control-v>", paste)
        self.entry._entry.bind("<Control-V>", paste)
        self.entry._entry.bind("<Control-c>", copy_)
        self.entry._entry.bind("<Control-C>", copy_)
        self.entry._entry.bind("<Control-x>", cut)
        self.entry._entry.bind("<Control-X>", cut)
        # layout-independent router: physical keycodes (86=V, 67=C, 88=X, 65=A)
        def key_router(e):
            if not (e.state & 0x4):   # Ctrl held
                return None
            code = e.keycode
            if code == 86: return paste(e)
            if code == 67: return copy_(e)
            if code == 88: return cut(e)
            if code == 65: return sel_all(e)
            return None
        self.bind_all("<Control-KeyPress>", key_router, add="+")
        ctx = tk.Menu(self, tearoff=0)
        entry = self.entry._entry  # real tkinter Entry inside CTkEntry
        ctx.add_command(label="Вставити", command=lambda: entry.event_generate("<<Paste>>"))
        ctx.add_command(label="Копіювати", command=lambda: entry.event_generate("<<Copy>>"))
        ctx.add_command(label="Виділити все", command=lambda: entry.select_range(0, "end"))
        self.entry.bind("<Button-3>", lambda e: ctx.tk_popup(e.x_root, e.y_root))
        self.entry.bind("<Return>", lambda e: self.on_download())
        self.entry._entry.bind("<Return>", lambda e: self.on_download())
        self.entry.bind("<KeyRelease>", self._detect_source, add="+")
        self.entry._entry.bind("<KeyRelease>", self._detect_source, add="+")
        self.entry._entry.bind("<FocusIn>", lambda e: urlrow.configure(border_color=ACCENT), add="+")
        self.entry._entry.bind("<FocusOut>", lambda e: urlrow.configure(border_color=BORDER), add="+")

        ctk.CTkLabel(self.content, text="Встав посилання (TikTok / YouTube / Spotify)",
                     font=(FONT, 14), text_color=TEXT).grid(row=2, column=0, pady=(4, 8))

        # segmented Video / Music control: one frame, two equal halves
        seg = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=10,
                           border_width=1, border_color=BORDER)
        seg.grid(row=3, column=0, sticky="ew")
        seg.grid_columnconfigure((0, 1), weight=1, uniform="seg")
        seg.grid_rowconfigure(0, weight=1)
        try:
            vid_img = format_icon()
        except Exception:
            vid_img = None
        try:
            mus_img = format_icon(music=True)
        except Exception:
            mus_img = None
        try:
            self._pf_ico = folder_action_icon()
        except Exception:
            self._pf_ico = None
        self.card_mp4 = self._segment(seg, 0, "Відео MP4", "Найкраща якість", vid_img, "video", (4, 2))
        self.card_mp3 = self._segment(seg, 1, "Музика", "MP3", mus_img, "music", (2, 4))
        self.select_format("video")

        # download button (gradient pill, keyboard accessible)
        self.btn = GradientButton(self.content, "Завантажити", self.on_download)
        self.btn.grid(row=4, column=0, pady=(12, 12))

        # results card
        self.info = ctk.CTkFrame(self.content, fg_color="#21272d", corner_radius=12,
                                 height=144, border_width=1, border_color="#3b4650")
        self.info.grid(row=5, column=0, sticky="ew")
        self.info.grid_propagate(False)
        self.info.grid_columnconfigure(0, weight=1)
        self.info.grid_rowconfigure(1, weight=1)

        # status row: green when done, red on error, neutral while working
        self._ico_check = check_icon()
        self._ico_warn = warn_icon()
        self._ico_dot = dot_icon()
        self.status = ctk.CTkFrame(self.info, fg_color="transparent", corner_radius=8)
        self.status.grid(row=0, column=0, sticky="ew", padx=1, pady=(1, 0))
        self.status.grid_columnconfigure(0, weight=1)
        srow = ctk.CTkFrame(self.status, fg_color="transparent")
        srow.grid(row=0, column=0, pady=9)
        self.lbl_icon = ctk.CTkLabel(srow, image=self._ico_check, text="", width=18)
        self.lbl_icon.pack(side="left", padx=(0, 7))
        self.lbl_status = ctk.CTkLabel(srow, text="", font=(FONT, 14), text_color=MUTED,
                                       wraplength=500, justify="left")
        self.lbl_status.pack(side="left")
        self.progress = ctk.CTkProgressBar(self.status, height=3, corner_radius=0,
                                           progress_color=ACCENT, fg_color="#2a3142")
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew")
        self.progress.grid_remove()
        self.status.grid_remove()
        for w in (self.status, srow, self.lbl_status):
            w.bind("<Button-1>", lambda e: self._open_downloads())

        self.gallery = ctk.CTkScrollableFrame(self.info, fg_color="transparent",
                                              scrollbar_button_color="#2f3650",
                                              scrollbar_button_hover_color="#3a4460")
        self.gallery.grid(row=1, column=0, sticky="nsew", padx=3, pady=7)
        self.gallery.grid_remove()
        self.gallery._parent_canvas.configure(yscrollcommand=self._gallery_scroll)
        for c in range(6):
            self.gallery.grid_columnconfigure(c, weight=0)

        self._empty = ctk.CTkFrame(self.info, fg_color="transparent")
        self._empty.grid(row=1, column=0, sticky="nsew", padx=8, pady=10)
        empty_content = ctk.CTkFrame(self._empty, fg_color="transparent")
        empty_content.pack(expand=True)
        ctk.CTkLabel(empty_content, text="Завантажень у цій сесії ще немає",
                     font=(FONT, 14), text_color="#a4afbf").pack()
        ctk.CTkLabel(empty_content, text="Встав посилання та натисни «Завантажити»",
                     font=(FONT, 12), text_color="#788597").pack(pady=(4, 0))

        self.gallery.bind("<Configure>", self._relayout, add="+")

        self.after(150, self._poll)
        self.after(60, self._relayout)
        self.after(60, self._detect_source)
        threading.Thread(target=self._thumbnail_worker, daemon=True).start()

    # -- layout helpers
    def _on_window_configure(self, event):
        if event.widget is not self:
            return
        logical_width = self.winfo_width() / self._get_window_scaling()
        pad = max(16, (logical_width - self.CONTENT_MAX) // 2)
        if pad != self._pad:
            self._pad = pad
            self.content.grid_configure(padx=pad)
        if hasattr(self, "info"):
            self._resize_results()
            self.lbl_status.configure(wraplength=max(180, min(self.CONTENT_MAX, logical_width - 32) - 64))

    def _resize_results(self):
        rows = (len(self._tiles) + max(1, self._cols) - 1) // max(1, self._cols)
        status_height = 46 if self.status.winfo_manager() else 0
        required = max(96, rows * (CARD_H + 8) + 30) if rows else 132
        available = max(110, self.winfo_height() / self._get_window_scaling() - 326)
        height = min(required + status_height, available, 200)
        if self.info.cget("height") != height:
            self.info.configure(height=height)

    def _gallery_scroll(self, first, last):
        self.gallery._scrollbar.set(first, last)
        if float(first) <= 0 and float(last) >= 0.999:
            self.gallery._scrollbar.grid_remove()
        else:
            self.gallery._scrollbar.grid()

    def _relayout(self, event=None):
        width = (self.gallery.winfo_width() if self._tiles else self.info.winfo_width() - 12)
        width /= self.gallery._get_widget_scaling()
        if width < 60:
            return
        cols = min(6, max(1, int(width // (CARD_W + 6))))
        if cols == self._cols:
            self._resize_results()
            return
        self._cols = cols
        self._resize_results()
        for c in range(6):
            self.gallery.grid_columnconfigure(c, weight=0, minsize=0)
        for i, tile in enumerate(self._tiles):
            tile.grid_configure(row=i // cols, column=i % cols)

    def _refresh_folder(self):
        base = os.path.basename(os.path.normpath(DOWNLOADS)) or DOWNLOADS
        self.lbl_folder.configure(text="Папка: " + base)
        self._folder_tip.text = DOWNLOADS

    def _refocus(self):
        try:
            self.entry._entry.focus_set()
            self.entry._entry.icursor("end")
        except Exception:
            pass

    # -- status row
    def _set_status(self, text, color=MUTED, ok=False):
        self._status_ok = ok
        if not text:
            self.status.grid_remove()
            return
        if not self.status.winfo_ismapped():
            self.status.grid()
        if ok:
            bg, border, icon, fg = "#15271f", "#205040", self._ico_check, GREEN
        elif color == RED:
            bg, border, icon, fg = "#2a171b", "#5a2e33", self._ico_warn, "#ff8d8d"
        else:
            bg, border, icon, fg = "#1b2130", "#2a3142", self._ico_dot, color
        self.lbl_icon.configure(image=icon, text="")
        self.status.configure(fg_color=bg, border_color=border,
                              cursor="hand2" if ok else "arrow")
        self.lbl_status.configure(text=text, text_color=fg,
                                  cursor="hand2" if ok else "arrow")
        self._resize_results()

    def _open_downloads(self, force=False):
        if not force and not self._status_ok:
            return
        try:
            os.startfile(DOWNLOADS if force else self._result_dest)
        except Exception:
            pass

    def _show_progress(self):
        self.progress.grid()

    def _hide_progress(self):
        if self.engine.busy == 0:
            self.progress.grid_remove()
            self.progress.set(0)

    # -- platform pill
    def _paint_badge(self, hover=None, press=None):
        for key, box in self._badges.items():
            if press == key:
                color = "#3a4460"
            elif hover == key:
                color = "#343c58"
            elif key == self._active_platform:
                color = self._badge_active
            else:
                color = "transparent"
            box.configure(fg_color=color)

    def _detect_source(self, event=None):
        """Highlight the platform the URL belongs to (the downloader routes by URL)."""
        key = platform_for(self.entry.get())
        if key != self._active_platform:
            self._active_platform = key
            self._paint_badge()

    # -- format segment
    def _segment(self, parent, col, title, sub, img, key, padx):
        card = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=8,
                            border_width=1, border_color=CARD, cursor="hand2")
        card.grid(row=0, column=col, sticky="nsew", padx=padx, pady=4)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(expand=True, pady=3)
        if img is not None:
            ctk.CTkLabel(row, image=img, text="").pack(side="left", padx=(0, 9))
        else:
            ctk.CTkLabel(row, text="HD" if key == "video" else "♪",
                         font=(FONT, 11), text_color=TEXT).pack(side="left", padx=(0, 9))
        txt = ctk.CTkFrame(row, fg_color="transparent")
        txt.pack(side="left")
        ctk.CTkLabel(txt, text=title, font=("Segoe UI", 16),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(txt, text=sub, font=(FONT, 12), text_color="#aebbd0").pack(anchor="w")

        def walk(w, acc):
            acc.append(w)
            canvas = getattr(w, "_canvas", None)
            if canvas is not None:
                acc.append(canvas)
            for ch in w.winfo_children():
                walk(ch, acc)

        targets = []
        walk(card, targets)
        for t in targets:
            try:
                t.bind("<Button-1>", lambda e, k=key: self.select_format(k), add="+")
            except Exception:
                pass
        return card

    def select_format(self, key):
        self.selected_format = key
        for k, card in (("video", self.card_mp4), ("music", self.card_mp3)):
            active = k == key
            card.configure(fg_color=SEG_ACTIVE if active else "transparent",
                           border_color="#4b6c9b" if active else CARD)

    def choose_folder(self):
        from tkinter import filedialog
        global DOWNLOADS
        d = filedialog.askdirectory(initialdir=DOWNLOADS, title="Папка завантажень")
        if d:
            DOWNLOADS = d
            self._refresh_folder()
            self._set_status("Папка: " + (os.path.basename(os.path.normpath(d)) or d), MUTED)

    def _open_settings(self):
        if self._settings_popup is not None and self._settings_popup.winfo_exists():
            self._settings_popup.destroy()
            self._settings_popup = None
            return
        popup = ctk.CTkToplevel(self, fg_color=BG)
        self._settings_popup = popup
        popup.withdraw()
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        frame = ctk.CTkFrame(popup, corner_radius=10, fg_color=CARD,
                             border_width=1, border_color=BORDER)
        frame.pack(fill="both", expand=True)
        buttons = []
        def invoke(action):
            popup.destroy()
            self._settings_popup = None
            self.after_idle(action)
        for text, action in (("Папка завантажень…", self.choose_folder),
                             ("Відкрити папку", lambda: self._open_downloads(True))):
            if buttons:
                ctk.CTkFrame(frame, height=1, fg_color=BORDER).pack(fill="x", padx=10)
            button = ctk.CTkButton(frame, text=text, image=self._pf_ico, compound="left",
                                   anchor="w", height=28, corner_radius=5, font=(FONT, 12),
                                   fg_color="transparent", hover_color=CARD_HOVER, text_color=TEXT,
                                   command=lambda a=action: invoke(a))
            button.pack(fill="x", padx=5, pady=(5 if not buttons else 2, 3))
            tk.Frame.configure(button, takefocus=1)
            tk.Frame.bind(button, "<FocusIn>", lambda e, b=button: b.configure(fg_color=CARD_HOVER))
            tk.Frame.bind(button, "<FocusOut>", lambda e, b=button: b.configure(fg_color="transparent"))
            for key in ("<Return>", "<space>"):
                tk.Frame.bind(button, key, lambda e, a=action: invoke(a))
            buttons.append(button)
        popup.bind("<Escape>", lambda e: popup.destroy())
        popup.bind("<Down>", lambda e: buttons[1].focus_set())
        popup.bind("<Up>", lambda e: buttons[0].focus_set())
        def dismiss():
            if popup.winfo_exists():
                focus = popup.focus_get()
                if focus is None or focus.winfo_toplevel() is not popup:
                    popup.destroy()
        popup.bind("<FocusOut>", lambda e: popup.after(40, dismiss))
        popup.update_idletasks()
        width, height = 212 * self._get_window_scaling(), 78 * self._get_window_scaling()
        x = max(0, min(self.winfo_screenwidth() - width - 8,
                       self.settings_button.winfo_rootx() + self.settings_button.winfo_width() - width))
        y = self.settings_button.winfo_rooty() + self.settings_button.winfo_height() + 6
        popup.geometry("212x78+%d+%d" % (x, min(y, self.winfo_screenheight() - height - 8)))
        popup.deiconify()
        popup.after(30, buttons[0].focus_set)

    def on_download(self):
        url = self.entry.get().strip()
        if not url:
            self._set_status("Встав посилання спочатку!", RED)
            return
        if not self.btn._enabled or self.engine.busy >= MAX_THREADS:
            self._set_status("Зачекай — ще виконується завантаження.", RED)
            return
        self._show_progress()
        self.progress.set(0)
        self.progress.configure(progress_color=ACCENT)
        self.btn.set_enabled(False, "Завантажую...")
        # Spotify always yields MP3 (DRM) - notify and auto-switch if Video selected
        if platform_for(url) == "spotify" and self.selected_format != "music":
            self.select_format("music")
            self._set_status("Spotify не віддає відео (DRM) — завантажую як Музика MP3", "#f5a623")
        else:
            self._set_status("Завантаження...", MUTED)
        self._detect_source()
        self.engine.start(url, self.selected_format == "music", DOWNLOADS)

    def _thumbnail_worker(self):
        while True:
            path, url, label = self._thumbnail_tasks.get()
            try:
                image = load_thumbnail(path, url)
                if image is not None:
                    self.events.put(dict(type="thumbnail", label=label, image=image))
            except Exception:
                pass  # A failed preview leaves a usable placeholder and open action.
            finally:
                self._thumbnail_tasks.task_done()

    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                t = ev["type"]
                if t == "status":
                    self._set_status(ev["text"], ev.get("color", MUTED))
                    if ev.get("color") == RED and self.engine.busy == 0:
                        self._hide_progress()
                        self.btn.set_enabled(True, "Завантажити")
                elif t == "progress":
                    self.progress.set((ev["value"] or 0) / 100.0)
                elif t == "done":
                    ok = ev.get("ok")
                    self._result_dest = ev.get("dest", DOWNLOADS)
                    self._set_status(ev["text"], GREEN if ok else RED, ok)
                    self.progress.set(1.0 if ok else 0)
                    self.btn.set_enabled(True, "Завантажити")
                    self.after(1500, self._hide_progress)
                    for path, url in ev.get("files", []):
                        try:
                            self._add_tile(path, url)
                        except Exception as ex:
                            self._set_status("Плитку не додано: %s" % str(ex)[:80], "#f5a623")
                    # restore keyboard focus to the entry (downloads steal it)
                    self.after(50, self._refocus)
                elif t == "thumbnail":
                    label = ev["label"]
                    if label.winfo_exists():
                        image = ev["image"]
                        label.configure(image=ctk.CTkImage(light_image=image, dark_image=image,
                                                         size=(CARD_W, CARD_H)), text="")
        except queue.Empty:
            pass
        except Exception as ex:  # one bad event must not stop the poll loop
            self._set_status("Помилка інтерфейсу: %s" % str(ex)[:80], RED)
        finally:
            self.after(150, self._poll)

    def _add_tile(self, path, url=None):
        if not path or not os.path.isfile(path) or os.path.abspath(path) in self._tile_paths:
            return
        self._tile_paths.add(os.path.abspath(path))
        if self._empty is not None:
            try:
                self._empty.destroy()
            except Exception:
                pass
            self._empty = None
            self.gallery.grid()

        placeholder = make_placeholder("music" if path.lower().endswith(".mp3") else "video",
                                       CARD_HOVER, (CARD_W * 2, CARD_H * 2))
        placeholder = tile_preview(placeholder)
        img = ctk.CTkImage(light_image=placeholder, dark_image=placeholder, size=(CARD_W, CARD_H))
        tile = ctk.CTkFrame(self.gallery, fg_color="transparent", cursor="hand2",
                            width=CARD_W, height=CARD_H)
        tile.pack_propagate(False)
        i = len(self._tiles)
        cols = max(1, self._cols)
        tile.grid(row=i // cols, column=i % cols, padx=3, pady=4)
        self._tiles.append(tile)

        if img is not None:
            pic = ctk.CTkLabel(tile, image=img, text="", cursor="hand2")
        else:
            pic = ctk.CTkLabel(tile, text="▶", font=(FONT, 18), text_color=ACCENT,
                               width=CARD_W, height=CARD_H, cursor="hand2")
        pic.pack()
        self._thumbnail_tasks.put((path, url, pic))

        name = os.path.basename(path)
        Tooltip(pic, "Відтворити\n" + name)
        Tooltip(tile, name)

        # Play is composited into the preview; the folder button has its own action.
        bfld = ctk.CTkButton(tile, text="", width=20, height=20, corner_radius=5,
                             fg_color="#0f1420", hover_color="#313854",
                             command=lambda p=path: self._show_in_folder(p))
        if self._pf_ico:
            bfld.configure(image=self._pf_ico)
        bfld.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)
        Tooltip(bfld, "Показати у папці")

        for w in (tile, pic):
            w.bind("<Button-1>", lambda e, p=path: self._open(p), add="+")
            canvas = getattr(w, "_canvas", None)
            if canvas is not None:
                canvas.bind("<Button-1>", lambda e, p=path: self._open(p), add="+")

        self._relayout()

    def _show_in_folder(self, path):
        try:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        except Exception:
            pass

    def _open(self, path):
        try:
            os.startfile(path)
        except Exception:
            pass


def main():
    # Setup/Uninstall checks this name before replacing or removing running files.
    # Windows keeps the mutex alive until the process exits; multiple app instances
    # remain allowed, each holding its own handle to the same mutex.
    create_mutex = ctypes.windll.kernel32.CreateMutexW
    create_mutex.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    create_mutex.restype = ctypes.c_void_p
    if not create_mutex(None, False, "Local\\MediaDownloader"):
        raise ctypes.WinError()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
