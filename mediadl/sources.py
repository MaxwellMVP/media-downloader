"""URL classification and user-facing text."""
import os
import re
from urllib.parse import urlsplit

from .messages import DEFAULT, tr

_DOMAINS = (("spotify.com", "spotify"), ("tiktok.com", "tiktok"),
            ("youtube.com", "youtube"), ("youtu.be", "youtube"))
_YOUTUBE_ID = re.compile(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})")


def platform_for(url):
    """Return 'spotify', 'tiktok', 'youtube' or None, matching the hostname only."""
    try:
        host = (urlsplit(url.strip()).hostname or "").lower()
    except ValueError:
        return None
    for domain, platform in _DOMAINS:
        if host == domain or host.endswith("." + domain):
            return platform
    return None


def youtube_thumbnail_url(url):
    """Thumbnail URL for a YouTube link, or None when the link has no video id."""
    match = _YOUTUBE_ID.search(url or "")
    if match:
        return "https://i.ytimg.com/vi/%s/mqdefault.jpg" % match.group(1)
    return None


def saved_text(dest, lang=DEFAULT):
    """Success message naming the folder the files were saved to."""
    return tr(lang, "saved", folder=os.path.basename(os.path.normpath(dest)) or dest)
