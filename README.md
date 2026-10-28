# Media Downloader

![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11%20x64-0078D6)
![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

Windows-застосунок для завантаження відео та музики з **YouTube, TikTok і Spotify** у форматах **MP4** і **MP3**. Темний інтерфейс українською мовою, прогрес завантаження, мініатюри та історія поточної сесії.

## Можливості

- Відео з YouTube і TikTok у форматі MP4.
- Музика з YouTube і TikTok у форматі MP3 (у TikTok зберігається лише аудіо).
- Треки Spotify у форматі MP3.
- Прогрес, мініатюри та відкриття файлу в Провіднику.
- Історія поточної сесії.
- Керування з клавіатури: `Tab`, `Shift+Tab`, `Enter`, `Space`.
- Вибір папки збереження через налаштування (⚙).

## Завантаження

Готові файли публікуються у розділі [Releases](https://github.com/MaxwellMVP/media-downloader/releases).

| Варіант | Файл у релізі | Як запустити |
|---|---|---|
| Інсталятор | `MediaDownloader-v<версія>-Setup.exe` | Запустити майстер встановлення. Ярлик з'явиться в меню «Пуск», видалення доступне в налаштуваннях Windows |
| Portable | `MediaDownloader-v<версія>-Portable.zip` | Розпакувати архів і запустити `MediaDownloader.exe` |

**Вимоги:** Windows 10/11 x64 і [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) (зазвичай уже встановлений). Python і допоміжні програми входять до збірки.

Інсталятор встановлює програму для поточного користувача, права адміністратора не потрібні. Ярлик на робочому столі можна вибрати під час встановлення.

## Як користуватися

1. Вставте посилання на YouTube, TikTok або Spotify.
2. Оберіть «Відео MP4» або «Музика MP3». Для Spotify завжди використовується MP3.
3. Натисніть «Завантажити» і дочекайтеся завершення.
4. Натисніть картку, щоб відтворити файл, або іконку папки, щоб показати його в Провіднику.

Одночасно виконується одне завантаження.

Готові збірки зберігають файли в системну папку **Downloads** поточного користувача або в обрану вами папку. Запуск із вихідного коду використовує папку `Downloads/` у каталозі проєкту.

Історія показує **лише поточну сесію**: після перезапуску вона порожня, але збережені файли залишаються на диску. Видалення програми їх не чіпає.

## Обмеження та приватність

- Spotify не віддає аудіо напряму: spotDL знаходить відповідний запис на YouTube.
- Доступність, якість і обмеження за IP залежать від зовнішніх сервісів.
- Фото-пости TikTok обробляються через стороннє API [tikwm.com](https://www.tikwm.com/api/): URL допису надсилається цьому сервісу. Його політику конфіденційності проєкт не контролює.
- Підтримуються лише посилання `http://` і `https://`.

## Запуск із вихідного коду

Потрібен Python 3.12 x64.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

Перед першим запуском додайте допоміжні EXE до `build_bin/`: `yt-dlp.exe`, `ffmpeg.exe`, `deno.exe`, `spotdl.exe`. Джерела та версії описано в [build_bin/README.md](build_bin/README.md). Без них інтерфейс відкриється, але завантаження не працюватимуть.

```powershell
.\.venv\Scripts\python.exe app.py
```

## Збирання та релізи

- [Збирання portable-версії та інсталятора](BUILDING.md) (потрібен Inno Setup 6.6 або новіший)
- [Публікація на GitHub і Releases](GITHUB_UPLOAD.md)
- [Історія змін](CHANGELOG.md)

## Тести

```powershell
.\.venv\Scripts\python.exe -m unittest test_app -v
```

Тести не потребують мережі чи допоміжних EXE. GitHub Actions запускає їх на Windows. Додаткові перевірки інтерфейсу вмикаються через `MEDIADL_GUI_TESTS=1`, деталі в [BUILDING.md](BUILDING.md).

## Структура проєкту

```text
app.py          точка входу: вікно pywebview
mediadl/        логіка завантаження, мініатюри, налаштування, API для інтерфейсу
web/            інтерфейс: HTML, CSS, JavaScript
scripts/        збирання, пакування та ліцензії
packaging/      скрипт Inno Setup
build_bin/      допоміжні EXE (не зберігаються в Git)
third_party/    ліцензійні тексти сторонніх компонентів
test_app.py     unit-тести
```

## Ліцензія

Вихідний код застосунку поширюється за ліцензією [MIT](LICENSE). Сторонні інструменти та бібліотеки мають власні ліцензії, див. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
