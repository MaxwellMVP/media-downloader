# SignPath application draft

Submit this description using the official application form. Review the team's
roles and confirm MFA before submission. This draft has not been submitted.

**Project:** Media Downloader

**Repository:** https://github.com/MaxwellMVP/media-downloader

**Existing Windows release:** https://github.com/MaxwellMVP/media-downloader/releases/tag/v0.3

**License:** MIT for the project's own code. Open-source dependencies retain their
respective licenses, documented in THIRD_PARTY_NOTICES.md and third_party/.

**Description:** A Windows desktop application to download user-supplied YouTube,
TikTok and Spotify media links as video, audio or photos, using upstream open-source
tools yt-dlp, FFmpeg, Deno and spotDL. There is no advertising or telemetry service.

**Artifacts to sign:** The project's PyInstaller-built MediaDownloader.exe and
Inno Setup installer. Upstream helper binaries will not be re-signed.

**Build provenance:** Public GitHub Actions workflow
`.github/workflows/release.yml`, GitHub-hosted Windows runners, reviewed main
branch. Builds use pinned Python dependencies and hash-checked upstream helpers.
Application signing precedes installer compilation; installer signing follows it.
Each signing request requires manual approval. Production signing is not active yet.

**Policy:** https://github.com/MaxwellMVP/media-downloader/blob/main/docs/CODE_SIGNING.md

**Maintainer / reviewer / signing approver:** MaxwellMVP
(https://github.com/MaxwellMVP).

Please assess the project's eligibility and advise on required artifact and build
origin restrictions, including the PyInstaller bundle with upstream helper tools.
