"""Size-capped, https-only HTTP helpers. Every remote read goes through here."""
import io
from urllib.parse import urlsplit

import requests

from .config import HTTP_HEADERS
from .messages import MediaError


def _open_https(url, max_bytes, types, params=None, timeout=30):
    """Open a streamed GET that stays on https and passes the size and type checks."""
    if urlsplit(url).scheme != "https":
        raise MediaError("https_only")
    response = requests.get(url, params=params, timeout=timeout, headers=HTTP_HEADERS, stream=True)
    try:
        response.raise_for_status()
        if urlsplit(response.url).scheme != "https":
            raise MediaError("redirect_blocked")
        declared = response.headers.get("Content-Length", "")
        if declared.isdigit() and int(declared) > max_bytes:
            raise MediaError("too_large")
        ctype = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if not ctype.startswith(types):
            if ctype:
                raise MediaError("bad_type", type=ctype)
            raise MediaError("bad_type_unknown")
    except BaseException:
        response.close()
        raise
    return response


def _copy_capped(response, fh, max_bytes):
    written = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        written += len(chunk)
        if written > max_bytes:
            raise MediaError("too_large_stream")
        fh.write(chunk)


def http_get(url, max_bytes, types, params=None):
    """Fetch a small remote body (API reply, thumbnail) under the same limits as file saves."""
    with _open_https(url, max_bytes, types, params) as response:
        body = io.BytesIO()
        _copy_capped(response, body, max_bytes)
        return body.getvalue()


def save_url(url, path, max_bytes, types):
    """Stream a remote file to path; a failed or oversized transfer raises and leaves a partial file."""
    with _open_https(url, max_bytes, types) as response, open(path, "wb") as fh:
        _copy_capped(response, fh, max_bytes)
