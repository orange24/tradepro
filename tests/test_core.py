import numpy as np
import pandas as pd
import pytest

from tradepro import backtest
from tradepro.config import Config
from tradepro.data import CSVSource, SyntheticSource
from tradepro.setups import Signal, detect
from tradepro.ticks import round_to_tick, set_tick


def test_set_ticks():
    assert set_tick(1.5) == 0.01
    assert set_tick(24.9) == 0.10
    assert set_tick(25) == 0.25
    assert set_tick(450) == 2.0
    assert round_to_tick(33.37, up=True) == 33.5
    assert round_to_tick(33.37, up=False) == 33.25


def _bars(closes, spread=0.4):
    closes = np.asarray(closes, float)
    opens = np.r_[closes[0], closes[:-1]]
    idx = pd.bdate_range("2024-01-01", periods=len(closes))
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, closes) + spread,
                         "low": np.minimum(opens, closes) - spread, "close": closes,
                         "volume": 1000}, index=idx)


def test_backtest_target_and_stop():
    idx = pd.bdate_range("2024-01-01", periods=4)
    df = pd.DataFrame({"open": [10, 10.2, 10.6, 11], "high": [10.3, 10.7, 11.2, 11.1],
                       "low": [9.9, 10.1, 10.5, 10.9], "close": [10.2, 10.6, 11, 11]}, index=idx)
    cfg = Config(cost_pct=0)
    win = Signal("X", idx[0], "W3", "long", entry=10.35, stop=9.85, target=11.1, context="green", order="stop")
    t = backtest.simulate(df, [win], cfg)[0]
    assert t.exit_reason == "target" and t.r == pytest.approx(1.5)
    lose = Signal("X", idx[0], "W3", "short", entry=10.15, stop=10.65, target=9.0, context="red", order="stop")
    t = backtest.simulate(df, [lose], cfg)[0]
    assert t.exit_reason == "stop" and t.r == pytest.approx(-1.0)
    untriggered = Signal("X", idx[1], "W3", "long", entry=12, stop=10, target=15, context="green", order="stop")
    assert backtest.simulate(df, [untriggered], cfg) == []


def test_synthetic_end_to_end(tmp_path):
    df = SyntheticSource().get("PTT")
    df.to_csv(tmp_path / "PTT.csv")
    again = CSVSource(tmp_path).get("PTT")
    assert len(again) == len(df)
    from tradepro.watchlists import SET50

    data = {t: SyntheticSource().get(t) for t in SET50[:20]} | {"PTT": again}
    trades = backtest.run(data)
    assert not trades.empty and set(trades["setup"]) == {"W3"}
    assert "ALL" in backtest.summarize(trades).index


def test_us_ticks_and_market_aware_signals():
    from tradepro.ticks import tick_size

    assert tick_size(150.0, "us") == 0.01
    assert tick_size(0.5, "us") == 0.0001
    assert round_to_tick(150.004, up=True, market="us") == 150.01
    df = SyntheticSource().get("AAPL")
    for s in detect(df, "AAPL", Config(market="us"))[:50]:
        assert round(s.entry * 100) == pytest.approx(s.entry * 100, abs=1e-6)


def test_cli_both_markets(tmp_path, capsys):
    from tradepro.__main__ import main

    out = tmp_path / "t.csv"
    main(["backtest", "--market", "all", "--source", "synthetic", "--out", str(out)])
    text = capsys.readouterr().out
    assert "=== SET ===" in text and "=== US ===" in text
    assert set(pd.read_csv(out)["market"]) == {"set", "us"}
    main(["scan", "--market", "all", "--source", "synthetic", "--recent", "3"])
    assert "No setups" not in capsys.readouterr().out


