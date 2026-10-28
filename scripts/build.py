"""Build the Windows portable executable and optional Inno Setup installer."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def version():
    tree = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'APP_VER' for t in node.targets):
            return ast.literal_eval(node.value).removeprefix('v')
    raise RuntimeError('APP_VER not found')


def check_tools():
    manifest = json.loads((ROOT / 'build_bin/tools.lock.json').read_text(encoding='utf-8'))
    for name, item in manifest.items():
        path = ROOT / 'build_bin' / name
        if not path.is_file():
            raise RuntimeError(f'Missing {path.name}; see build_bin/README.md')
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != item['sha256']:
            raise RuntimeError(f'{name} does not match build_bin/tools.lock.json')


def write_version_info(app_version):
    parts = tuple(int(p) for p in app_version.split('.'))
    numeric = (parts + (0, 0, 0, 0))[:4]
    file = ROOT / 'build/windows-version.txt'
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeric!r}, prodvers={numeric!r},
    mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'Media Downloader'),
    StringStruct('FileVersion', '{app_version}'),
    StringStruct('ProductName', 'Media Downloader'),
    StringStruct('ProductVersion', '{app_version}'),
    StringStruct('OriginalFilename', 'MediaDownloader.exe')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
''', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iscc', help='Path to Inno Setup 6.6+ ISCC.exe; omit to build only portable')
    parser.add_argument('--skip-portable', action='store_true', help='Reuse existing Portable/MediaDownloader.exe')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Windows is required')
    app_version = version()
    output = ROOT / 'Release' / ('v' + app_version)
    output.mkdir(parents=True, exist_ok=True)
    check_tools()
    if not args.skip_portable:
        write_version_info(app_version)
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm',
                        str(ROOT / 'packaging/MediaDownloader.spec'),
                        '--distpath', str(ROOT / 'Portable'),
                        '--workpath', str(ROOT / 'build/pyinstaller')], cwd=ROOT, check=True)
    if not (ROOT / 'Portable/MediaDownloader.exe').is_file():
        raise RuntimeError('Portable executable is missing')
    if args.iscc:
        compiler = shutil.which(args.iscc) or args.iscc
        subprocess.run([compiler, '/Qp', '/DAppVersion=' + app_version,
                        '/DReleaseDir=' + str(output), str(ROOT / 'packaging/windows/installer.iss')],
                       cwd=ROOT, check=True)
    print(f'Build ready: {output}')


if __name__ == '__main__':
    main()
