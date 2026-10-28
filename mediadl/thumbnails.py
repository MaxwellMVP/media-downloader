"""Thumbnails: extraction, caching and the rounded tile preview. Safe to call from worker threads."""
import hashlib
import io
import os
import subprocess

from PIL import Image, ImageDraw, ImageOps

from .config import (CARD_H, CARD_HOVER, CARD_W, HIDDEN_PROCESS, MAX_IMAGE_BYTES,
                     TYPES_IMAGE, cache_path, exe, log)
from .network import http_get

THUMB_SIZE = (200, 200)
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXTS = (".mp4", ".mkv", ".webm")


def extract_embedded_cover(mp3_path, out_png):
    """Save the ID3 APIC cover of an MP3 as a thumbnail. Returns False when there is none."""
    try:
        from mutagen.id3 import ID3
        tags = ID3(mp3_path)
        for frame in tags.getall("APIC"):
            img = Image.open(io.BytesIO(frame.data))
            img.thumbnail(THUMB_SIZE)
            img.convert("RGB").save(out_png)
            return True
    except Exception:
        log.debug("No readable embedded cover in %s", mp3_path, exc_info=True)
    return False


def make_placeholder(kind, color, size=THUMB_SIZE):
    """Flat placeholder drawn with shapes (font glyphs are not reliable)."""
    img = Image.new("RGB", size, color)
    d = ImageDraw.Draw(img)
    w, h = size
    fg = "#5d6684"
    if kind == "music":
        r = int(w * 0.032)
        for cx, cy, top in ((0.44, 0.60, 0.38), (0.60, 0.55, 0.33)):
            d.ellipse([w * cx - r, h * cy - r, w * cx + r, h * cy + r], fill=fg)
            d.rectangle([w * cx + r * 0.55, h * top, w * cx + r * 1.3, h * cy], fill=fg)
        d.polygon([(w * 0.47, h * 0.40), (w * 0.62, h * 0.36), (w * 0.62, h * 0.42),
                   (w * 0.47, h * 0.46)], fill=fg)
    else:
        d.polygon([(w * 0.45, h * 0.36), (w * 0.45, h * 0.64), (w * 0.62, h * 0.50)], fill=fg)
    return img


def _save_resized(source, png):
    source.thumbnail(THUMB_SIZE)
    source.convert("RGB").save(png)


def _remote_thumbnail(url, png):
    try:
        with Image.open(io.BytesIO(http_get(url, MAX_IMAGE_BYTES, TYPES_IMAGE))) as img:
            _save_resized(img, png)
        return True
    except Exception:
        log.warning("Remote thumbnail unavailable: %s", url, exc_info=True)
        return False


def _image_thumbnail(path, png):
    try:
        with Image.open(path) as img:
            _save_resized(img, png)
        return True
    except Exception:
        log.warning("Image thumbnail failed for %s", path, exc_info=True)
        return False


def _ffmpeg_frame(path, png):
    try:
        result = subprocess.run(
            [exe("ffmpeg.exe"), "-y", "-ss", "0", "-i", path,
             "-frames:v", "1", "-vf", "scale=200:-1", png],
            capture_output=True, timeout=10, **HIDDEN_PROCESS)
        if result.returncode == 0 and os.path.isfile(png):
            return True
        log.warning("ffmpeg thumbnail failed for %s: %s", path,
                    result.stderr.decode("utf-8", "replace")[-300:])
        return False
    except Exception:
        log.warning("ffmpeg could not run for %s", path, exc_info=True)
        return False


def _write_thumbnail(path, url, png):
    """Try each source in order (remote, embedded cover, image, video frame) and fall back to a placeholder."""
    ext = os.path.splitext(path)[1].lower()
    if url and _remote_thumbnail(url, png):
        return
    if ext == ".mp3" and extract_embedded_cover(path, png):
        return
    if ext in IMAGE_EXTS and _image_thumbnail(path, png):
        return
    if ext in VIDEO_EXTS and _ffmpeg_frame(path, png):
        return
    make_placeholder("music" if ext == ".mp3" else "video", CARD_HOVER).save(png)


def load_thumbnail(path, url=None):
    """Load a PIL thumbnail for a file. This function never touches Tk."""
    stat = os.stat(path)
    identity = "v4:%s:%s:%s" % (os.path.abspath(path), stat.st_size, stat.st_mtime_ns)
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    png = cache_path(key + ".png")
    if not os.path.exists(png):
        _write_thumbnail(path, url, png)
    try:
        with Image.open(png) as source:
            return tile_preview(source)
    except Exception:
        log.warning("Cached thumbnail unreadable: %s", png, exc_info=True)
        return None


def tile_preview(source):
    """Uniform crop and a legible play badge, composited without Tk backgrounds."""
    im = ImageOps.fit(source.convert("RGBA"), (CARD_W * 2, CARD_H * 2), Image.LANCZOS)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=14, fill=255)
    im.putalpha(mask)
    overlay = Image.new("RGBA", im.size)
    draw = ImageDraw.Draw(overlay)
    cx, cy, radius = im.width // 2, im.height // 2, 20
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(9, 15, 24, 155))
    draw.polygon(((cx - 5, cy - 9), (cx - 5, cy + 9), (cx + 9, cy)), fill=(245, 248, 255, 240))
    return Image.alpha_composite(im, overlay)
