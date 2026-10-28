"""Download engine: runs one job at a time on a worker thread and reports events through a queue."""
import json
import os
import queue
import re
import subprocess
import tempfile
import threading
from urllib.parse import urlsplit

from .config import (HIDDEN_PROCESS, MAX_API_BYTES, MAX_AUDIO_BYTES, MAX_THREADS,
                     MAX_VIDEO_BYTES, TIKWM_API, TYPES_API, TYPES_AUDIO,
                     TYPES_VIDEO, exe, find_exe, log)
from .files import download_file, publish_file, sanitize
from .messages import DEFAULT, MediaError, error_text, tr
from .network import http_get, save_url
from .sources import platform_for, saved_text, youtube_thumbnail_url

MEDIA_EXTS = (".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".opus",
              ".jpg", ".jpeg", ".png", ".webp")
_DESTINATION_RE = re.compile(r"\[download\]\s+Destination:\s+")
_PERCENT_RE = re.compile(r"\[download\]\s+([\d.]+)%")
_SPOTIFY_FOUND_RE = re.compile(r"Found\s+(\d+)\s+song")
_SPOTIFY_DOWNLOADING_RE = re.compile(r"Downloading\s+(?:\"|\u201c)?")
_SPOTIFY_ALREADY_RE = re.compile(r"Already\s+downloaded")
_TIKTOK_IMAGE_EXT_RE = re.compile(r"\.(png|jpeg|webp)(\?|$)")
# Helper tools each download path runs; checked before anything is written.
_SPOTIFY_TOOLS = ("spotdl.exe", "ffmpeg.exe")
_MEDIA_TOOLS = ("yt-dlp.exe", "ffmpeg.exe", "deno.exe")


def _start_tool(cmd):
    """Start a helper tool with its console hidden and stdout and stderr merged."""
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", **HIDDEN_PROCESS)


def _finish_tool(proc):
    """Wait for a helper tool to exit and release its output pipe."""
    proc.wait()
    proc.stdout.close()


