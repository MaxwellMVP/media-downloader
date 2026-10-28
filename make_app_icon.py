# -*- coding: utf-8 -*-
"""ico.jpg -> remove background (rembg with glow-friendly alpha) -> app.ico"""
import os
from PIL import Image

A = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
src = os.path.join(A, "ico.jpg")

try:
    from rembg import remove, new_session
    session = new_session("isnet-general-use")  # good with glow/soft edges
    with open(src, "rb") as f:
        cut = remove(Image.open(f).convert("RGBA"), session=session)
    print("rembg OK (isnet)")
except Exception as e:
    print("rembg failed:", e, "- falling back to corner-based flood mask")
    img = Image.open(src).convert("RGBA")
    from PIL import ImageOps
    # simple background removal: key out the uniform gray background
    import numpy as np
    arr = np.array(img).astype(int)
    corners = [arr[0, 0, :3], arr[0, -1, :3], arr[-1, 0, :3], arr[-1, -1, :3]]
    bg = sum(corners) / 4.0
    dist = ((arr[:, :, :3] - bg) ** 2).sum(axis=2) ** 0.5
    alpha = (dist > 28) * 255
    arr[:, :, 3] = alpha.astype("uint8")
    cut = Image.fromarray(arr.astype("uint8"))

# trim transparent borders
bbox = cut.split()[3].getbbox()
if bbox:
    cut = cut.crop(bbox)

cut = cut.resize((256, 256), Image.LANCZOS)
cut.save(os.path.join(A, "app.png"))
cut.save(os.path.join(A, "app.ico"),
         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("app.ico saved", cut.size)
