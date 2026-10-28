# Build through scripts/build.py; all paths are relative to this repository.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parent
datas, extra_binaries, hiddenimports = collect_all('webview')
datas += [(str(root / 'web'), 'web'),
          (str(root / 'assets'), 'assets'),
          (str(root / 'third_party'), 'third_party'),
          (str(root / 'THIRD_PARTY_NOTICES.md'), '.'),
          (str(root / 'LICENSE'), '.')]
binaries = [(str(root / 'build_bin' / name), '.')
            for name in ('ffmpeg.exe', 'deno.exe', 'spotdl.exe', 'yt-dlp.exe')]
a = Analysis([str(root / 'app.py')], pathex=[str(root)],
             binaries=binaries + extra_binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['numpy', 'cryptography', 'pytest'],
             noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='MediaDownloader',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=[str(root / 'assets' / 'app.ico')],
          version=str(root / 'build' / 'windows-version.txt'))
