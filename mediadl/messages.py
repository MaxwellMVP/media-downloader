"""User-facing text for the engine and the network layer, in English and Ukrainian.

Each entry is a (English, Ukrainian) pair of str.format templates.
"""

SUPPORTED = ("en", "uk")
DEFAULT = "en"

_TEXT = {
    "invalid_url": ("A http(s) link is required.",
                    "Потрібне http(s)-посилання."),
    "tools_missing": ("Not found: {names} (place them in build_bin or next to the app).",
                      "Не знайдено: {names} (поклади у build_bin або поруч із програмою)."),
    "tool_missing": ("Not found: {name} (place it in build_bin or next to the app).",
                     "Не знайдено {name} (поклади у build_bin або поруч із програмою)."),
    "busy": ("Wait — a download is still running.",
             "Зачекай — ще виконується завантаження."),
    "error": ("Error: {detail}", "Помилка: {detail}"),
    "exit_code": ("code {code}", "код {code}"),
    "connecting": ("Connecting...", "З'єднання..."),
    "converting_mp3": ("Converting to MP3...", "Конвертація в MP3..."),
    "spotify_working": ("Spotify: searching and downloading...", "Spotify: шукаю та завантажую..."),
    "spotify_progress": ("Spotify: {done} of {total}...", "Spotify: {done} з {total}..."),
    "spotify_failed": ("Spotify error (see the log).", "Помилка Spotify (див. журнал)."),
    "tiktok_fetching": ("TikTok: fetching photos...", "TikTok: отримую фото..."),
    "tiktok_photo_progress": ("TikTok: photo {done} of {total}...", "TikTok: фото {done} з {total}..."),
    "tiktok_api_error": ("TikTok: {msg}", "TikTok: {msg}"),
    "tiktok_unavailable": ("TikTok: could not fetch this post.", "TikTok: не вдалось отримати допис."),
    "tiktok_no_audio": ("TikTok: this post has no audio.", "TikTok: у цьому дописі немає аудіо."),
    "tiktok_no_files": ("TikTok: no files found to download.", "TikTok: файлів для завантаження не знайдено."),
    "partial_saved": ("Saved {count} file(s), but {error}", "Збережено {count} файл(ів), але {error}"),
    "mp3_failed": ("Could not create MP3: {detail}", "Не вдалося створити MP3: {detail}"),
    "saved": ("Done! Files are in the folder {folder}.", "Готово! Файли в папці {folder}."),
    "https_only": ("Only https links are allowed.", "Дозволено лише https-посилання."),
    "redirect_blocked": ("Redirect to a non-https address was blocked.",
                         "Перенаправлення на не-https адресу заблоковано."),
    "too_large": ("The file is larger than the size limit.", "Файл більший за ліміт розміру."),
    "too_large_stream": ("The file exceeds the size limit.", "Файл перевищує ліміт розміру."),
    "bad_type": ("Unexpected content type: {type}", "Неочікуваний тип вмісту: {type}"),
    "bad_type_unknown": ("Unexpected content type: unknown", "Неочікуваний тип вмісту: невідомо"),
}


def tr(lang, key, **params):
    """Text for key in lang; unknown languages fall back to English."""
    index = SUPPORTED.index(lang) if lang in SUPPORTED else SUPPORTED.index(DEFAULT)
    return _TEXT[key][index].format(**params)


class MediaError(RuntimeError):
    """An error whose message is translated when it is shown. str() gives the English text."""

    def __init__(self, key, **params):
        self.key = key
        self.params = params
        super().__init__(tr(DEFAULT, key, **params))


def error_text(error, lang):
    """Message for an error in lang. Translated for MediaError; other errors keep their own text."""
    if isinstance(error, MediaError):
        return tr(lang, error.key, **error.params)
    return str(error)