def test_wave3_after_deep_wave2_and_first_cdc_green():
    from tradepro.wave import cdc_action_zone

    closes = (list(np.linspace(100, 101, 30)) + list(np.linspace(101, 130, 20))      # base, wave 1
              + list(np.linspace(130, 107, 18)) + list(np.linspace(107.5, 124, 22)))   # wave 2 (~80%), turn up
    df = _bars(closes, spread=0.3)
    w3 = [s for s in detect(df, "X") if s.setup == "W3"]
    assert len(w3) == 1
    s = w3[0]
    green = cdc_action_zone(df)["cdc_green"]
    assert green[s.date] and not green.shift(1)[s.date]          # first green bar
    assert 0.618 <= s.levels["retrace"] <= 0.942 and s.order == "open"
    assert s.stop < s.levels["w2_low"] and s.target == pytest.approx(s.levels["w2_low"] + 1.618 * (
        s.levels["w1_top"] - s.levels["w1_base"]), abs=0.01)


def test_chaloke_live_checklist():
    from tradepro.chaloke import analyze

    base_w1 = list(np.linspace(100, 101, 30)) + list(np.linspace(101, 130, 20))
    wave2 = list(np.linspace(130, 107, 18))
    a = analyze(_bars(base_w1 + wave2, spread=0.3), Config())          # still falling into the zone
    assert a["status"] == "wait_green" and a["wave"]["top"] > a["wave"]["w2"] > a["wave"]["base"]
    assert not a["checks"][3][0]                                        # CDC not green yet
    b = analyze(_bars(base_w1 + wave2 + list(np.linspace(107.5, 118, 16)), spread=0.3), Config())
    assert b["status"] == "buy" and b["cdc"]["zone"] == "green" and b["wave"]["rr"] >= 2
    late = analyze(_bars(base_w1 + wave2 + list(np.linspace(107.5, 124, 16)), spread=0.3), Config())
    assert late["status"] == "missed"                                   # ran away: reward/risk below 1:2
    c = analyze(_bars(list(np.linspace(130, 80, 80)), spread=0.3), Config())   # endless new lows
    assert c["status"] == "no_wave" and c["wave"] is None


def test_w3_three_lots_and_stop_on_close():
    idx = pd.bdate_range("2024-01-01", periods=5)
    df = pd.DataFrame({"open": [10, 10, 10.5, 11, 11], "high": [10.2, 11.2, 12.1, 11.2, 13.5],
                       "low": [9.8, 9.5, 10.4, 8.8, 10.9], "close": [10, 10.5, 11.5, 9.5, 13]}, index=idx)
    sig = Signal("X", idx[0], "W3", "long", entry=10, stop=9, target=11, context="green",
                 levels={"t2": 12, "t3": 13})
    cfg = Config(cost_pct=0, w3_trail="none")
    t = backtest.simulate_w3(df, [sig], cfg)[0]
    assert t.exit_reason == "target" and t.r == pytest.approx(2.0)     # 1/3 each at +1R, +2R, +3R
    t = backtest.simulate_w3(df, [sig], Config(cost_pct=0, w3_trail="breakeven"))[0]
    assert t.exit_reason == "trail"                                    # closed at 9.5, under the moved-up stop (10)
    assert t.r == pytest.approx((1 + 2 - 0.5) / 3, abs=1e-3)
    t = backtest.simulate_w3(df, [sig], Config(cost_pct=0, w3_stop_on_close=False, w3_trail="none"))[0]
    assert t.exit_reason == "stop"                                     # the wick to 8.8 stops a touch stop


def test_portfolio_action_trim_at_fib_targets():
    from tradepro.advisor import _action
    from tradepro.indicators import add_features

    df = _bars(list(np.linspace(10, 16, 40)), spread=0.1)
    f = add_features(df, Config())
    s = Signal("X", df.index[5], "W3", "long", entry=10.8, stop=10, target=12, context="green",
               levels={"t2": 14, "t3": 20})
    action, text = _action(f, s, "hold", "green", False, Config())
    assert action == "trim" and "261.8" in text and "2 ใน 3" in text
    action, _ = _action(f, s, "sell", "red", False, Config())
    assert action == "sell"
    fresh = Signal("X", df.index[-2], "W3", "long", entry=15.8, stop=15, target=19, context="green")
    assert _action(f, fresh, "hold", "green", False, Config())[0] == "add"
    action, text = _action(f, fresh, "hold", "green", False, Config(), cost=17)     # holding is at a loss
    assert action == "hold" and "ถัวเฉลี่ย" in text
