"""Every page the navigation points at must exist, and must not need the internet."""
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

PAGES = ["/", "/inventory", "/admin", "/monitor"]


@pytest.mark.parametrize("path", PAGES)
def test_page_is_reachable(client, path):
    """Only the owner's pages remain; the browser till went in docs/research/09 D1."""
    r = client.get(path)
    assert r.status_code == 200
    assert "<html" in r.text.lower()


def test_no_page_loads_anything_from_the_internet():
    """The till sits on a shop counter that may have no connection."""
    offenders = []
    for f in (ROOT / "server" / "static").rglob("*"):
        if f.suffix not in {".html", ".css", ".js"}:
            continue
        text = f.read_text(encoding="utf-8")
        if "https://" in text or "http://" in text:
            offenders.append(f.name)
    assert offenders == [], f"these still fetch from the network: {offenders}"


def test_trained_weights_are_not_served_over_http(client):
    assert client.get("/models/chips_model.pt").status_code == 404


@pytest.mark.parametrize("path", PAGES)
def test_every_static_asset_a_page_names_resolves(client, path):
    """A stylesheet, script or font that 404s leaves the page in fallback fonts
    with no styling and no charts - silently.  So every URL is fetched."""
    html = client.get(path).text
    urls = set(re.findall(r'(?:href|src)="(/static/[^"]+)"', html))
    assert urls, f"{path} names no static assets"
    for url in urls:
        assert client.get(url).status_code == 200, url
        if url.endswith(".css"):
            css = client.get(url).text
            for font in set(re.findall(r"url\((/static/fonts/[^)]+)\)", css)):
                assert client.get(font).status_code == 200, font
