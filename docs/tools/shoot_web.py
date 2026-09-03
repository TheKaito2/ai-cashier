#!/usr/bin/env python3
"""Screenshot web pages to PNG.

usage: shoot_web.py <outdir> <base_url> <path:name:theme[:full]> ...
SHOT_W / SHOT_H set the viewport (default 1440x900).
"""
import os, sys, pathlib
from playwright.sync_api import sync_playwright

out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
base = sys.argv[2].rstrip('/')
jobs = [a.split(':') for a in sys.argv[3:]]   # path, name, theme, optional 'full'

with sync_playwright() as p:
    b = p.chromium.launch()
    for job in jobs:
        path, name, theme = job[:3]
        full = len(job) > 3 and job[3] == 'full'
        pg = b.new_page(viewport={'width': int(os.environ.get('SHOT_W', 1440)), 'height': int(os.environ.get('SHOT_H', 900))}, device_scale_factor=2)
        pg.goto(f"{base}/{path.lstrip('/')}", wait_until='networkidle')
        pg.evaluate("t => { localStorage.setItem('theme', t); document.documentElement.setAttribute('data-theme', t); }", theme)
        pg.wait_for_timeout(900)
        f = out / f"{name}.png"
        pg.screenshot(path=str(f), full_page=full)
        print(f"  {f.name}  {f.stat().st_size//1024} KB")
        pg.close()
    b.close()