class DownloadEngine:
    """Runs downloads in background threads and pushes events to a queue."""

    def __init__(self, events: queue.Queue):
        self.events = events
        self.busy = 0
        self.lock = threading.Lock()

    def send(self, **event):
        event.setdefault("type", "status")
        event.setdefault("kind", "info")
        self.events.put(event)

    def start(self, url, mp3, dest, lang=DEFAULT):
        url = url.strip()
        if not url:
            return
        if not url.lower().startswith(("http://", "https://")):
            self.send(text=tr(lang, "invalid_url"), kind="error")
            return
        missing = [name for name in self._required_tools(url) if find_exe(name) is None]
        if missing:
            self.send(text=tr(lang, "tools_missing", names=", ".join(missing)), kind="error")
            return
        with self.lock:
            if self.busy >= MAX_THREADS:
                self.send(text=tr(lang, "busy"), kind="error")
                return
            self.busy += 1
        threading.Thread(target=self._run, args=(url, mp3, dest, lang), daemon=True).start()

    @staticmethod
    def _required_tools(url):
        return _SPOTIFY_TOOLS if platform_for(url) == "spotify" else _MEDIA_TOOLS

    def _run(self, url, mp3, dest, lang=DEFAULT):
        try:
            os.makedirs(dest, exist_ok=True)
            platform = platform_for(url)
            if platform == "spotify":
                self._spotify(url, dest, lang)
            elif platform == "tiktok" and "/video/" not in urlsplit(url).path:
                self._tiktok_photo(url, dest, mp3, lang)
            else:
                self._ytdlp(url, dest, mp3, lang)
        except Exception as error:
            log.exception("Download failed: %s", url)
            self.send(type="done", ok=False, text=tr(lang, "error", detail=error_text(error, lang)[:120]))
        finally:
            with self.lock:
                self.busy -= 1

    def _scan(self, dest):
        """Media files currently in dest; yt-dlp partial files use other extensions and are ignored."""
        try:
            return {f for f in os.listdir(dest) if f.lower().endswith(MEDIA_EXTS)}
        except OSError:
            return set()

    # -- yt-dlp (YouTube, TikTok video, and other links)

    def _ytdlp(self, url, dest, mp3, lang=DEFAULT):
        cmd = [exe("yt-dlp.exe"), "--ffmpeg-location", exe("ffmpeg.exe"),
               "--js-runtimes", "deno:" + exe("deno.exe"),
               "--newline", "--no-playlist",
               "-o", os.path.join(dest, "%(title)s.%(ext)s")]
        if mp3:
            cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0",
                    "--embed-thumbnail", "--add-metadata"]
        else:
            cmd += ["-f", "bv*+ba/b", "--merge-output-format", "mp4"]
        cmd.append(url)
        self.send(text=tr(lang, "converting_mp3" if mp3 else "connecting"))
        self._pipe_ytdlp(cmd, url, dest, lang)

    def _pipe_ytdlp(self, cmd, url, dest, lang=DEFAULT):
        before = self._scan(dest)
        proc = _start_tool(cmd)
        last_error = None
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("ERROR:"):
                last_error = line[6:].strip()
            if _DESTINATION_RE.search(line):
                self.send(type="progress", value=0)
            match = _PERCENT_RE.search(line)
            if match:
                self.send(type="progress", value=float(match.group(1)))
        _finish_tool(proc)
        new = [f for f in self._scan(dest) if f not in before]
        if proc.returncode == 0:
            thumb = youtube_thumbnail_url(url)
            self.send(type="done", ok=True, text=saved_text(dest, lang),
                      files=[(os.path.join(dest, f), thumb) for f in new], dest=dest)
        else:
            detail = last_error or tr(lang, "exit_code", code=proc.returncode)
            self.send(type="done", ok=False, text=tr(lang, "error", detail=detail[:160]))

    # -- Spotify (spotDL searches YouTube for each track)

    def _spotify(self, url, dest, lang=DEFAULT):
        self.send(text=tr(lang, "spotify_working"))
        cmd = [exe("spotdl.exe"), "download", url, "--output", dest,
               "--threads", "3", "--ffmpeg", exe("ffmpeg.exe")]
        before = self._scan(dest)
        proc = _start_tool(cmd)
        total, position = None, 0
        for line in proc.stdout:
            line = line.strip()
            if not total:
                found = _SPOTIFY_FOUND_RE.search(line)
                if found:
                    total = int(found.group(1))
            if _SPOTIFY_DOWNLOADING_RE.search(line):
                position += 1
                if total:
                    self.send(type="progress", value=100.0 * position / total)
                    self.send(text=tr(lang, "spotify_progress", done=position, total=total))
            if _SPOTIFY_ALREADY_RE.search(line):
                position += 1
        _finish_tool(proc)
        new = [f for f in self._scan(dest) if f not in before]
        ok = proc.returncode == 0
        self.send(type="done", ok=ok,
                  text=saved_text(dest, lang) if ok else tr(lang, "spotify_failed"),
                  files=[(os.path.join(dest, f), None) for f in new], dest=dest)

    # -- TikTok photo slideshows (metadata from the tikwm API)

    def _tiktok_photo(self, url, dest, mp3=False, lang=DEFAULT):
        self.send(text=tr(lang, "tiktok_fetching"))
        data = json.loads(http_get(TIKWM_API, MAX_API_BYTES, TYPES_API, params={"url": url}))
        if data.get("code") != 0 or not data.get("data"):
            msg = data.get("msg")
            if msg:
                raise MediaError("tiktok_api_error", msg=msg)
            raise MediaError("tiktok_unavailable")
        post = data["data"]
        # Shared TikTok links can resolve to videos. Keep yt-dlp's format handling.
        if not post.get("images"):
            return self._ytdlp(url, dest, mp3, lang)
        title = sanitize(post.get("title"))
        files = []
        try:
            if not mp3:
                self._save_slides(post, title, dest, files, lang)
            if post.get("music"):
                files.append(self._save_tiktok_audio(post["music"], title, dest, lang))
            elif mp3:
                raise MediaError("tiktok_no_audio")
            if not files:
                raise MediaError("tiktok_no_files")
        except Exception as error:
            log.exception("TikTok download failed: %s", url)
            detail = error_text(error, lang)[:180]
            text = tr(lang, "partial_saved", count=len(files), error=detail) if files else detail
            self.send(type="done", ok=False, text=text,
                      files=[(f, None) for f in files], dest=dest)
            return
        self.send(type="done", ok=True, text=saved_text(dest, lang),
                  files=[(f, None) for f in files], dest=dest)

    def _save_slides(self, post, title, dest, files, lang=DEFAULT):
        """Download each photo and the optional video; saved paths are appended to files as they finish."""
        images = post["images"]
        for index, img_url in enumerate(images, 1):
            self.send(type="progress", value=100.0 * index / len(images))
            self.send(text=tr(lang, "tiktok_photo_progress", done=index, total=len(images)))
            match = _TIKTOK_IMAGE_EXT_RE.search(img_url or "")
            ext = match.group(1) if match else "jpg"
            files.append(download_file(img_url, dest, "%s_%02d.%s" % (title, index, ext)))
        if post.get("play"):
            files.append(download_file(post["play"], dest, title + ".mp4", MAX_VIDEO_BYTES, TYPES_VIDEO))

    def _save_tiktok_audio(self, music_url, title, dest, lang=DEFAULT):
        """Fetch the track and convert it to MP3 in a staging folder, then publish it."""
        with tempfile.TemporaryDirectory(prefix=".mediadl-", dir=dest) as work:
            source = os.path.join(work, "source.audio")
            save_url(music_url, source, MAX_AUDIO_BYTES, TYPES_AUDIO)
            name = title + " (audio).mp3"
            audio = os.path.join(work, name)
            conv = subprocess.run([exe("ffmpeg.exe"), "-y", "-i", source, "-q:a", "0", audio],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  **HIDDEN_PROCESS)
            if conv.returncode != 0:
                detail = (conv.stderr or "FFmpeg " + tr(lang, "exit_code", code=conv.returncode)).strip()[-180:]
                raise MediaError("mp3_failed", detail=detail)
            return publish_file(audio, dest, name)
