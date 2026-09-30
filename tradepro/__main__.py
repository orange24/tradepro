"""Command line: python -m tradepro {scan,backtest,download} ..."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

import pandas as pd

from . import backtest
from .config import DEFAULT
from .data import make_source
from .scanner import scan
from .watchlists import WATCHLISTS


def _tickers(args) -> list[str]:
    if args.tickers:
        return [t.upper() for t in args.tickers]
    return WATCHLISTS[args.watchlist]


def _warn(t, e):
    print(f"  ! {t}: {e}", file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(prog="tradepro", description="Brooks price action scanner")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "backtest", "download"):
        sp = sub.add_parser(name)
        sp.add_argument("tickers", nargs="*", help="e.g. PTT KBANK (default: the watchlist)")
        sp.add_argument("--watchlist", default="set50", choices=sorted(WATCHLISTS))
        sp.add_argument("--source", default="yahoo", help="yahoo | csv | synthetic")
        sp.add_argument("--csv-dir", default="data/cache")
        sp.add_argument("--start", default=None, help="first date, e.g. 2015-01-01")
        if name in ("scan", "backtest"):
            sp.add_argument("--reward", type=float, default=DEFAULT.reward_r, help="target in R for pullbacks")
            sp.add_argument("--long-only", action="store_true", help="skip short setups")
        if name == "scan":
            sp.add_argument("--recent", type=int, default=1, help="look at signals from the last N bars")
        if name == "backtest":
            sp.add_argument("--hold", type=int, default=DEFAULT.max_hold_bars)
            sp.add_argument("--out", default="trades.csv")
    args = p.parse_args(argv)

    source = make_source(args.source, args.csv_dir)
    tickers = _tickers(args)
    pd.set_option("display.width", 200, "display.max_columns", 20, "display.max_rows", 200)

    if args.cmd == "download":
        for t in tickers:
            try:
                df = source.get(t, start=args.start or "2010-01-01")
                print(f"{t}: {len(df)} bars")
            except Exception as e:
                _warn(t, e)
        return

    cfg = replace(DEFAULT, reward_r=args.reward, long_only=args.long_only)
    if args.cmd == "scan":
        res = scan(source, tickers, recent_bars=args.recent, start=args.start or "2023-01-01",
                   cfg=cfg, on_error=_warn)
        if res.empty:
            print("No setups on the latest bar(s).")
        else:
            print(res.sort_values(["date", "setup", "ticker"]).to_string(index=False))
        return

    cfg = replace(cfg, max_hold_bars=args.hold)
    data = {}
    for t in tickers:
        try:
            df = source.get(t, start=args.start or "2015-01-01")
            if len(df) >= 60:
                data[t] = df
        except Exception as e:
            _warn(t, e)
    trades = backtest.run(data, cfg)
    if trades.empty:
        print("No trades.")
        return
    trades.to_csv(args.out, index=False)
    print(backtest.summarize(trades).to_string())
    print(f"\n{len(trades)} trades on {len(data)} tickers, saved to {args.out}")


if __name__ == "__main__":
    main()
