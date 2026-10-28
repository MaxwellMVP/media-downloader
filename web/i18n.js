"use strict";

// Page translations. Engine messages are translated in mediadl/messages.py.
// Static markup uses data-i18n (text), data-i18n-title (title) and data-i18n-label (aria-label).

const I18N = {
  en: {
    settings: "Settings",
    choose_folder: "Downloads folder…",
    open_folder: "Open folder",
    menu_language: "Language",
    lang_name: "English",
    minimize: "Minimize",
    maximize: "Maximize",
    restore: "Restore",
    close: "Close",
    platforms_label: "Platforms",
    format_label: "Format",
    hint: "Paste a link from TikTok, YouTube or Spotify",
    format_video: "Video MP4",
    format_video_sub: "Best quality",
    format_music: "Music",
    download: "Download",
    downloading: "Downloading...",
    loading: "Starting download...",
    need_link: "Paste a link first!",
    busy: "Wait — a download is still running.",
    folder_set: "Folder: {folder}",
    open_failed: "Could not open the folder.",
    spotify_notice: "Spotify does not provide video (DRM) — downloading as Music MP3",
    play_title: "Play: {name}",
    show_in_folder: "Show in folder",
    empty_title: "No downloads in this session yet",
    empty_sub: "Paste a link and press “Download”",
  },
  uk: {
    settings: "Налаштування",
    choose_folder: "Папка завантажень…",
    open_folder: "Відкрити папку",
    menu_language: "Мова",
    lang_name: "Українська",
    minimize: "Згорнути",
    maximize: "Розгорнути",
    restore: "Відновити",
    close: "Закрити",
    platforms_label: "Платформи",
    format_label: "Формат",
    hint: "Встав посилання з TikTok, YouTube або Spotify",
    format_video: "Відео MP4",
    format_video_sub: "Найкраща якість",
    format_music: "Музика",
    download: "Завантажити",
    downloading: "Завантажую...",
    loading: "Завантаження...",
    need_link: "Встав посилання спочатку!",
    busy: "Зачекай — ще виконується завантаження.",
    folder_set: "Папка: {folder}",
    open_failed: "Не вдалося відкрити папку.",
    spotify_notice: "Spotify не віддає відео (DRM) — завантажую як Музика MP3",
    play_title: "Відтворити: {name}",
    show_in_folder: "Показати у папці",
    empty_title: "Завантажень у цій сесії ще немає",
    empty_sub: "Встав посилання та натисни «Завантажити»",
  },
};

const LANGUAGES = Object.keys(I18N);
let currentLang = "en";

function t(key, params = {}) {
  const table = I18N[currentLang] || I18N.en;
  const text = table[key] ?? I18N.en[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (match, name) => (name in params ? params[name] : match));
}

// Applies the language to static markup and returns the language in effect.
function setLanguage(lang) {
  currentLang = LANGUAGES.includes(lang) ? lang : "en";
  document.documentElement.lang = currentLang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
  });
  document.querySelectorAll("[data-i18n-label]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nLabel));
  });
  return currentLang;
}
