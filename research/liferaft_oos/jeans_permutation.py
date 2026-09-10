"""
Permutation test on Thrifted Jeans at its post-Liferaft allocation.

Context. Freeing the Liferaft budget did not leave the rest of the book
unchanged. Thrifted Jeans went from $3,842 of mean notional held on 66 days to
$42,300 held on 351 days, an 11x increase, because it is the residual claimant
in BUDGET_PRIORITY. Of the $110,397 the local backtest gained, $88,148 is Jeans.

The existing note in algorithm.py already argues Jeans is a random walk with
drift: ADF cannot reject a unit root, Hurst is indistinguishable from 0.5, every
variance ratio has |z| < 0.1. A prior permutation test at the small allocation
put its P&L at the 96th percentile of a shuffled-returns null.

That test needs redoing, because the allocation it was run at no longer exists.
Method: shuffle the Jeans daily returns (preserving their distribution and total
drift, destroying only the ordering), rebuild the price path, rerun the entire
backtest so budget interactions are captured, and record total P&L. If momentum
is capturing genuine serial structure, shuffling should destroy it. If it is
just harvesting drift, the shuffled runs will look the same as the real one.
"""

import csv
import os
import shutil
import sys
import tempfile

import numpy as np

N_PERM = 200
HERE = os.path.dirname(os.path.abspath(__file__))
TI = os.path.abspath(os.path.join(HERE, "..", "..", "trader_interface"))
CSV = os.path.join(TI, "data", "Thrifted Jeans_price_history.csv")


def load():
    rows = list(csv.reader(open(CSV)))
    return rows[0], [(r[0], float(r[1])) for r in rows[1:]]


def write(path, header, days, prices):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for d, p in zip(days, prices):
            w.writerow([d, f"{p:.2f}"])


def run_backtest(workdir):
    """Run the full engine inside workdir and return total P&L."""
    cwd = os.getcwd()
    os.chdir(workdir)
    for m in ("simulation", "algorithm"):
        sys.modules.pop(m, None)
    sys.path.insert(0, workdir)
    try:
        import simulation as sim
        from algorithm import Algorithm
        e = sim.TradingEngine()
        a = Algorithm(e.positions)
        e.run_algorithms(a)
        return float(e.totalPNL)  # engine uses Decimal internally
    finally:
        sys.path.remove(workdir)
        os.chdir(cwd)


def main():
    header, rows = load()
    days = [d for d, _ in rows]
    prices = np.array([p for _, p in rows])
    rets = np.diff(np.log(prices))

    work = tempfile.mkdtemp(prefix="jeansperm_")
    shutil.copytree(TI, os.path.join(work, "ti"))
    wd = os.path.join(work, "ti")
    csv_path = os.path.join(wd, "data", "Thrifted Jeans_price_history.csv")

    # silence the engine's per-day printing
    devnull = open(os.devnull, "w")
    real_stdout = sys.stdout

    sys.stdout = devnull
    actual = run_backtest(wd)
    sys.stdout = real_stdout
    print(f"actual total P&L                 ${actual:>12,.0f}")

    rng = np.random.default_rng(4242)
    null = []
    for i in range(N_PERM):
        shuf = rng.permutation(rets)
        path = prices[0] * np.exp(np.concatenate([[0.0], np.cumsum(shuf)]))
        write(csv_path, header, days, path)
        sys.stdout = devnull
        try:
            null.append(run_backtest(wd))
        finally:
            sys.stdout = real_stdout
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{N_PERM} permutations")

    null = np.array(null)
    pct = (null < actual).mean() * 100
    p_val = (1 + (null >= actual).sum()) / (1 + len(null))

    print()
    print(f"shuffled-null mean               ${null.mean():>12,.0f}")
    print(f"shuffled-null median             ${np.median(null):>12,.0f}")
    print(f"shuffled-null 5th / 95th pct     ${np.percentile(null, 5):>12,.0f} / "
          f"${np.percentile(null, 95):>12,.0f}")
    print(f"actual sits at percentile        {pct:>12.1f}")
    print(f"one-sided p-value                {p_val:>12.3f}")
    print()
    if p_val > 0.05:
        print("The real ordering is not distinguishable from a shuffled one.")
        print("Jeans momentum is harvesting drift, not serial structure.")
    else:
        print("The real ordering beats the shuffled null at the 5% level.")

    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
