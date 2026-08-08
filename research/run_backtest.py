"""Run the official simulation without needing write access to trader_interface/.

simulation.py hardcodes its chart output to './simulation_results', relative to
the current working directory. If trader_interface/ isn't writable the run
completes but crashes at the very last step, throwing away the plot.

This runner leaves simulation.py and algorithm.py untouched. It points the
engine at the data by absolute path, then chdir's into a writable output folder
so './simulation_results' lands somewhere it's allowed to.

It also prints the summary the harness doesn't: Sharpe, max drawdown, win rate,
budget utilisation, and per-instrument risk-adjusted return — and writes the
daily P&L to CSV so you can diff two strategies instead of eyeballing charts.

    python run_backtest.py                  # default output: research/backtest_out
    python run_backtest.py --out /tmp/bt    # anywhere writable
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TRADER = os.path.abspath(os.path.join(HERE, "..", "trader_interface"))
DATA = os.path.join(TRADER, "data")

parser = argparse.ArgumentParser()
parser.add_argument("--out", default=os.path.join(HERE, "backtest_out"),
                    help="writable directory for charts and CSVs")
parser.add_argument("--quiet", action="store_true",
                    help="suppress the per-day P&L spam")
args = parser.parse_args()

os.makedirs(args.out, exist_ok=True)

# Import the competition harness in place.
sys.path.insert(0, TRADER)
import simulation as sim          # noqa: E402
from algorithm import Algorithm   # noqa: E402


def main():
    engine = sim.TradingEngine(dataFolder=DATA + os.sep)
    algo = Algorithm(engine.positions)

    if args.quiet:
        devnull = open(os.devnull, "w")
        real_stdout = sys.stdout
        sys.stdout = devnull
        try:
            engine.run_algorithms(algo)
        finally:
            sys.stdout = real_stdout
            devnull.close()
    else:
        engine.run_algorithms(algo)

    # plot_returns() writes to './simulation_results', so give it a cwd it can
    # actually write to.
    cwd = os.getcwd()
    os.chdir(args.out)
    try:
        engine.plot_returns()
    finally:
        os.chdir(cwd)

    report(engine)


def report(engine):
    daily = pd.Series([float(v) for v in engine.totalReturnHistory])
    cum = daily.cumsum()
    budget = pd.Series(engine.pcTotalBudget)

    trading = daily[daily != 0]
    sharpe = (daily.mean() / daily.std() * np.sqrt(252)) if daily.std() else np.nan
    peak = cum.cummax()
    dd = cum - peak

    print("\n" + "=" * 64)
    print("PORTFOLIO SUMMARY")
    print("=" * 64)
    rows = [
        ("Total P&L", f"${float(engine.totalPNL):,.2f}"),
        ("Trading days", f"{len(daily)}"),
        ("Mean daily P&L", f"${daily.mean():,.2f}"),
        ("Daily P&L std dev", f"${daily.std():,.2f}"),
        ("Annualised Sharpe", f"{sharpe:.2f}"),
        ("Win rate", f"{(trading > 0).mean():.1%}"),
        ("Best day", f"${daily.max():,.2f}"),
        ("Worst day", f"${daily.min():,.2f}"),
        ("Max drawdown", f"${dd.min():,.2f}"),
        ("Max drawdown (% of peak)",
         f"{(dd.min() / peak[dd.idxmin()] * 100):.1f}%" if peak[dd.idxmin()] else "n/a"),
        ("Longest losing streak", f"{losing_streak(daily)} days"),
        ("Mean budget used", f"{budget.mean():.1f}%"),
        ("Max budget used", f"{budget.max():.1f}%"),
        ("Days over budget (zeroed)", f"{int((budget == 0).sum())}"),
    ]
    for k, v in rows:
        print(f"  {k:<28} {v:>18}")

    print("\n" + "=" * 64)
    print("PER-INSTRUMENT")
    print("=" * 64)
    print(f"  {'Instrument':<20}{'P&L':>14}{'Sharpe':>9}{'Win rate':>10}"
          f"{'Max DD':>13}")
    per = []
    for ins, hist in engine.returnsHistory.items():
        s = pd.Series([float(v) for v in hist])
        c = s.cumsum()
        sh = (s.mean() / s.std() * np.sqrt(252)) if s.std() else 0.0
        active = s[s != 0]
        wr = (active > 0).mean() if len(active) else np.nan
        mdd = (c - c.cummax()).min()
        per.append((ins, c.iloc[-1], sh, wr, mdd))
    for ins, pnl, sh, wr, mdd in sorted(per, key=lambda x: -x[1]):
        wrs = f"{wr:.1%}" if wr == wr else "n/a"
        print(f"  {ins:<20}{pnl:>14,.2f}{sh:>9.2f}{wrs:>10}{mdd:>13,.0f}")

    note = [p for p in per if p[0] in sim.NO_LOCAL_PNL_INSTRUMENTS]
    if note:
        names = ", ".join(n for n, *_ in note)
        print(f"\n  Note: {names} is forced to $0 locally by the harness — its real")
        print("  payoff is decided live from every team's positions. It still")
        print("  consumes budget, so don't judge it by this table.")

    # Machine-readable output for comparing strategy variants.
    out = pd.DataFrame({"day": range(len(daily)), "daily_pnl": daily.values,
                        "cum_pnl": cum.values, "pc_budget": budget.values})
    for ins, hist in engine.returnsHistory.items():
        out[f"pnl_{ins}"] = [float(v) for v in hist]
    for ins, hist in engine.pcPositionHistorys.items():
        out[f"pos_{ins}"] = hist
    path = os.path.join(args.out, "daily_pnl.csv")
    out.to_csv(path, index=False)
    print(f"\n  chart -> {os.path.join(args.out, 'simulation_results', 'returns_plot.png')}")
    print(f"  data  -> {path}")


def losing_streak(daily):
    best = run = 0
    for v in daily:
        run = run + 1 if v < 0 else 0
        best = max(best, run)
    return best


if __name__ == "__main__":
    main()
