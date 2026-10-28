"""Make clean source/portable archives and SHA-256 sums; never uploads files."""
import hashlib
from pathlib import Path
import shutil
import zipfile
from build import ROOT, version

SOURCE_FILES = ['app.py', 'test_app.py', 'make_app_icon.py', 'make_icons.py',
                'README.md', 'BUILDING.md', 'GITHUB_UPLOAD.md', 'LICENSE',
                'THIRD_PARTY_NOTICES.md', 'CHANGELOG.md', 'requirements.txt',
                'requirements-lock.txt', 'requirements-build.txt', '.gitignore', '.gitattributes',
                'build_bin/README.md', 'build_bin/tools.lock.json']
SOURCE_DIRS = ['assets', 'web', 'mediadl', 'packaging', 'scripts', '.github', 'third_party', 'docs']


def sources():
    paths = [ROOT / name for name in SOURCE_FILES]
    for folder in SOURCE_DIRS:
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.exe', '.bak'))
    for path in paths:
        if not path.is_file():
            raise RuntimeError(f'Missing source file: {path.relative_to(ROOT)}')
        if path.stat().st_size >= 25 * 1024 * 1024:
            raise RuntimeError(f'Unexpected large source file: {path.name}')
    return sorted(set(paths))


def main():
    app_version = version()
    output = ROOT / 'Release' / ('v' + app_version)
    output.mkdir(parents=True, exist_ok=True)
    executable = ROOT / 'Portable/MediaDownloader.exe'
    installer = output / f'MediaDownloader-v{app_version}-Setup.exe'
    if not executable.is_file() or not installer.is_file():
        raise RuntimeError('Build both portable and installer before packaging')
    with zipfile.ZipFile(output / f'MediaDownloader-v{app_version}-Portable.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(executable, 'MediaDownloader.exe')
        for path in [ROOT / 'LICENSE', ROOT / 'THIRD_PARTY_NOTICES.md', ROOT / 'docs/PORTABLE_README.txt']:
            archive.write(path, path.name)
        for path in (ROOT / 'third_party').rglob('*'):
            if path.is_file():
                archive.write(path, str(Path('licenses') / path.relative_to(ROOT / 'third_party')))
    source_zip = output / f'MediaDownloader-v{app_version}-Source.zip'
    with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sources():
            archive.write(path, path.relative_to(ROOT).as_posix())
    github_dir = ROOT / 'GitHub'
    github_dir.mkdir(exist_ok=True)
    shutil.copy2(source_zip, github_dir / source_zip.name)
    shutil.copy2(ROOT / 'docs/RELEASE_NOTES.md', output / 'RELEASE_NOTES.md')
    files = sorted(p for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS.txt')
    lines = []
    for file in files:
        with file.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        lines.append(f'{digest}  {file.name}')
    (output / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Release files: {output}')
    print(f'GitHub source upload: {github_dir / source_zip.name}')


if __name__ == '__main__':
    main()
