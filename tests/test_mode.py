import importlib

import pytest
from fastapi.testclient import TestClient


def make_client(monkeypatch, tmp_path, mode):
    monkeypatch.setenv("TRADE_MODE", mode)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    import app.mode, app.main
    importlib.reload(app.mode); importlib.reload(app.main)
    return TestClient(app.main.app)


@pytest.mark.parametrize("path", ["/history", "/commissions", "/gaps", "/inventory", "/api/inventory/items", "/photos/x.jpg"])
def test_public_hides_private_routes(monkeypatch, tmp_path, path):
    with make_client(monkeypatch, tmp_path, "public") as c:
        assert c.get(path).status_code == 404


def test_public_blocks_mutations(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path, "public") as c:
        assert c.post("/rooms/ABCDE/delete").status_code == 404
        assert c.post("/commissions/ABCDE/delete").status_code == 404
        assert c.post("/commissions", data={"painter_name": "x"}).status_code == 404
        assert c.patch("/catalog/units/1/models-per-box", json={"models_per_box": 5}).status_code == 404


def test_public_trade_flow_and_pwa(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path, "public") as c:
        assert c.get("/").status_code == 200 and "past trades" not in c.get("/").text
        r = c.post("/rooms", follow_redirects=False)
        assert r.status_code == 303 and c.get(r.headers["location"]).status_code == 200
        assert c.get("/healthz").json()["mode"] == "public"
        assert c.get("/manifest.webmanifest").json()["display"] == "standalone"
        assert c.get("/sw.js").status_code == 200
        assert c.get("/static/branding/icon-192.png").status_code == 200


def test_public_room_rate_limit(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path, "public") as c:
        codes = [c.post("/rooms", follow_redirects=False).status_code for _ in range(22)]
        assert codes[:20] == [303] * 20 and codes[20:] == [429, 429]


def test_default_mode_is_public(monkeypatch):
    monkeypatch.delenv("TRADE_MODE", raising=False)
    import app.mode
    importlib.reload(app.mode)
    assert app.mode.MODE == "public"


def test_private_has_admin_pages(monkeypatch, tmp_path):
    with make_client(monkeypatch, tmp_path, "private") as c:
        assert c.get("/history").status_code == 200 and c.get("/commissions").status_code == 200
        assert "past trades" in c.get("/").text
