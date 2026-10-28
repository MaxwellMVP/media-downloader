"""Python side of the web UI.

Public methods of `Api` are exposed to the page as `window.pywebview.api.<name>()`.
Events produced by the engine and thumbnail worker are sent to the page with
`window.mediadl.receive(batch)`.
"""
import base64
import io
import json
import os
import queue
import subprocess
import threading

import webview

from . import prefs
from .config import DOWNLOADS, log
from .engine import DownloadEngine
from .messages import SUPPORTED
from .sources import platform_for
from .thumbnails import load_thumbnail

# Minimum window size in logical pixels; keep in sync with min_size in app.py.
MIN_WIDTH, MIN_HEIGHT = 520, 500


def to_data_url(image):
    """Encode a PIL image as a PNG data URL for use in an <img> tag."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class Api:
    """Bridge between the HTML/JS page and the download engine."""

    def __init__(self):
        # Private attributes: pywebview walks public attributes of js_api and
        # touching the native window from that walk fails off the UI thread.
        self._events = queue.Queue()
        self._engine = DownloadEngine(self._events)
        self._language = prefs.load_language()
        self.download_dir = DOWNLOADS
        self.result_dir = DOWNLOADS
        self._window = None
        self._maximized = False
        self._resize_origin = (0, 0)
        self._shown = set()  # absolute paths already in the gallery
        self._thumb_tasks = queue.Queue()
        self._page_ready = threading.Event()

    def attach(self, window):
        """Bind the pywebview window and start the background threads."""
        self._window = window
        window.events.loaded += self._page_ready.set
        window.events.maximized += self._on_maximized
        window.events.restored += self._on_restored
        threading.Thread(target=self._thumbnail_worker, daemon=True).start()
        threading.Thread(target=self._pump, daemon=True).start()

    # ----- methods called from the page -----

    def get_state(self):
        return self._folder_state()

    def set_language(self, lang):
        """Switch the page and engine language and remember the choice. Returns the language in effect."""
        if lang not in SUPPORTED:
            return self._language
        self._language = lang
        try:
            prefs.save_language(lang)
        except OSError:
            log.warning("Could not save the language setting", exc_info=True)
        return lang

    def detect_platform(self, url):
        return platform_for(url or "")

    def start_download(self, url, mp3):
        self._engine.start(url or "", bool(mp3), self.download_dir, self._language)

    def choose_folder(self):
        picked = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=self.download_dir)
        if not picked:
            return None
        self.download_dir = picked[0]
        return self._folder_state()

    def open_downloads(self, folder=False):
        """Open the download folder (folder=True) or the folder of the last result."""
        return self._open(self.download_dir if folder else self.result_dir)

    def open_file(self, path):
        """Open a file that is shown in the gallery. Other paths are refused."""
        if not self._is_shown(path):
            return False
        return self._open(os.path.abspath(path))

    def show_in_folder(self, path):
        if not self._is_shown(path):
            return False
        try:
            subprocess.Popen(["explorer", "/select,", os.path.abspath(path)])
        except OSError:
            log.warning("Could not show %s in Explorer", path, exc_info=True)
            return False
        return True

    def minimize(self):
        self._window.minimize()

    def toggle_maximize(self):
        if self._maximized:
            self._window.restore()
        else:
            self._window.maximize()

    def close(self):
        self._window.destroy()

    def begin_resize(self):
        """Remember the window size at the start of a drag on a resize handle."""
        self._resize_origin = (self._window.width, self._window.height)

    def resize_window(self, dx, dy, edge):
        """Resize from the origin captured by begin_resize. dx/dy are logical pixels."""
        width, height = self._resize_origin
        if "e" in edge:
            width = max(MIN_WIDTH, width + dx)
        if "s" in edge:
            height = max(MIN_HEIGHT, height + dy)
        self._window.resize(int(width), int(height))

    # ----- events to the page -----

    def _on_maximized(self):
        self._set_maximized(True)

    def _on_restored(self):
        self._set_maximized(False)

    def _set_maximized(self, value):
        self._maximized = value
        self._events.put({"type": "window", "maximized": value})

    def _pump(self):
        """Forward queued events to the page in batches."""
        self._page_ready.wait()
        while True:
            batch = [self._events.get()]
            while True:
                try:
                    batch.append(self._events.get_nowait())
                except queue.Empty:
                    break
            payload = [item for item in (self._to_page(ev) for ev in batch) if item is not None]
            if payload:
                self._push(payload)

    def _push(self, payload):
        try:
            self._window.evaluate_js("window.mediadl && window.mediadl.receive(%s)" % json.dumps(payload))
        except Exception:
            log.exception("Could not send events to the page")

    def _to_page(self, ev):
        kind = ev["type"]
        if kind == "status":
            # A rejected request (error while nothing runs) leaves the UI ready for another try.
            idle = ev.get("kind") == "error" and self._engine.busy == 0
            return {"type": "status", "text": ev["text"], "kind": ev.get("kind", "info"), "idle": idle}
        if kind == "progress":
            return {"type": "progress", "value": ev.get("value") or 0}
        if kind == "done":
            return self._done(ev)
        if kind in ("thumbnail", "window"):
            return ev
        return None

    def _done(self, ev):
        self.result_dir = ev.get("dest") or self.download_dir
        files = []
        for path, url in ev.get("files", []):
            key = os.path.abspath(path)
            if key in self._shown or not os.path.isfile(key):
                continue
            self._shown.add(key)
            self._thumb_tasks.put((key, url))
            files.append({"path": key, "name": os.path.basename(key), "music": key.lower().endswith(".mp3")})
        return {"type": "done", "ok": bool(ev.get("ok")), "text": ev["text"], "files": files}

    # ----- background work -----

    def _thumbnail_worker(self):
        """Build thumbnails off the UI path; None is the stop sentinel."""
        while True:
            task = self._thumb_tasks.get()
            try:
                if task is None:
                    return
                path, url = task
                image = load_thumbnail(path, url)
                if image is not None:
                    self._events.put({"type": "thumbnail", "path": path, "data": to_data_url(image)})
            except Exception:
                log.exception("Thumbnail task failed: %r", task)
            finally:
                self._thumb_tasks.task_done()

    # ----- helpers -----

    def _folder_state(self):
        return {"folder": os.path.basename(os.path.normpath(self.download_dir)) or self.download_dir,
                "path": self.download_dir,
                "language": self._language}

    def _is_shown(self, path):
        return os.path.abspath(path or "") in self._shown

    def _open(self, target):
        try:
            os.startfile(target)
        except OSError:
            log.warning("Could not open %s", target, exc_info=True)
            return False
        return True
