"""Download release build tools from upstream; verify locked EXE hashes before use."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

from build import ROOT, check_tools

DOWNLOADS = {
    'deno.exe': ('https://github.com/denoland/deno/releases/download/v2.9.8/deno-x86_64-pc-windows-msvc.zip', 'deno.exe'),
    'ffmpeg.exe': ('https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip', 'ffmpeg.exe'),
    'spotdl.exe': ('https://github.com/spotDL/spotify-downloader/releases/download/v4.6.0/spotdl-4.6.0-win32.exe', None),
    'yt-dlp.exe': ('https://github.com/yt-dlp/yt-dlp/releases/download/2026.10.26/yt-dlp.exe', None),
}


def main():
    manifest = json.loads((ROOT / 'build_bin/tools.lock.json').read_text(encoding='utf-8'))
    destination = ROOT / 'build_bin'
    destination.mkdir(exist_ok=True)
    for name, (url, member_name) in DOWNLOADS.items():
        with tempfile.TemporaryDirectory() as folder:
            downloaded = Path(folder) / 'download'
            print(f'Downloading {name}', flush=True)
            request = urllib.request.Request(url, headers={'User-Agent': 'MediaDownloader-build'})
            with urllib.request.urlopen(request, timeout=120) as response, downloaded.open('wb') as target:
                shutil.copyfileobj(response, target)
            candidate = downloaded
            if member_name:
                candidate = Path(folder) / name
                with zipfile.ZipFile(downloaded) as archive:
                    members = [info for info in archive.infolist()
                               if not info.is_dir() and Path(info.filename).name == member_name]
                    if len(members) != 1:
                        raise RuntimeError(f'Expected exactly one {member_name} in {url}')
                    with archive.open(members[0]) as source, candidate.open('wb') as target:
                        shutil.copyfileobj(source, target)
            with candidate.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != manifest[name]['sha256']:
                raise RuntimeError(f'Hash mismatch for {name}; refusing to use downloaded binary')
            shutil.copyfile(candidate, destination / name)
    check_tools()


if __name__ == '__main__':
    main()
