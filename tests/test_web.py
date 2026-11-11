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
    live = client.get("/?fresh=1").get_data(as_text=True)
    assert 'id="holdings"' in live and "PTT" in live and 'id="live-status"' in live
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


def test_thai_password(tmp_path, monkeypatch):
    import base64
    monkeypatch.setenv("TRADEPRO_PASSWORD", "รหัสของคุณ")
    c = create_app(db_path=str(tmp_path / "t.db"), source="synthetic", autoscan=False).test_client()
    basic = lambda pw: {"Authorization": "Basic " + base64.b64encode(f"boy:{pw}".encode()).decode()}
    assert c.get("/", headers=basic("รหัสของคุณ")).status_code == 200
    assert c.get("/", headers=basic("wrong")).status_code == 401


def test_bitcoin_and_gold(client):
    r = client.get("/chart?market=set&ticker=btc")
    assert r.status_code == 302 and r.headers["Location"].endswith("/chart/asset/BTC-USD")
    assert client.get("/chart?market=us&ticker=ทองคำ").headers["Location"].endswith("/chart/asset/GC=F")
    d = client.get("/api/chart/asset/BTC-USD").get_json()
    assert len(d["candles"]) == 250
    client.post("/holdings", data={"market": "set", "ticker": "gold", "shares": "0.5", "cost": "2000"})
    assert "/chart/asset/GC=F" in client.get("/").get_data(as_text=True)


def test_set_index_alias_and_overview(client):
    assert client.get("/chart?market=us&ticker=set").headers["Location"].endswith("/chart/set/TDEX")
    client.application.config["scanner"]._run("set")
    ov = client.application.config["store"].latest_scan("set")["summary"]
    assert ov["n"] > 0 and sum(ov["counts"].values()) == ov["n"] and ov["verdict"][1]
    html = client.get("/scan?market=set").get_data(as_text=True)
    assert "ภาพรวมตลาด" in html
    # Chaloke's way: the funnel starts at the weekly wave structure, no monthly step
    fn = ov["funnel"]
    assert {t for t, _ in fn["wd"]} <= {t for t, _ in fn["w"]}
    assert "Weekly → Daily" in html and "Monthly" not in html


def test_company_info(client):
    i = client.get("/api/info/set/WHA").get_json()
    assert i["name"].startswith("WHA") and i["industry_th"] == "อสังหาริมทรัพย์และก่อสร้าง"
    b = client.get("/api/info/asset/BTC-USD").get_json()
    assert b["name"] == "Bitcoin" and "ดิจิทัล" in b["about_th"]


def test_weekly_w3_scan(client):
    client.application.config["scanner"]._run("set_w")
    scan = client.application.config["store"].latest_scan("set_w")
    assert scan["summary"]["tf"] == "W"
    html = client.get("/scan?market=set_w").get_data(as_text=True)
    assert "โหมดรายสัปดาห์" in html and "ราคาเปิดสัปดาห์ถัดไป" in html
