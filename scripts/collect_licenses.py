"""Copy installed runtime package license texts for redistribution."""
from importlib import metadata
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ['pywebview', 'pythonnet', 'clr-loader', 'cffi', 'pycparser', 'bottle',
            'typing-extensions', 'pillow', 'requests', 'mutagen',
            'packaging', 'charset-normalizer', 'idna', 'urllib3', 'certifi']
# Wheels that ship no license file. Their name and version go to VERSIONS.txt only;
# the MIT text must be added by hand to third_party/python-packages/proxy-tools/.
NO_LICENSE_FILE = ['proxy-tools']


def main():
    destination = ROOT / 'third_party/python-packages'
    lines = []
    for name in PACKAGES:
        distribution = metadata.distribution(name)
        target = destination / name
        target.mkdir(parents=True, exist_ok=True)
        copied = 0
        for entry in distribution.files or []:
            if any(token in entry.name.lower() for token in ('license', 'licence', 'copying', 'notice')):
                source = distribution.locate_file(entry)
                if source.is_file() and source.suffix != '.pyc':
                    relative = Path(str(entry))
                    parts = relative.parts
                    # Preserve nested license names without embedding machine paths.
                    start = next((i + 1 for i, p in enumerate(parts) if p.endswith('.dist-info')), 0)
                    local = Path(*parts[start:]) if start else Path(relative.name)
                    output = target / local
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, output)
                    copied += 1
        if copied == 0:
            raise RuntimeError(f'No installed license text found for {name}')
        lines.append(f'{name}=={distribution.version}')
    for name in NO_LICENSE_FILE:
        lines.append(f'{name}=={metadata.version(name)}  (license text to be added manually)')
    (destination / 'VERSIONS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError(f'CPython license text not found: {python_license}')
    shutil.copy2(python_license, destination / 'CPython-LICENSE.txt')
    print(f'Licenses copied: {destination}')


if __name__ == '__main__':
    main()


if __name__ == '__main__':
    main()
