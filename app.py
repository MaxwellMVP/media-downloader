# -*- coding: utf-8 -*-
"""Media Downloader v0.3 - TikTok / YouTube / Spotify

Entry point only. The application code lives in the mediadl package and the
user interface is the HTML/CSS/JS page in web/, shown in a pywebview window.
"""
import ctypes
import logging
import os

import webview

from mediadl.api import MIN_HEIGHT, MIN_WIDTH, Api
from mediadl.config import APP_TITLE, BG, LOG_PATH, asset, res_dir


def main():
    # The windowed build has no console, so warnings are written to a log file.
    logging.basicConfig(filename=LOG_PATH, level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Setup/Uninstall checks this name before replacing or removing running files.
    # Windows keeps the mutex alive until the process exits; multiple app instances
    # remain allowed, each holding its own handle to the same mutex.
    create_mutex = ctypes.windll.kernel32.CreateMutexW
    create_mutex.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    create_mutex.restype = ctypes.c_void_p
    if not create_mutex(None, False, "Local\\MediaDownloader"):
        raise ctypes.WinError()
    # Own taskbar identity so Windows shows the app icon, not the Python one.
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MediaDownloader.v03")
    except OSError:
        logging.getLogger("mediadl").warning("Could not set the AppUserModelID", exc_info=True)

    index = os.path.join(res_dir(), "web", "index.html")
    api = Api()
    window = webview.create_window(
        APP_TITLE,
        url=index,
        js_api=api,
        width=1024,
        height=600,
        min_size=(MIN_WIDTH, MIN_HEIGHT),
        frameless=True,
        easy_drag=False,  # the page marks its title bar with pywebview-drag-region
        background_color=BG,
        text_select=True,  # the URL field must accept typing and selection
    )
    api.attach(window)
    # gui="edgechromium" needs the Microsoft Edge WebView2 Runtime.
    webview.start(gui="edgechromium", icon=asset("app.ico"))


if __name__ == "__main__":
    main()
