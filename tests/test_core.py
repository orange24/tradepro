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
