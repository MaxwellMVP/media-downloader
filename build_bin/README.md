# Зовнішні інструменти

EXE не зберігаються в Git. Перед запуском або збиранням поклади сюди:

| Файл | Версія для v0.3 | Офіційне джерело |
|---|---|---|
| `yt-dlp.exe` | 2026.10.26 | https://github.com/yt-dlp/yt-dlp/releases/tag/2026.10.26 |
| `ffmpeg.exe` | 9.0.2 essentials, gyan.dev | https://www.gyan.dev/ffmpeg/builds/ |
| `deno.exe` | 2.9.8, Windows x64 | https://github.com/denoland/deno/releases/tag/v2.9.8 |
| `spotdl.exe` | 4.6.0, Windows | https://github.com/spotDL/spotify-downloader/releases/tag/v4.6.0 |

Розпакуй архіви й перейменуй Windows binary spotDL на `spotdl.exe`, якщо потрібно.
Точні SHA-256 поточних інструментів наведено в `tools.lock.json`. Скрипт збирання
перевіряє їх до пакування. Для свідомого оновлення інструмента потрібно також
оновити manifest, ліцензії, відповідні джерела та перевірити завантаження.
