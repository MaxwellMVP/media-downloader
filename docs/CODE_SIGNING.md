# Code signing policy

## Status

SignPath integration is prepared, but access to a production certificate has not
been approved or configured yet. The published v0.3 files are unsigned.
This page does not claim that SignPath has accepted this project.

The intended service is free code signing provided by [SignPath.io](https://signpath.io),
certificate by [SignPath Foundation](https://signpath.org), **subject to approval**.

## Scope and team

- Project: [MaxwellMVP/media-downloader](https://github.com/MaxwellMVP/media-downloader).
- Maintainer, reviewer and signing approver: [MaxwellMVP](https://github.com/MaxwellMVP).
- Contributions from other authors must be reviewed before a signed release.
- All people with repository/signing access must use multi-factor authentication.
- Only the project's own `MediaDownloader.exe` and its Inno Setup installer are
  submitted. FFmpeg, Deno, spotDL and yt-dlp are bundled as upstream components;
  they are not re-signed with the project's certificate.
- Every production request requires manual approval in SignPath. Signed artifacts
  must originate from GitHub-hosted builds of this repository's reviewed `main`.
- The generated Inno uninstaller is not separately signed by this integration.

## Privacy

The app initiates media downloads, metadata and thumbnail requests after a user
supplies a media link. It does not contain analytics or a telemetry reporting service.
These operations communicate with YouTube/Google, TikTok, Spotify, their CDNs and,
for TikTok photo posts, the tikwm.com API. Spotify lookup through spotDL may use
YouTube and other metadata providers. Their own privacy policies apply:
[Google](https://policies.google.com/privacy),
[TikTok](https://www.tiktok.com/legal/page/eea/privacy-policy/en),
[Spotify](https://www.spotify.com/legal/privacy-policy/),
[TikWM](https://www.tikwm.com/).
Remote services receive the requested URL or media identifier and normal network
request information, including IP address. The selected output folder, preferences
and diagnostic logs are local. The application does not upload downloaded files.

## Налаштування власником

1. Подай [заявку SignPath Foundation](https://signpath.org/apply), вкажи репозиторій,
   [реліз v0.3](https://github.com/MaxwellMVP/media-downloader/releases/tag/v0.3),
   MIT для власного коду та окремі ліцензії bundled-компонентів.
   Для заявки можна використати [підготовлений опис](SIGNPATH_APPLICATION.md).
   Видачу доступу не гарантовано: сервіс оцінює також репутацію проєкту.
2. Після схвалення встанови офіційний
   [SignPath GitHub App](https://github.com/apps/signpath) лише для цього репозиторію.
   У SignPath підключи Trusted Build System **GitHub.com** до проєкту.
3. Створи в SignPath дві artifact configurations зі slug `portable` та `installer`.
   Імпортуй відповідні XML із `packaging/signpath/`. Обидві конфігурації приймають
   ZIP артефакти GitHub і обов'язковий параметр `version`; перевіряють ProductName
   та ProductVersion. Не додавай маску для підпису сторонніх EXE.
4. Створи production signing policy з виданим Foundation сертифікатом,
   ручним підтвердженням MaxwellMVP та доступом submitter для CI.
   Обмеж перевірку походження репозиторієм `MaxwellMVP/media-downloader`, `main`,
   workflow `.github/workflows/release.yml` і GitHub-hosted runners.
   Узгодь конфігурації та політику з SignPath під час onboarding.
5. У [GitHub Environments](https://github.com/MaxwellMVP/media-downloader/settings/environments)
   створи `signpath-production`: дозволена deployment branch лише `main`,
   required reviewer — MaxwellMVP (дозволь власнику підтверджувати свої запуски).
   Додай environment secret `SIGNPATH_API_TOKEN` із мінімальними правами submitter.
   **Не додавай токен у код, issues або чат.**
6. У цьому environment додай variables:

   | Назва | Значення з SignPath |
   |---|---|
   | `SIGNPATH_ORGANIZATION_ID` | Organization ID, UUID |
   | `SIGNPATH_PROJECT_SLUG` | Slug проєкту |
   | `SIGNPATH_SIGNING_POLICY_SLUG` | Slug production signing policy |

7. Спочатку в Actions → **Windows release build** → Run workflow вибери `main`
   й залиш `sign=false`. Перевір збірку та артефакт `unsigned-release`.
   Потім запусти з `sign=true`, підтвердь environment і **два** запити в SignPath:
   спершу portable, потім Setup. На кожне підтвердження передбачено 45 хвилин.
8. Workflow перевіряє довіру Windows, timestamp та видавця SignPath Foundation.
   Якщо підпис відсутній/недовірений, він завершується помилкою й не створює
   `signed-release`. Самопідписані test certificates не пройдуть цю перевірку.
9. Забери `signed-release` з поточного запуску. SHA256 формується **після** підпису.
   Перевір portable та встановлення/видалення Setup, потім опублікуй новий реліз
   із новою версією та посиланням на цю policy. Workflow не замінює наявний v0.3.
10. Після підтвердженого production підпису онови Status цієї сторінки та
    формулювання про unsigned файли в документації нового релізу.

Підпис підтверджує видавця й цілісність. Він не гарантує миттєвого зникнення
SmartScreen-попереджень на всіх комп'ютерах.

## Перевірка користувачем

У PowerShell (для майбутніх підписаних файлів):

```powershell
Get-AuthenticodeSignature .\MediaDownloader.exe |
  Format-List Status,SignerCertificate,TimeStamperCertificate
```

Очікується `Status: Valid`, сертифікат SignPath Foundation та timestamp.
Сума SHA256 сама по собі не є цифровим підписом видавця.

Джерела: [умови SignPath](https://signpath.org/terms),
[GitHub integration](https://docs.signpath.io/trusted-build-systems/github),
[Windows signing options](https://learn.microsoft.com/windows/apps/package-and-deploy/code-signing-options).
