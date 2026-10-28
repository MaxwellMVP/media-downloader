"""File naming and publishing: downloads are staged first and only then made visible."""
import os
import re
import tempfile

from .config import MAX_IMAGE_BYTES, TYPES_IMAGE
from .network import save_url


def sanitize(name):
    """Make a title safe for Windows file names (no reserved characters, bounded length)."""
    name = re.sub(r'[\\/:*?"<>|]+', "", name or "media").strip()[:120].strip(" .")
    return name or "media"


def publish_file(staged, dest, name):
    """Move a complete staged file into dest without replacing existing files."""
    stem, ext = os.path.splitext(name)
    index = 0
    while True:
        target = os.path.join(dest, name if not index else "%s (%d)%s" % (stem, index, ext))
        try:
            # Windows rename is atomic and fails if the destination already exists.
            os.rename(staged, target)
            return target
        except FileExistsError:
            index += 1


def download_file(url, dest, name, max_bytes=MAX_IMAGE_BYTES, types=TYPES_IMAGE):
    """Download url into dest/name through a hidden staging folder; partial files never appear."""
    with tempfile.TemporaryDirectory(prefix=".mediadl-", dir=dest) as work:
        staged = os.path.join(work, name)
        save_url(url, staged, max_bytes, types)
        return publish_file(staged, dest, name)
