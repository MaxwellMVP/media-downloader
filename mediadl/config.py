"""Version, theme constants, size limits, bundled-file lookup and process helpers."""
import logging
import os
import subprocess
import sys
import tempfile

from .messages import MediaError

APP_TITLE = "Media Downloader"
APP_VER = "v0.3"

# Window background (shown before the page paints) and thumbnail placeholder.
# The rest of the palette lives in web/app.css.
BG = "#242933"
CARD_HOVER = "#343c49"

# Thumbnail tile size in logical pixels
CARD_W, CARD_H = 84, 53

# One progress bar and one status label: parallel jobs would fight over them.
MAX_THREADS = 1

MB = 1024 * 1024
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0"}
TIKWM_API = "https://www.tikwm.com/api/"

# Remote data is size-capped and type-checked before it is read or saved.
MAX_API_BYTES, TYPES_API = 1 * MB, ("application/json", "text/")
MAX_IMAGE_BYTES, TYPES_IMAGE = 25 * MB, ("image/", "application/octet-stream")
MAX_VIDEO_BYTES, TYPES_VIDEO = 2048 * MB, ("video/", "application/octet-stream")
MAX_AUDIO_BYTES, TYPES_AUDIO = 200 * MB, ("audio/", "video/", "application/octet-stream")

# The windowed build has no console, so diagnostics go to a log file.
LOG_PATH = os.path.join(tempfile.gettempdir(), "mediadl.log")
log = logging.getLogger("mediadl")

# Hide console windows of helper tools (yt-dlp, spotdl, ffmpeg, deno).
CREATE_NO_WINDOW = 0x08000000
_startupinfo = subprocess.STARTUPINFO()
_startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
_startupinfo.wShowWindow = 0  # SW_HIDE
HIDDEN_PROCESS = {"startupinfo": _startupinfo, "creationflags": CREATE_NO_WINDOW}


def res_dir():
    """Folder that holds bundled assets: the PyInstaller bundle or the repository root."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    # This file lives in mediadl/, so the repository root is one level up.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_exe(name):
    """Path to a helper tool, or None when it is missing."""
    # frozen: binaries are extracted next to the app; source: they live in build_bin/
    for folder in (res_dir(), os.path.join(res_dir(), "build_bin")):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            return path
    return None


def exe(name):
    path = find_exe(name)
    if path is None:
        raise MediaError("tool_missing", name=name)
    return path


def asset(name):
    return os.path.join(res_dir(), "assets", name)


def cache_path(name):
    """Path inside the temp thumbnail cache; creates the cache folder on first use."""
    os.makedirs(THUMBS, exist_ok=True)
    return os.path.join(THUMBS, name)


DOWNLOADS = (os.path.join(os.path.expanduser("~"), "Downloads") if getattr(sys, "frozen", False)
             else os.path.join(res_dir(), "Downloads"))
THUMBS = os.path.join(tempfile.gettempdir(), "mediadl_thumbs")
