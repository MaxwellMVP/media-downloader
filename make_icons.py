# -*- coding: utf-8 -*-
"""Generate icons: app.ico + platform badge pngs -> assets/"""
import os
import math
from PIL import Image, ImageDraw

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(out, exist_ok=True)


def rounded(draw, box, r, fill):
    draw.rounded_rectangle(box, radius=r, fill=fill)

# ---------- YouTube icon: red rounded square + white triangle
def yt(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = size * 0.08
    rounded(d, [m, m, size - m, size - m], size * 0.28, (255, 0, 51, 255))
    # white play triangle
    cx, cy = size / 2, size / 2
    w = size * 0.20
    h = size * 0.24
    d.polygon([(cx - w * 0.6, cy - h), (cx - w * 0.6, cy + h), (cx + w, cy)], fill="white")
    return img

# ---------- Spotify icon: green circle + 3 white arcs
def sp(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, size - 1, size - 1], fill=(30, 185, 84, 255))
    for offset, width, frac in ((0.62, size * 0.09, 0.34), (0.40, size * 0.11, 0.28), (0.18, size * 0.13, 0.22)):
        y = size * frac
        w = size * 0.62
        d.arc([size * 0.16, y - width, size * 0.16 + w, y + width],
              start=200, end=340, fill="white", width=int(width))
    return img

# ---------- TikTok icon: dark circle + note with cyan/pink shadows
def tt(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, size - 1, size - 1], fill=(17, 17, 17, 255))
    # stylized note: vertical stem + flag + circle foot
    def note(dx, dy, color):
        x = size * 0.44 + dx
        w = size * 0.09
        top = size * 0.22 + dy
        bottom = size * 0.62 + dy
        d.ellipse([x - w, bottom, x + w, bottom + w * 2], fill=color)          # foot
        d.rectangle([x - w * 0.9, top, x + w * 0.9, bottom + w], fill=color)   # stem
        d.arc([x - w * 2.4, top - size * 0.16, x + w, top + w * 1.4],
              start=270, end=110, fill=color, width=int(size * 0.11))          # flag
    note(size * 0.06, size * 0.06, (37, 244, 238, 255))
    note(-size * 0.06, -size * 0.06, (254, 44, 85, 255))
    note(0, 0, (255, 255, 255, 255))
    return img

# ---------- App icon: dark rounded square + blue gradient + down arrow into tray
def app_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # vertical gradient inside rounded square
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(79 + (167 - 79) * t)   # #4f6ef7 -> #a76cf0
        g = int(110 + (108 - 110) * t)
        b = int(247 + (240 - 247) * t)
        gd.line([(0, y), (size, y)], fill=(r, g, b, 255))
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    m = size * 0.06
    md.rounded_rectangle([m, m, size - m, size - m], radius=size * 0.24, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # down arrow (thicker & bolder so it reads at 16-48 px)
    cx = size * 0.5
    shaft = size * 0.085
    head = size * 0.20
    d.rectangle([cx - shaft, size * 0.26, cx + shaft, size * 0.54], fill="white")
    d.polygon([(cx - head, size * 0.50), (cx + head, size * 0.50), (cx, size * 0.74)], fill="white")
    return img


# ---------- Folder-download button icon
def folder_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    body = (233, 236, 245, 255)
    tab = (190, 196, 212, 255)
    s = size
    d.rounded_rectangle([s * 0.08, s * 0.22, s * 0.62, s * 0.36], radius=s * 0.06, fill=tab)
    d.rounded_rectangle([s * 0.08, s * 0.32, s * 0.92, s * 0.82], radius=s * 0.08, fill=body)
    # small down arrow inside folder
    d.rectangle([s * 0.46, s * 0.44, s * 0.54, s * 0.62], fill=(90, 100, 130, 255))
    d.polygon([(s * 0.40, s * 0.60), (s * 0.60, s * 0.60), (s * 0.50, s * 0.72)], fill=(90, 100, 130, 255))
    return img

# save pngs
for name, fn, sz in (("yt.png", yt, 128), ("sp.png", sp, 128), ("tt.png", tt, 128), ("folder.png", folder_icon, 64)):
    fn(sz).save(os.path.join(out, name))

# save app.ico with multiple sizes
base = 256
img = app_icon(base)
img.save(os.path.join(out, "app.png"))
img.save(os.path.join(out, "app.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icons saved to", out)
