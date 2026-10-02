import numpy as np
import pandas as pd
import pytest

from tradepro import backtest
from tradepro.config import Config
from tradepro.data import CSVSource, SyntheticSource
from tradepro.setups import Signal, count_highs, detect
from tradepro.ticks import round_to_tick, set_tick


def test_set_ticks():
    assert set_tick(1.5) == 0.01
    assert set_tick(24.9) == 0.10
    assert set_tick(25) == 0.25
    assert set_tick(450) == 2.0
    assert round_to_tick(33.37, up=True) == 33.5
    assert round_to_tick(33.37, up=False) == 33.25


def test_count_highs_two_legged_pullback():
    #        leg high, down, H1, down, H2, new high
    high = np.array([10, 12, 11.5, 11.8, 11.0, 11.6, 12.5])
    count, armed, in_pb = count_highs(high)
    assert list(count) == [0, 0, 0, 1, 1, 2, 0]
    assert armed[4] and not armed[5]
    assert not in_pb[6]


def test_count_highs_resets_on_strong_breakout():
    high = np.array([10, 12, 11.5, 11.8, 11.0, 11.6, 11.2, 11.4])
    reset = np.zeros(len(high), bool)
    reset[5] = True                      # bar 5 would be H2, but it is a strong breakout: new leg
    count, _, _ = count_highs(high, reset)
    assert list(count) == [0, 0, 0, 1, 1, 0, 0, 1]


def _bars(closes, spread=0.4):
    closes = np.asarray(closes, float)
    opens = np.r_[closes[0], closes[:-1]]
    idx = pd.bdate_range("2024-01-01", periods=len(closes))
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, closes) + spread,
                         "low": np.minimum(opens, closes) - spread, "close": closes,
                         "volume": 1000}, index=idx)


def test_h2_in_bull_trend():
    up = list(np.linspace(20, 40, 60))
    # two-legged pullback: down, up (H1), down, then a bull signal bar
    pb = [39.2, 38.4, 39.8, 38.6, 37.6]
    df = _bars(up + pb)
    df.iloc[-1, df.columns.get_loc("open")] = 37.0   # bull close near its high
    df.iloc[-1, df.columns.get_loc("high")] = 37.7
    df.iloc[-1, df.columns.get_loc("low")] = 36.8
    sigs = [s for s in detect(df, "X") if s.date == df.index[-1]]
    assert [s.setup for s in sigs] == ["H2"]
    s = sigs[0]
    assert s.entry > df["high"].iloc[-1] and s.stop < df["low"].iloc[-1]
    assert s.reward_r == pytest.approx(2.0, abs=0.05)


def test_backtest_target_and_stop():
    idx = pd.bdate_range("2024-01-01", periods=4)
    df = pd.DataFrame({"open": [10, 10.2, 10.6, 11], "high": [10.3, 10.7, 11.2, 11.1],
                       "low": [9.9, 10.1, 10.5, 10.9], "close": [10.2, 10.6, 11, 11]}, index=idx)
    cfg = Config(cost_pct=0)
    win = Signal("X", idx[0], "H2", "long", entry=10.35, stop=9.85, target=11.1, context="bull")
    t = backtest.simulate(df, [win], cfg)[0]
    assert t.exit_reason == "target" and t.r == pytest.approx(1.5)
    lose = Signal("X", idx[0], "L2", "short", entry=10.15, stop=10.65, target=9.0, context="bear")
    t = backtest.simulate(df, [lose], cfg)[0]
    assert t.exit_reason == "stop" and t.r == pytest.approx(-1.0)
    untriggered = Signal("X", idx[1], "H2", "long", entry=12, stop=10, target=15, context="bull")
    assert backtest.simulate(df, [untriggered], cfg) == []


def test_synthetic_end_to_end(tmp_path):
    df = SyntheticSource().get("PTT")
    df.to_csv(tmp_path / "PTT.csv")
    again = CSVSource(tmp_path).get("PTT")
    assert len(again) == len(df)
    trades = backtest.run({"PTT": again})
    assert not trades.empty
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


def test_signal_bar_rejects_doji_and_bear_bars():
    from tradepro.indicators import is_good_bull_signal
    from types import SimpleNamespace as R

    cfg = Config()
    good = R(open=10.0, close=10.8, high=10.9, low=9.9, range=1.0, body_ratio=0.8, close_pos=0.9, atr=1.0)
    doji = R(open=10.4, close=10.5, high=10.9, low=9.9, range=1.0, body_ratio=0.1, close_pos=0.6, atr=1.0)
    bear = R(open=10.8, close=10.0, high=10.9, low=9.9, range=1.0, body_ratio=0.8, close_pos=0.1, atr=1.0)
    assert is_good_bull_signal(good, cfg)
    assert not is_good_bull_signal(doji, cfg) and not is_good_bull_signal(bear, cfg)


def test_breakout_waits_for_follow_through():
    flat = [20 + 0.3 * np.sin(k) for k in range(40)]
    df = _bars(flat + [22.5, 23.4], spread=0.05)      # breakout bar, then a follow-through bar
    df.iloc[-1, df.columns.get_loc("low")] = 22.45     # gap above the breakout point
    bo = lambda cfg: [s.date for s in detect(df, "X", cfg) if s.setup == "BO_BULL"]
    assert df.index[-2] in bo(Config(bo_follow_through=False))
    assert bo(Config(bo_follow_through=True)) == [df.index[-1]]


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
