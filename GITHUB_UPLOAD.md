# Завантаження на GitHub

## 1. Вихідний код

У папці `GitHub/` підготовлено `MediaDownloader-v0.3-Source.zip`.
Розпакуй його й завантаж **вміст**, включно з прихованими `.github/`,
`.gitignore` та `.gitattributes`, у порожній репозиторій. Не завантажуй сам ZIP
як єдиний файл репозиторію: тоді GitHub не побачить README та код.

Альтернатива — Git із кореня проєкту:

```text
git init
git add .
git status
git commit -m "Release Media Downloader v0.3"
git branch -M main
git remote add origin <URL вашого нового репозиторію>
git push -u origin main
```

Перед commit перевір список `git status`: медіафайлів, EXE, резервних копій,
кешів, `.venv`, `Portable`, `Release` та `GitHub` там бути не повинно.
Шаблон `.gitignore` вже виключає ці файли.

## 2. Файли для користувачів

У репозиторії відкрий **Releases → Draft a new release**, створи тег `v0.3`,
назву `Media Downloader v0.3` і встав опис із `Release/v0.3/RELEASE_NOTES.md`.
Прикріпи файли з `Release/v0.3/`:

- `MediaDownloader-v0.3-Setup.exe` — версія зі встановленням;
- `MediaDownloader-v0.3-Portable.zip` — версія без встановлення;
- `MediaDownloader-v0.3-Source.zip` — знімок вихідного коду;
- `SHA256SUMS.txt` — контрольні суми.

EXE не потрібно комітити в Git: звичайний GitHub репозиторій блокує файли
понад 100 MiB. Великі дистрибутиви слід додавати до Releases:
https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github

Тексти ліцензій і точні джерела компонентів наведені в `THIRD_PARTY_NOTICES.md`.
MIT стосується вашого коду, а не автоматично всіх вбудованих сторонніх програм.
Не видаляй ліцензійні файли з архівів; при публікації GPL-компонентів забезпеч
доступ до відповідних вихідних кодів та збережи посилання на них у релізі.

Після першого push GitHub Actions запускатиме Windows unit-тести. Цей workflow
не публікує релізи та нічого не завантажує від вашого імені.
