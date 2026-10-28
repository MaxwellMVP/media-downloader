# -*- coding: utf-8 -*-
"""Мінімальні тести для app.py: python -m unittest test_app -v"""
import os
import queue
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import threading
import shutil
from types import SimpleNamespace

import app as A


def fake_tool(body):
    d = tempfile.mkdtemp()
    path = os.path.join(d, "tool.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write("import os, sys\n" + body)
    return [sys.executable, path]


class Helpers(unittest.TestCase):
    def test_previews_use_one_crop_and_contrasting_play_badge(self):
        for size in ((40, 200), (200, 40)):
            preview = A.tile_preview(A.Image.new("RGB", size, "white"))
            self.assertEqual(preview.size, (A.CARD_W * 2, A.CARD_H * 2))
            self.assertEqual(preview.getpixel((0, 0))[3], 0)
            self.assertLess(preview.getpixel((preview.width // 2 - 15, preview.height // 2))[0], 200)

    def test_sanitize(self):
        self.assertEqual(A.sanitize('a/b:c*?"<>|d'), "abcd")
        self.assertEqual(A.sanitize("   "), "media")
        self.assertEqual(A.sanitize(None), "media")
        self.assertEqual(A.sanitize("x" * 500), "x" * 120)

    def test_source_finds_bundled_tools(self):
        with tempfile.TemporaryDirectory() as root, patch.object(A, "res_dir", return_value=root):
            tools = Path(root, "build_bin")
            tools.mkdir()
            (tools / "yt-dlp.exe").touch()
            self.assertEqual(os.path.dirname(A.exe("yt-dlp.exe")), str(tools))


class ButtonBehavior(unittest.TestCase):
    def button(self):
        button = Mock(_enabled=True, _pressed=True)
        button._label.winfo_width.return_value = 232
        button._label.winfo_height.return_value = 44
        return button

    def test_mouse_release_only_invokes_once_after_press(self):
        button = self.button()
        event = SimpleNamespace(x=10, y=10)
        A.GradientButton._on_release(button, event)
        A.GradientButton._on_release(button, event)
        button._command.assert_called_once()

    def test_release_outside_or_disabled_does_not_invoke(self):
        button = self.button()
        A.GradientButton._on_release(button, SimpleNamespace(x=-1, y=10))
        button._command.assert_not_called()
        button._pressed, button._enabled = True, False
        A.GradientButton._on_release(button, SimpleNamespace(x=10, y=10))
        button._command.assert_not_called()


@unittest.skipUnless(os.environ.get("MEDIADL_GUI_TESTS"), "Set MEDIADL_GUI_TESTS=1 for desktop integration checks")
class DesktopLayout(unittest.TestCase):
    def close_window(self, window):
        for callback in window.tk.call("after", "info"):
            window.after_cancel(callback)
        window.destroy()

    def test_dense_grid_counts_and_long_url(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(A, "DOWNLOADS", folder):
            paths = []
            for index in range(20):
                path = Path(folder, "media-%02d.png" % index)
                shutil.copyfile(A.asset("yt.png"), path)
                paths.append(str(path))
            window = A.App()
            errors = []
            window.report_callback_exception = lambda *args: errors.append(args)
            try:
                window.update()
                added = 0
                window._set_status("Готово! Файли в папці Downloads.", A.GREEN, True)
                for count in (1, 6, 7, 20):
                    for path in paths[added:count]:
                        window._add_tile(path)
                    added = count
                    window.after(130, window.quit)
                    window.mainloop()
                    window.update()
                    self.assertEqual(window._cols, 6, (count, window.info.winfo_width(), window.gallery.winfo_width(), window.gallery._scrollbar.winfo_ismapped()))
                    self.assertLessEqual(window.info.cget("height"), 200)
                    for index, tile in enumerate(window._tiles):
                        self.assertEqual(int(tile.grid_info()["row"]), index // 6)
                        self.assertEqual((tile.winfo_width(), tile.winfo_height()), (A.CARD_W, A.CARD_H))
                    self.assertEqual(bool(window.gallery._scrollbar.winfo_ismapped()), count == 20)
                long_url = "https://open.spotify.com/playlist/" + "abcdefghij" * 60
                window.entry.insert(0, long_url)
                window.entry._entry.icursor("end")
                window.entry._entry.xview("end")
                window.update()
                self.assertEqual(window.entry.get(), long_url)
                self.assertGreater(window.entry._entry.xview()[0], 0)
                field = window.entry.master
                self.assertGreaterEqual(field.winfo_width() - window.entry.winfo_x() - window.entry.winfo_width(), 18)
                self.assertGreater(window.content.winfo_y(), 40)
                self.assertEqual(errors, [])
            finally:
                self.close_window(window)

    def test_real_widgets_empty_gallery_files_and_resize(self):
        real_files = sorted(Path(A.DOWNLOADS).glob("*.mp3")) + sorted(Path(A.DOWNLOADS).glob("*.mp4"))
        self.assertTrue(real_files, "This desktop check requires existing local media")
        real_files += sorted(Path(A.asset("")).glob("*.png"))
        with tempfile.TemporaryDirectory() as folder, patch.object(A, "DOWNLOADS", folder):
            window = A.App()
            errors = []
            window.report_callback_exception = lambda *args: errors.append(args)
            try:
                window.update()
                window.after(180, window.quit)
                window.mainloop()
                window.update()
                self.assertEqual(len(window._tiles), 0)
                self.assertFalse(window._status_ok)
                self.assertIsNotNone(window._empty)
                # Real existing files, without making demo downloads or copying media.
                window._add_tile(str(real_files[0]))
                window.update()
                self.assertEqual(len(window._tiles), 1)
                self.assertIsNone(window._empty)
                for path in real_files[1:]:
                    window._add_tile(str(path))
                window.update()
                self.assertEqual(len(window._tiles), len(real_files))
                for geometry in ("520x500", "1024x600", "1400x850"):
                    window.geometry(geometry)
                    window.update()
                    window._relayout()
                    window.update()
                    self.assertLessEqual(window.content.winfo_width(), 602)
                    self.assertLessEqual(window.info.winfo_y() + window.info.winfo_height(), window.content.winfo_height())
                    self.assertLessEqual(window._cols, 6)
                    for tile in window._tiles:
                        self.assertLessEqual(tile.winfo_x() + tile.winfo_width(), window.gallery.winfo_width())
                    if geometry == "520x500":
                        canvas = window.gallery._parent_canvas
                        canvas.yview_moveto(1)
                        window.update()
                        self.assertGreater(canvas.yview()[0], 0, "Gallery should scroll when its real files overflow")
                window.select_format("music")
                self.assertEqual(window.selected_format, "music")
                window.select_format("video")
                self.assertEqual(window.selected_format, "video")
                window.events.put(dict(type="done", ok=True, text="Saved", files=[], dest=folder))
                window._poll()
                self.assertTrue(window._status_ok)
                window.events.put(dict(type="done", ok=False, text="Network failure", files=[]))
                window._poll()
                self.assertFalse(window._status_ok)
                self.assertEqual(window.lbl_status.cget("text"), "Network failure")
                self.assertEqual(window.btn.tk.call(window.btn._w, "cget", "-takefocus"), "1")
                self.assertEqual(errors, [])
            finally:
                self.close_window(window)

    def test_new_session_ignores_existing_downloads(self):
        # Existing media in the real folder must never become session history.
        self.assertTrue(list(Path(A.DOWNLOADS).glob("*.mp*")))
        for launch in range(2):
            with patch.object(A.DownloadEngine, "_scan", side_effect=AssertionError("Startup must not scan downloads")):
                window = A.App()
                try:
                    window.after(220, window.quit)
                    window.mainloop()
                    self.assertEqual(window._tiles, [])
                    self.assertIsNotNone(window._empty)
                    self.assertFalse(window.gallery.winfo_ismapped())
                    self.assertLessEqual(window.info.cget("height"), 150)
                finally:
                    self.close_window(window)


class Engine(unittest.TestCase):
    def tiktok_response(self, **data):
        response = Mock()
        response.json.return_value = {"code": 0, "data": dict(title="same", **data)}
        return response

    def test_failed_photo_download_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder, "same_01.jpg")
            original.write_bytes(b"original photo")
            q = queue.Queue()
            with patch.object(A.requests, "get", return_value=self.tiktok_response(images=["https://example.com/a.jpg"])), \
                 patch.object(A, "http_get", side_effect=RuntimeError("network failure")):
                A.DownloadEngine(q)._tiktok_photo("https://tiktok.com/@a/photo/1", folder)
            self.assertEqual(original.read_bytes(), b"original photo")
            self.assertEqual(list(Path(folder).iterdir()), [original])
            events = list(q.queue)
            self.assertFalse(events[-1]["ok"])
            self.assertIn("network failure", events[-1]["text"])

    def test_photo_name_collision_keeps_both_files(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder, "same_01.jpg")
            original.write_bytes(b"original")
            with patch.object(A, "http_get", return_value=b"new"):
                result = A.download_file("https://example.com/a.jpg", folder, original.name)
            self.assertEqual(original.read_bytes(), b"original")
            self.assertNotEqual(result, str(original))
            self.assertEqual(Path(result).read_bytes(), b"new")

    def test_tiktok_audio_only_does_not_download_images_or_video(self):
        with tempfile.TemporaryDirectory() as folder:
            q = queue.Queue()
            def convert(cmd, **kwargs):
                Path(cmd[-1]).write_bytes(b"mp3")
                return Mock(returncode=0)
            response = self.tiktok_response(images=["https://example.com/photo.jpg"],
                                            play="https://example.com/video.mp4", music="https://example.com/audio")
            with patch.object(A.requests, "get", return_value=response), \
                 patch.object(A, "http_get", return_value=b"audio") as get, \
                 patch.object(A, "exe", return_value="ffmpeg.exe"), \
                 patch.object(A.subprocess, "run", side_effect=convert):
                A.DownloadEngine(q)._tiktok_photo("https://tiktok.com/@a/photo/1", folder, True)
            get.assert_called_once_with("https://example.com/audio", binary=True)
            self.assertEqual([p.suffix for p in Path(folder).iterdir()], [".mp3"])
            self.assertTrue(list(q.queue)[-1]["ok"])

    def test_audio_conversion_failure_reports_partial_result(self):
        with tempfile.TemporaryDirectory() as folder:
            q = queue.Queue()
            response = self.tiktok_response(images=["https://example.com/photo.jpg"], music="https://example.com/audio")
            with patch.object(A.requests, "get", return_value=response), \
                 patch.object(A, "http_get", return_value=b"media"), \
                 patch.object(A, "exe", return_value="ffmpeg.exe"), \
                 patch.object(A.subprocess, "run", return_value=Mock(returncode=1, stderr="invalid input")):
                A.DownloadEngine(q)._tiktok_photo("https://tiktok.com/@a/photo/1", folder)
            done = list(q.queue)[-1]
            self.assertFalse(done["ok"])
            self.assertIn("invalid input", done["text"])
            self.assertEqual(len(done["files"]), 1)
            self.assertEqual([p.suffix for p in Path(folder).iterdir()], [".jpg"])

    def test_short_tiktok_video_uses_selected_format(self):
        q = queue.Queue()
        engine = A.DownloadEngine(q)
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(A.requests, "get", return_value=self.tiktok_response(play="https://example.com/video.mp4")), \
             patch.object(engine, "_ytdlp") as download:
            engine.busy = 1
            engine._run("https://vm.tiktok.com/abc/", True, folder)
            download.assert_called_once_with("https://vm.tiktok.com/abc/", folder, True)
            self.assertEqual(engine.busy, 0)

    def test_platform_detection_uses_hostname(self):
        self.assertEqual(A.platform_for("https://vm.tiktok.com/abc/"), "tiktok")
        self.assertEqual(A.platform_for("https://open.spotify.com/track/1"), "spotify")
        self.assertEqual(A.platform_for("https://youtu.be/abcdefghijk"), "youtube")
        self.assertIsNone(A.platform_for("https://example.com/?next=open.spotify.com"))
        self.assertIsNone(A.platform_for("https://["))

    def test_thumbnail_loading_is_queued_off_main_thread(self):
        tasks, events = queue.Queue(), queue.Queue()
        controller = Mock(_thumbnail_tasks=tasks, events=events)
        main_thread = threading.get_ident()
        worker_thread = []
        image = object()
        class StopWorker(BaseException):
            pass
        def load(path, url):
            worker_thread.append(threading.get_ident())
            return image
        # Stop after one task without leaving a test thread waiting forever.
        calls = iter([("file.mp4", "https://example.com/thumb", "label")])
        def next_task():
            try:
                return next(calls)
            except StopIteration:
                raise StopWorker()
        tasks.get = next_task
        def run():
            try:
                A.App._thumbnail_worker(controller)
            except StopWorker:
                pass
        with patch.object(A, "load_thumbnail", side_effect=load):
            worker = threading.Thread(target=run)
            tasks.put(None)
            worker.start()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertNotEqual(worker_thread, [main_thread])
        self.assertIs(events.get_nowait()["image"], image)

    def test_rejects_non_http(self):
        q = queue.Queue()
        e = A.DownloadEngine(q)
        e.start("--version", False, tempfile.mkdtemp())
        ev = q.get_nowait()
        self.assertEqual(ev["type"], "status")
        self.assertIn("http", ev["text"])
        self.assertEqual(e.busy, 0)

    def test_scan_ignores_partial_files(self):
        d = tempfile.mkdtemp()
        for name in ("a.mp4", "b.part", "c.ytdl", "d.mp3", "note.txt"):
            open(os.path.join(d, name), "wb").close()
        self.assertEqual(sorted(A.DownloadEngine(queue.Queue())._scan(d)), ["a.mp4", "d.mp3"])

    def test_reports_progress_and_files(self):
        d = tempfile.mkdtemp()
        cmd = fake_tool(
            "dest = sys.argv[1]\n"
            "print('[download] Destination: ' + os.path.join(dest, 'a.mp4'), flush=True)\n"
            "print('[download]  50.0% of 1MiB', flush=True)\n"
            "open(os.path.join(dest, 'a.mp4'), 'wb').close()\n")
        cmd.append(d)
        q = queue.Queue()
        e = A.DownloadEngine(q)
        e._ytdlp_thumb = lambda url: None
        e._pipe_ytdlp(cmd, "https://example.com", d)
        events = []
        while not q.empty():
            events.append(q.get())
        self.assertEqual([ev["value"] for ev in events if ev["type"] == "progress"], [0, 50.0])
        done = [ev for ev in events if ev["type"] == "done"][0]
        self.assertTrue(done["ok"])
        self.assertEqual([os.path.basename(p) for p, _ in done["files"]], ["a.mp4"])

    def test_failure_shows_tool_error(self):
        d = tempfile.mkdtemp()
        cmd = fake_tool("print('ERROR: [TikTok] IP address is blocked', flush=True)\nsys.exit(1)\n")
        q = queue.Queue()
        e = A.DownloadEngine(q)
        e._pipe_ytdlp(cmd, "https://example.com", d)
        events = []
        while not q.empty():
            events.append(q.get())
        done = [ev for ev in events if ev["type"] == "done"][0]
        self.assertFalse(done["ok"])
        self.assertIn("IP address is blocked", done["text"])


if __name__ == "__main__":
    unittest.main()
