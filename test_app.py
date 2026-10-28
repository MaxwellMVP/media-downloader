# -*- coding: utf-8 -*-
"""Мінімальні тести для пакета mediadl: python -m unittest test_app -v"""
import base64
import io
import json
import os
import queue
import re
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch
from pathlib import Path
import threading
from types import SimpleNamespace

import requests
import subprocess
from PIL import Image

from mediadl import config, messages, prefs
from mediadl.api import MIN_HEIGHT, MIN_WIDTH, Api, to_data_url
from mediadl.engine import DownloadEngine
from mediadl.files import download_file, sanitize
from mediadl.messages import MediaError, error_text
from mediadl.network import http_get
from mediadl.sources import platform_for
from mediadl.thumbnails import tile_preview


def fake_tool(folder, body):
    path = os.path.join(folder, "tool.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write("import os, sys\n" + body)
    return [sys.executable, path]


def reply(chunks=(b"media",), content_type="application/octet-stream",
          url="https://example.com/file", length=None, error=None):
    """Streamed requests response double; supports the `with` form used by app.py."""
    response = MagicMock()
    response.url = url
    response.headers = {"Content-Type": content_type}
    if length is not None:
        response.headers["Content-Length"] = str(length)
    response.iter_content.return_value = list(chunks)
    response.raise_for_status.side_effect = error
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def web(api=None, media=b"media", failing=()):
    """Fake requests.get: the TikWM API returns `api` as JSON, `failing` URLs error, others return `media`."""
    def get(url, params=None, **kwargs):
        if url == config.TIKWM_API:
            return reply([json.dumps({"code": 0, "data": api}).encode()], "application/json", url)
        if url in failing:
            return reply(url=url, error=RuntimeError("network failure"))
        return reply([media], url=url)
    return get


class TempDirs(unittest.TestCase):
    def make_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name


class Helpers(TempDirs):
    def test_previews_use_one_crop_and_contrasting_play_badge(self):
        for size in ((40, 200), (200, 40)):
            preview = tile_preview(Image.new("RGB", size, "white"))
            self.assertEqual(preview.size, (config.CARD_W * 2, config.CARD_H * 2))
            self.assertEqual(preview.getpixel((0, 0))[3], 0)
            self.assertLess(preview.getpixel((preview.width // 2 - 15, preview.height // 2))[0], 200)

    def test_sanitize(self):
        self.assertEqual(sanitize('a/b:c*?"<>|d'), "abcd")
        self.assertEqual(sanitize("   "), "media")
        self.assertEqual(sanitize(None), "media")
        self.assertEqual(sanitize("x" * 500), "x" * 120)

    def test_source_finds_bundled_tools(self):
        with tempfile.TemporaryDirectory() as root, patch.object(config, "res_dir", return_value=root):
            tools = Path(root, "build_bin")
            tools.mkdir()
            (tools / "yt-dlp.exe").touch()
            self.assertEqual(os.path.dirname(config.exe("yt-dlp.exe")), str(tools))


class Layout(unittest.TestCase):
    def test_web_entry_point_and_assets_exist(self):
        web_dir = os.path.join(config.res_dir(), "web")
        with open(os.path.join(web_dir, "index.html"), encoding="utf-8") as f:
            page = f.read()
        for name in ("app.css", "app.js"):
            self.assertIn(name, page)
            self.assertTrue(os.path.isfile(os.path.join(web_dir, name)))
        # pywebview serves only the web/ folder, so parent-relative URLs 404.
        self.assertNotIn("../", page)
        for asset in set(re.findall(r'assets/([\w.]+)', page)):
            self.assertTrue(os.path.isfile(os.path.join(web_dir, "assets", asset)), asset)


class Engine(TempDirs):
    def test_failed_photo_download_preserves_existing_file(self):
        folder = self.make_dir()
        original = Path(folder, "same_01.jpg")
        original.write_bytes(b"original photo")
        q = queue.Queue()
        api = dict(title="same", images=["https://example.com/a.jpg"])
        with patch.object(requests, "get", side_effect=web(api, failing=("https://example.com/a.jpg",))):
            DownloadEngine(q)._tiktok_photo("https://tiktok.com/@a/photo/1", folder)
        self.assertEqual(original.read_bytes(), b"original photo")
        self.assertEqual(list(Path(folder).iterdir()), [original])
        events = list(q.queue)
        self.assertFalse(events[-1]["ok"])
        self.assertIn("network failure", events[-1]["text"])

    def test_photo_name_collision_keeps_both_files(self):
        folder = self.make_dir()
        original = Path(folder, "same_01.jpg")
        original.write_bytes(b"original")
        with patch.object(requests, "get", side_effect=web(media=b"new")):
            result = download_file("https://example.com/a.jpg", folder, original.name)
        self.assertEqual(original.read_bytes(), b"original")
        self.assertNotEqual(result, str(original))
        self.assertEqual(Path(result).read_bytes(), b"new")

    def test_tiktok_audio_only_does_not_download_images_or_video(self):
        folder = self.make_dir()
        q = queue.Queue()

        def convert(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(b"mp3")
            return Mock(returncode=0)
        api = dict(title="same", images=["https://example.com/photo.jpg"],
                   play="https://example.com/video.mp4", music="https://example.com/audio")
        with patch.object(requests, "get", side_effect=web(api, media=b"audio")) as get, \
             patch("mediadl.engine.exe", return_value="ffmpeg.exe"), \
             patch.object(subprocess, "run", side_effect=convert):
            DownloadEngine(q)._tiktok_photo("https://tiktok.com/@a/photo/1", folder, True)
        requested = [call.args[0] for call in get.call_args_list]
        self.assertEqual(requested, [config.TIKWM_API, "https://example.com/audio"])
        self.assertEqual([p.suffix for p in Path(folder).iterdir()], [".mp3"])
        self.assertTrue(list(q.queue)[-1]["ok"])

    def test_audio_conversion_failure_reports_partial_result(self):
        folder = self.make_dir()
        q = queue.Queue()
        api = dict(title="same", images=["https://example.com/photo.jpg"], music="https://example.com/audio")
        with patch.object(requests, "get", side_effect=web(api)), \
             patch("mediadl.engine.exe", return_value="ffmpeg.exe"), \
             patch.object(subprocess, "run", return_value=Mock(returncode=1, stderr="invalid input")):
            DownloadEngine(q)._tiktok_photo("https://tiktok.com/@a/photo/1", folder)
        done = list(q.queue)[-1]
        self.assertFalse(done["ok"])
        self.assertIn("invalid input", done["text"])
        self.assertEqual(len(done["files"]), 1)
        self.assertEqual([p.suffix for p in Path(folder).iterdir()], [".jpg"])

    def test_short_tiktok_video_uses_selected_format(self):
        folder = self.make_dir()
        engine = DownloadEngine(queue.Queue())
        api = dict(title="same", play="https://example.com/video.mp4")
        with patch.object(requests, "get", side_effect=web(api)), \
             patch.object(engine, "_ytdlp") as download:
            engine.busy = 1
            engine._run("https://vm.tiktok.com/abc/", True, folder)
            download.assert_called_once_with("https://vm.tiktok.com/abc/", folder, True, "en")
            self.assertEqual(engine.busy, 0)

    def test_platform_detection_uses_hostname(self):
        self.assertEqual(platform_for("https://vm.tiktok.com/abc/"), "tiktok")
        self.assertEqual(platform_for("https://open.spotify.com/track/1"), "spotify")
        self.assertEqual(platform_for("https://youtu.be/abcdefghijk"), "youtube")
        self.assertIsNone(platform_for("https://example.com/?next=open.spotify.com"))
        self.assertIsNone(platform_for("https://["))

    def test_missing_tool_blocks_download_before_it_starts(self):
        q = queue.Queue()
        engine = DownloadEngine(q)
        with patch("mediadl.engine.find_exe", side_effect=lambda name: None if name == "ffmpeg.exe" else "x"), \
             patch.object(engine, "_ytdlp") as download, \
             patch("mediadl.engine.threading.Thread") as thread:
            engine.start("https://www.youtube.com/watch?v=abcdefghijk", True, "unused")
        download.assert_not_called()
        thread.assert_not_called()
        event = q.get_nowait()
        self.assertEqual(event["kind"], "error")
        self.assertIn("ffmpeg.exe", event["text"])
        self.assertEqual(engine.busy, 0)

    def test_thumbnail_worker_loads_off_main_thread_and_stops_on_sentinel(self):
        tasks, events = queue.Queue(), queue.Queue()
        controller = SimpleNamespace(_thumb_tasks=tasks, _events=events)
        image = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        loaded_on = []

        def load(path, url):
            loaded_on.append(threading.get_ident())
            return image
        tasks.put(("file.mp4", "https://example.com/thumb"))
        tasks.put(None)
        with patch("mediadl.api.load_thumbnail", side_effect=load):
            worker = threading.Thread(target=Api._thumbnail_worker, args=(controller,), daemon=True)
            worker.start()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(loaded_on, [worker.ident])
        event = events.get_nowait()
        self.assertEqual(event["type"], "thumbnail")
        self.assertEqual(event["path"], "file.mp4")
        self.assertTrue(event["data"].startswith("data:image/png;base64,"))
        self.assertEqual(tasks.unfinished_tasks, 0)

    def test_thumbnail_failure_is_logged_and_worker_keeps_running(self):
        tasks, events = queue.Queue(), queue.Queue()
        controller = SimpleNamespace(_thumb_tasks=tasks, _events=events)
        tasks.put(("broken.mp4", None))
        tasks.put(None)
        with patch("mediadl.api.load_thumbnail", side_effect=OSError("unreadable")), \
             self.assertLogs(config.log, level="ERROR"):
            worker = threading.Thread(target=Api._thumbnail_worker, args=(controller,), daemon=True)
            worker.start()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertTrue(events.empty())
        self.assertEqual(tasks.unfinished_tasks, 0)

    def test_rejects_non_http(self):
        q = queue.Queue()
        e = DownloadEngine(q)
        e.start("--version", False, self.make_dir())
        ev = q.get_nowait()
        self.assertEqual(ev["type"], "status")
        self.assertIn("http", ev["text"])
        self.assertEqual(e.busy, 0)

    def test_scan_ignores_partial_files(self):
        d = self.make_dir()
        for name in ("a.mp4", "b.part", "c.ytdl", "d.mp3", "note.txt"):
            open(os.path.join(d, name), "wb").close()
        self.assertEqual(sorted(DownloadEngine(queue.Queue())._scan(d)), ["a.mp4", "d.mp3"])

    def test_reports_progress_and_files(self):
        d = self.make_dir()
        cmd = fake_tool(self.make_dir(),
            "dest = sys.argv[1]\n"
            "print('[download] Destination: ' + os.path.join(dest, 'a.mp4'), flush=True)\n"
            "print('[download]  50.0% of 1MiB', flush=True)\n"
            "open(os.path.join(dest, 'a.mp4'), 'wb').close()\n")
        cmd.append(d)
        q = queue.Queue()
        e = DownloadEngine(q)
        e._pipe_ytdlp(cmd, "https://example.com", d)
        events = []
        while not q.empty():
            events.append(q.get())
        self.assertEqual([ev["value"] for ev in events if ev["type"] == "progress"], [0, 50.0])
        done = [ev for ev in events if ev["type"] == "done"][0]
        self.assertTrue(done["ok"])
        self.assertEqual([os.path.basename(p) for p, _ in done["files"]], ["a.mp4"])

    def test_failure_shows_tool_error(self):
        d = self.make_dir()
        cmd = fake_tool(self.make_dir(), "print('ERROR: [TikTok] IP address is blocked', flush=True)\nsys.exit(1)\n")
        q = queue.Queue()
        e = DownloadEngine(q)
        e._pipe_ytdlp(cmd, "https://example.com", d)
        events = []
        while not q.empty():
            events.append(q.get())
        done = [ev for ev in events if ev["type"] == "done"][0]
        self.assertFalse(done["ok"])
        self.assertIn("IP address is blocked", done["text"])


class Language(TempDirs):
    """English is the default; Ukrainian is a secondary language stored in settings."""

    def settings_path(self):
        return os.path.join(self.make_dir(), "settings.json")

    def test_message_tables_are_complete(self):
        for key, (english, ukrainian) in messages._TEXT.items():
            self.assertTrue(english and ukrainian, key)
            placeholders = set(re.findall(r"\{(\w+)\}", english))
            self.assertEqual(placeholders, set(re.findall(r"\{(\w+)\}", ukrainian)), key)

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(messages.tr("fr", "busy"), messages.tr("en", "busy"))
        self.assertEqual(messages.DEFAULT, "en")

    def test_media_error_is_english_text_but_translates_on_display(self):
        error = MediaError("tool_missing", name="ffmpeg.exe")
        self.assertIsInstance(error, RuntimeError)
        self.assertIn("Not found: ffmpeg.exe", str(error))
        self.assertIn("Не знайдено ffmpeg.exe", error_text(error, "uk"))
        self.assertEqual(error_text(RuntimeError("plain"), "uk"), "plain")

    def test_engine_messages_follow_requested_language(self):
        events = queue.Queue()
        DownloadEngine(events).start("ftp://example.com/x", False, self.make_dir(), "uk")
        self.assertEqual(events.get_nowait()["text"], "Потрібне http(s)-посилання.")
        DownloadEngine(events).start("ftp://example.com/x", False, self.make_dir())
        self.assertEqual(events.get_nowait()["text"], "A http(s) link is required.")

    def test_preferences_round_trip_and_defaults(self):
        path = self.settings_path()
        with patch.object(prefs, "SETTINGS_PATH", path):
            self.assertEqual(prefs.load_language(), "en")
            prefs.save_language("uk")
            self.assertEqual(prefs.load_language(), "uk")
            with open(path, "w", encoding="utf-8") as f:
                f.write("not json")
            self.assertEqual(prefs.load_language(), "en")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"language": "fr"}, f)
            self.assertEqual(prefs.load_language(), "en")

    def test_set_language_persists_and_rejects_unsupported(self):
        path = self.settings_path()
        with patch.object(prefs, "SETTINGS_PATH", path):
            api = Api()
            self.assertEqual(api.get_state()["language"], "en")
            self.assertEqual(api.set_language("fr"), "en")
            self.assertFalse(os.path.exists(path))
            self.assertEqual(api.set_language("uk"), "uk")
            self.assertEqual(api.get_state()["language"], "uk")
            self.assertEqual(prefs.load_language(), "uk")


class ApiBridge(TempDirs):
    """Bridge between the page and the engine. No window is attached, so no threads run."""

    def test_data_url_is_png(self):
        url = to_data_url(Image.new("RGBA", (6, 4), (0, 0, 0, 0)))
        self.assertTrue(url.startswith("data:image/png;base64,"))
        decoded = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
        self.assertEqual(decoded.size, (6, 4))

    def test_done_lists_each_existing_file_once_and_queues_thumbnails(self):
        folder = self.make_dir()
        real = Path(folder, "a.mp4")
        real.write_bytes(b"x")
        api = Api()
        page = api._to_page(dict(type="done", ok=True, text="Готово", dest=folder,
                                 files=[(str(real), "https://example.com/t"), (str(real), None),
                                        (str(Path(folder, "missing.mp4")), None)]))
        self.assertTrue(page["ok"])
        self.assertEqual([f["name"] for f in page["files"]], ["a.mp4"])
        self.assertFalse(page["files"][0]["music"])
        self.assertEqual(api.result_dir, folder)
        self.assertEqual(api._thumb_tasks.get_nowait(), (os.path.abspath(real), "https://example.com/t"))
        self.assertTrue(api._thumb_tasks.empty())

    def test_error_status_while_idle_resets_ui(self):
        api = Api()
        api._engine.start("--version", False, self.make_dir())
        page = api._to_page(api._events.get_nowait())
        self.assertEqual(page["kind"], "error")
        self.assertTrue(page["idle"])

    def test_info_status_keeps_busy_state(self):
        page = Api()._to_page(dict(type="status", text="Завантаження...", kind="info"))
        self.assertFalse(page["idle"])

    def test_platform_detection_for_page(self):
        api = Api()
        self.assertEqual(api.detect_platform("https://vm.tiktok.com/abc/"), "tiktok")
        self.assertIsNone(api.detect_platform(""))

    def test_resize_is_clamped_to_minimum(self):
        api = Api()
        api._window = Mock(width=1024, height=600)
        api.begin_resize()
        api.resize_window(-2000, -2000, "se")
        api._window.resize.assert_called_once_with(MIN_WIDTH, MIN_HEIGHT)

    def test_only_gallery_files_can_be_opened(self):
        folder = self.make_dir()
        real = Path(folder, "a.mp4")
        real.write_bytes(b"x")
        api = Api()
        with patch("mediadl.api.os.startfile") as start:
            self.assertFalse(api.open_file(str(real)))
            self.assertFalse(api.show_in_folder(str(real)))
            start.assert_not_called()
            api._to_page(dict(type="done", ok=True, text="Готово", dest=folder, files=[(str(real), None)]))
            self.assertTrue(api.open_file(str(real)))
            start.assert_called_once_with(os.path.abspath(real))


class Network(TempDirs):
    URL = "https://example.com/a.jpg"

    def test_rejects_plain_http_before_any_request(self):
        with patch.object(requests, "get") as get, self.assertRaises(RuntimeError):
            http_get("http://example.com/a.jpg", config.MAX_IMAGE_BYTES, config.TYPES_IMAGE)
        get.assert_not_called()

    def test_rejects_unexpected_content_type_and_closes_response(self):
        response = reply([b"<html>"], "text/html", self.URL)
        with patch.object(requests, "get", return_value=response), self.assertRaises(RuntimeError):
            http_get(self.URL, config.MAX_IMAGE_BYTES, config.TYPES_IMAGE)
        response.close.assert_called_once()

    def test_rejects_declared_size_over_limit(self):
        response = reply([b"x"], "image/jpeg", self.URL, length=1001)
        with patch.object(requests, "get", return_value=response), self.assertRaises(RuntimeError):
            http_get(self.URL, 1000, config.TYPES_IMAGE)
        response.close.assert_called_once()

    def test_rejects_redirect_to_http(self):
        response = reply([b"x"], "image/jpeg", "http://example.com/a.jpg")
        with patch.object(requests, "get", return_value=response), self.assertRaises(RuntimeError):
            http_get(self.URL, config.MAX_IMAGE_BYTES, config.TYPES_IMAGE)
        response.close.assert_called_once()

    def test_stops_stream_over_limit_and_keeps_folder_clean(self):
        folder = self.make_dir()
        response = reply([b"a" * 8, b"b" * 8], "image/jpeg", self.URL)
        with patch.object(requests, "get", return_value=response), self.assertRaises(RuntimeError):
            download_file(self.URL, folder, "a.jpg", 10, config.TYPES_IMAGE)
        self.assertEqual(list(Path(folder).iterdir()), [])

    def test_dropped_connection_leaves_no_partial_file(self):
        folder = self.make_dir()

        def broken(**kwargs):
            yield b"partial"
            raise ConnectionError("dropped")
        response = reply(url=self.URL)
        response.iter_content.side_effect = broken
        with patch.object(requests, "get", return_value=response), self.assertRaises(ConnectionError):
            download_file(self.URL, folder, "a.jpg")
        self.assertEqual(list(Path(folder).iterdir()), [])

    def test_saves_file_within_limits(self):
        folder = self.make_dir()
        with patch.object(requests, "get", return_value=reply([b"photo"], "image/jpeg", self.URL)):
            saved = download_file(self.URL, folder, "a.jpg")
        self.assertEqual(Path(saved).read_bytes(), b"photo")


if __name__ == "__main__":
    unittest.main()
