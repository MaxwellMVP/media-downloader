# Third-party notices — Media Downloader v0.3

Original application code is MIT licensed; see `LICENSE`. Each dependency and
external executable retains its own license. They are not relicensed under MIT.
The application invokes the external tools as separate processes.

## External programs bundled in the Windows executable

| Component | Version | License / upstream source |
|---|---|---|
| FFmpeg, gyan.dev essentials build | 9.0.2 | GPLv3 build (`--enable-gpl --enable-version3`); https://www.gyan.dev/ffmpeg/builds/ and https://github.com/FFmpeg/FFmpeg/tree/n9.0.2 |
| yt-dlp Windows executable | 2026.10.26 | Core: Unlicense; bundled executable and bundled dependencies have additional terms; https://github.com/yt-dlp/yt-dlp/tree/2026.10.26 |
| Deno | 2.9.8 | MIT and third-party notices; https://github.com/denoland/deno/tree/v2.9.8 |
| spotDL | 4.6.0 | MIT for the project, dependency licenses apply separately; https://github.com/spotDL/spotify-downloader/tree/v4.6.0 |

Hashes of the exact bundled executables: `build_bin/tools.lock.json`.
License texts and a recorded FFmpeg configuration are in `third_party/`.

FFmpeg source release: https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz
Gyan build source revision: https://github.com/FFmpeg/FFmpeg/commit/946fcce07b
Build provider information, including external libraries: https://www.gyan.dev/ffmpeg/builds/
FFmpeg distribution information: https://ffmpeg.org/legal.html

When redistributing GPL-covered binaries, preserve their terms and provide
access to the corresponding source, including relevant linked libraries and
build materials. The links here identify upstream projects; they are not a
claim that this repository contains a complete source reconstruction of every
third-party Windows executable. See each upstream project's release and license
for its bundled dependencies. Do not describe the entire Windows distribution
as MIT-only.

## Python runtime and libraries

The build uses CPython 3.12 and packages pinned in `requirements-lock.txt`:
pywebview (with pythonnet, clr-loader, cffi, pycparser, bottle and typing-extensions
as its runtime dependencies), proxy-tools, Pillow, requests, mutagen, packaging,
charset-normalizer, idna, urllib3 and certifi. Mutagen uses GPL terms, certifi uses
MPL terms, and other packages have their own notices. Their installed license texts
are copied to `third_party/python-packages/` by `scripts/collect_licenses.py`, which
fails if a package with a license file ships none. The CPython license text is included
there as `CPython-LICENSE.txt`.

proxy-tools 0.1.0 is MIT licensed but its wheel ships no license file. The MIT text
must be placed in `third_party/python-packages/proxy-tools/` before distribution;
`VERSIONS.txt` marks this as pending.

The user interface is rendered by the Microsoft Edge WebView2 Runtime, which is
a system component and is not bundled with the application.

PyInstaller's bootloader license has an exception for distributing applications;
the build tool's license does not replace the application's dependency licenses.
https://pyinstaller.org/en/stable/license.html
