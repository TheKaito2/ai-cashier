#!/usr/bin/env python3
"""Render captured terminal text to a PNG.

usage: shoot_term.py <in.txt> <out.png> [title] [columns]

Long output is laid out in columns so the image stays landscape and readable
when it is dropped into a report at page width.
"""
import sys, pathlib
from PIL import Image, ImageDraw, ImageFont

src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
out.parent.mkdir(parents=True, exist_ok=True)
title = sys.argv[3] if len(sys.argv) > 3 else src.name
lines = src.read_text(errors="replace").rstrip().splitlines() or ["(empty)"]
COLS = int(sys.argv[4]) if len(sys.argv) > 4 else 1
if COLS > 1:
    per = -(-len(lines) // COLS)
    chunks = [lines[i * per:(i + 1) * per] for i in range(COLS)]
    chunks = [c + [""] * (per - len(c)) for c in chunks]
    pad = [max((len(l) for l in c), default=0) + 4 for c in chunks]
    lines = ["".join(c[r].ljust(pad[i]) for i, c in enumerate(chunks)).rstrip()
             for r in range(per)]

SIZE, PAD, LH, S = 26, 34, 34, 2                       # S = supersample for crisp text
for cand in ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf",
             "/System/Library/Fonts/Courier.ttc"):
    if pathlib.Path(cand).exists():
        font, bold = ImageFont.truetype(cand, SIZE * S), ImageFont.truetype(cand, SIZE * S)
        break
else:
    font = bold = ImageFont.load_default()

w = max(int(font.getlength(l)) for l in lines + [title]) + PAD * S * 2
h = (len(lines) + 3) * LH * S + PAD * S * 2
img = Image.new("RGB", (w, h), "#11161d")
d = ImageDraw.Draw(img)
d.rectangle([0, 0, w, (LH + 22) * S], fill="#1b2430")
for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
    d.ellipse([(PAD + i * 30) * S, 20 * S, (PAD + i * 30 + 16) * S, 36 * S], fill=c)
d.text((w // 2, 28 * S), title, font=bold, fill="#8fa0b4", anchor="mm")

PAL = {"$": "#7ee787", "✓": "#7ee787", "200": "#7ee787", "404": "#ff7b72",
       "ERROR": "#ff7b72", "WARN": "#e3b341"}
y = (PAD + LH + 22) * S
for l in lines:
    colour = "#c9d5e1"
    if l.lstrip().startswith("$"): colour = "#7ee787"
    elif any(k in l for k in ("ERROR", "Traceback", " 404", "FAILED")): colour = "#ff7b72"
    elif any(k in l for k in ("✓", "PASSED", "passed", " 200", "OK")): colour = "#79c0ff"
    d.text((PAD * S, y), l, font=font, fill=colour)
    y += LH * S

img.resize((w // S, h // S), Image.LANCZOS).save(out)
print(f"{out}  {out.stat().st_size // 1024} KB")
