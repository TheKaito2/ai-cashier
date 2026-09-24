"""The dashboard must be movable off 8000.

A Raspberry Pi that carries more than one project will already have something on
8000 - this was found when the till refused to start beside an unrelated service
and reported only "server did not come up within 30s".
"""
import socket
import urllib.request

import app


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_start_server_honours_a_custom_port():
    port = _free_port()
    assert port != app.DEFAULT_PORT

    url = app.start_server("127.0.0.1", lan=False, port=port)

    assert url == f"http://127.0.0.1:{port}"
    with urllib.request.urlopen(f"{url}/api/system-status", timeout=5) as r:
        assert r.status == 200
