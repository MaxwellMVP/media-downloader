# Збирання Media Downloader v0.3

Потрібні Windows 10/11 x64, Python 3.12 x64 та Inno Setup 6.6 або новіший.
Для поточного релізу використано Python 3.12.14, PyInstaller 6.22.3 та Inno Setup 6.7.3.

## Середовище

У PowerShell із кореня репозиторію:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt -r requirements-build.txt
```

Додай чотири EXE до `build_bin/` відповідно до [інструкції](build_bin/README.md).
Вони не входять до Git і до архіву вихідного коду. Їхні хеші зафіксовані в
`build_bin/tools.lock.json` і перевіряються перед збиранням.

Ліцензійні тексти лежать у `third_party/`. Якщо змінюєш версії Python-пакетів,
онови тексти через `python scripts/collect_licenses.py` у середовищі з цими пакетами.

## Перевірка

```powershell
.\.venv\Scripts\python.exe -m unittest test_app -v
```

Тести логіки не потребують мережі чи допоміжних EXE. Для перевірки справжніх
віджетів на доступному робочому столі додатково встанови
`$env:MEDIADL_GUI_TESTS='1'`. GUI-перевірки використовують реальні локальні
медіафайли з проєктної папки `Downloads/`; цей каталог не входить до репозиторію.

## Portable та інсталятор

Закрий запущену програму, щоб Windows дозволила замінити EXE.

```powershell
.\.venv\Scripts\python.exe scripts/build.py --iscc 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
.\.venv\Scripts\python.exe scripts/package_release.py
```

Для збирання лише portable пропусти `--iscc`. Для повторного збирання лише
інсталятора додай `--skip-portable`; він використає поточний файл у `Portable/`.

Версія береться з `APP_VER` у `app.py`. Скрипт генерує Windows FileVersion і
ProductVersion, збирає EXE, а потім передає ту саму версію Inno Setup.

Результати:

```text
Portable/MediaDownloader.exe
Release/v0.3/MediaDownloader-v0.3-Setup.exe
Release/v0.3/MediaDownloader-v0.3-Portable.zip
Release/v0.3/MediaDownloader-v0.3-Source.zip
Release/v0.3/SHA256SUMS.txt
GitHub/MediaDownloader-v0.3-Source.zip
```

## Інсталятор

Встановлення за замовчуванням: `%LOCALAPPDATA%\Programs\Media Downloader`.
Права адміністратора не потрібні. Ярлик меню «Пуск» створюється автоматично,
ярлик робочого столу — за бажанням. Видалення доступне через налаштування Windows.
Завантажені медіафайли зберігаються поза каталогом програми та не видаляються
деінсталятором. Історія завжди починається порожньою в новій сесії.
Setup і деінсталятор перевіряють mutex програми та просять закрити її перед змінами.

Для ізольованої перевірки можна запустити Setup з `/VERYSILENT /SUPPRESSMSGBOXES
/NORESTART /TestMode=1 /DIR="абсолютний шлях до тестової папки"`. TestMode не
створює ярликів і запису в списку програм, але створює деінсталятор у цій папці.

Поточні файли зібрані без Authenticode-сертифіката видавця. Перед публікацією
ознайомся з [ліцензіями компонентів](THIRD_PARTY_NOTICES.md).
