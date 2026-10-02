"""Command line: python -m tradepro {scan,backtest,download} ..."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

from . import backtest
from .config import DEFAULT
from .data import make_source
from .markets import markets_for
from .scanner import scan
from .watchlists import WATCHLISTS


def _warn(t, e):
    print(f"  ! {t}: {e}", file=sys.stderr)


def _load(source, tickers, start):
    data = {}
    for t in tickers:
        try:
            df = source.get(t, start=start)
            if len(df) >= 60:
                data[t] = df
            else:
                _warn(t, ValueError(f"only {len(df)} bars"))
        except Exception as e:
            _warn(t, e)
    return data


def main(argv=None):
    p = argparse.ArgumentParser(prog="tradepro", description="ChalokeDotCom Wave 3 + CDC Action Zone scanner")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "backtest", "download"):
        sp = sub.add_parser(name)
        sp.add_argument("tickers", nargs="*", help="e.g. PTT KBANK or AAPL MSFT (default: the market's watchlist)")
        sp.add_argument("--market", default="set", choices=["set", "us", "all"])
        sp.add_argument("--watchlist", default=None, choices=sorted(WATCHLISTS),
                        help="default: set100 for SET, us50 for US")
        sp.add_argument("--source", default="yahoo", help="yahoo | csv | synthetic")
        sp.add_argument("--csv-dir", default="data/cache", help="per-market subfolders set/ and us/")
        sp.add_argument("--start", default=None, help="first date, e.g. 2015-01-01")
        if name == "scan":
            sp.add_argument("--recent", type=int, default=1, help="look at signals from the last N bars")
        if name == "backtest":
            sp.add_argument("--hold", type=int, default=DEFAULT.w3_max_hold_bars, help="max bars to hold a trade (0 = no limit)")
            sp.add_argument("--out", default="trades.csv")
    args = p.parse_args(argv)
    if args.tickers and args.market == "all":
        p.error("give tickers with --market set or --market us, not all")
    pd.set_option("display.width", 200, "display.max_columns", 20, "display.max_rows", 200)

    scans, trades = [], []
    for m in markets_for(args.market):
        source = make_source(args.source, str(Path(args.csv_dir) / m.name), yahoo_suffix=m.yahoo_suffix)
        tickers = [t.upper() for t in args.tickers] or WATCHLISTS[args.watchlist or m.watchlist]

        if args.cmd == "download":
            for t, df in _load(source, tickers, args.start or "2010-01-01").items():
                print(f"[{m.name}] {t}: {len(df)} bars")
            continue

        cfg = replace(DEFAULT, market=m.name, cost_pct=m.cost_pct)
        if args.cmd == "scan":
            res = scan(source, tickers, recent_bars=args.recent, start=args.start or "2023-01-01",
                       cfg=cfg, on_error=_warn)
            scans.append(res.assign(market=m.name))
        else:
            cfg = replace(cfg, max_hold_bars=args.hold, w3_max_hold_bars=args.hold)
            t = backtest.run(_load(source, tickers, args.start or "2015-01-01"), cfg)
            if not t.empty:
                trades.append(t.assign(market=m.name))

    if args.cmd == "scan":
        res = pd.concat(scans, ignore_index=True)
        if res.empty:
            print("No setups on the latest bar(s).")
        else:
            cols = ["market"] + [c for c in res.columns if c != "market"]
            print(res[cols].sort_values(["market", "date", "setup", "ticker"]).to_string(index=False))
    elif args.cmd == "backtest":
        if not trades:
            print("No trades.")
            return
        all_trades = pd.concat(trades, ignore_index=True)
        all_trades.to_csv(args.out, index=False)
        for market, t in all_trades.groupby("market"):
            print(f"\n=== {market.upper()} ===")
            print(backtest.summarize(t).to_string())
        print(f"\n{len(all_trades)} trades saved to {args.out}")


if __name__ == "__main__":
    main()
