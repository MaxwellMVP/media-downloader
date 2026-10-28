# Media Downloader v0.3

## Завантаження

- **MediaDownloader-v0.3-Setup.exe** — встановлення для поточного користувача,
  ярлик меню «Пуск» і стандартне видалення через Windows.
- **MediaDownloader-v0.3-Portable.zip** — розпакувати й запустити EXE.
- **MediaDownloader-v0.3-Source.zip** — вихідний код і сценарії збирання.
- **SHA256SUMS.txt** — SHA-256 файлів релізу.

Windows 10/11 x64. Python окремо встановлювати не потрібно.

## Можливості

YouTube, TikTok і Spotify; відео MP4 й аудіо MP3; мініатюри, прогрес та
історія поточної сесії. Spotify використовує відповідне аудіо з YouTube.
Системні або мережеві обмеження сервісів можуть впливати на завантаження.

## Перевірка файлів

У PowerShell: `Get-FileHash .\MediaDownloader-v0.3-Setup.exe -Algorithm SHA256`.
Порівняйте результат із `SHA256SUMS.txt`. Збірки не підписані Authenticode.

MIT поширюється на вихідний код застосунку. Сторонні програми мають власні
ліцензії: див. `THIRD_PARTY_NOTICES.md` і `licenses/` у дистрибутиві.
FFmpeg: https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz
Gyan build information: https://www.gyan.dev/ffmpeg/builds/
yt-dlp: https://github.com/yt-dlp/yt-dlp/tree/2026.10.26
Deno: https://github.com/denoland/deno/tree/v2.9.8
spotDL: https://github.com/spotDL/spotify-downloader/tree/v4.6.0
# Code signing policy

Поточний v0.3 не підписаний. [Політика підпису](https://github.com/MaxwellMVP/media-downloader/blob/main/docs/CODE_SIGNING.md).

