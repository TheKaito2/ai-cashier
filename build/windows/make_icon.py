#!/usr/bin/env python3
"""Draw the app icon: the till's orange, a white ring for the camera, a bar for
the mat.  Writes build/windows/icon.ico (and a 256-px PNG for the landing page)."""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ORANGE, INK, WHITE = (255, 122, 24), (14, 17, 22), (255, 255, 255)


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = size // 5
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=ORANGE)
    cx, cy = size // 2, int(size * 0.42)
    ring = int(size * 0.2)
    d.ellipse((cx - ring, cy - ring, cx + ring, cy + ring), outline=WHITE, width=max(2, size // 14))
    d.ellipse((cx - ring // 3, cy - ring // 3, cx + ring // 3, cy + ring // 3), fill=WHITE)
    d.rounded_rectangle((int(size * 0.18), int(size * 0.74), int(size * 0.82), int(size * 0.84)),
                        radius=size // 30, fill=INK)
    return img


if __name__ == "__main__":
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [draw(s) for s in sizes]
    frames[-1].save(HERE / "icon.ico", format="ICO", sizes=[(s, s) for s in sizes],
                    append_images=frames[:-1])
    frames[-1].save(HERE / "icon-256.png")
    print("wrote", HERE / "icon.ico")
