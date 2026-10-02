import pytest

from tradepro.web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("TRADEPRO_PASSWORD", raising=False)
    app = create_app(db_path=str(tmp_path / "t.db"), source="synthetic", autoscan=False)
    return app.test_client()


def test_portfolio_flow(client):
    assert "ยังไม่มีหุ้นในพอร์ต" in client.get("/").get_data(as_text=True)
    r = client.post("/holdings", data={"market": "set", "ticker": "ptt", "shares": "1000", "cost": "35"})
    assert r.status_code == 302
    client.post("/holdings", data={"market": "us", "ticker": "AAPL", "shares": "10", "cost": "180"})
    html = client.get("/").get_data(as_text=True)
    assert "PTT" in html and "AAPL" in html and "จุดขาย" in html
    assert client.post("/holdings", data={"market": "set", "ticker": "X", "shares": "-1", "cost": "1"}).status_code == 400
    client.post("/holdings/1/delete")
    assert "/chart/set/PTT" not in client.get("/").get_data(as_text=True)


def test_scan_and_chart(client):
    client.application.config["scanner"]._run("set")
    html = client.get("/scan?market=set").get_data(as_text=True)
    assert "สแกนล่าสุด" in html
    d = client.get("/api/chart/us/NVDA").get_json()
    assert len(d["candles"]) == 250 and d["advice"]["status"] in ("hold", "watch", "sell")
    assert len(d["bars"]) == 250 and d["swings"]
    lv = d["levels"]
    assert lv["cdc_zone"] in ("green", "yellow", "orange", "red", "lblue", "blue")
    assert len(d["cdc_fast"]) == len(d["cdc_slow"]) == 250
    k = client.get("/api/chaloke/set/PTT").get_json()
    assert k["status"] and k["cdc"]["zone"] and isinstance(k["checks"], list)


def test_password(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADEPRO_PASSWORD", "secret")
    c = create_app(db_path=str(tmp_path / "t.db"), source="synthetic", autoscan=False).test_client()
    assert c.get("/").status_code == 401
    assert c.get("/", auth=("boy", "secret")).status_code == 200
