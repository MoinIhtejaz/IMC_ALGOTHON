"""
Equivalence test: does the code actually shipped in trader_interface/algorithm.py
behave identically to the strategy that was tested?

A report is worthless if the deployed function is a paraphrase of the tested one.
This imports the real Algorithm class, drives its _sig_liferaft through the
simulator, and checks it matches RegimeContrarian(k=2, warmup=0, probe=0) run
for run, not just on average.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "trader_interface"))

from algorithm import Algorithm, LIFERAFT_FLOOR, LIFERAFT_K, LIFERAFT_MIN_N  # noqa: E402

from engine import Agent, run  # noqa: E402
from harness import rngf  # noqa: E402
from opponents import random_room  # noqa: E402
from strategies import RegimeContrarian  # noqa: E402


class ShippedAgent(Agent):
    """Wraps the real Algorithm object so the shipped code path is what runs."""
    name = "shipped"

    def reset(self, rng):
        self.rng = rng
        self.algo = Algorithm({})
        self.algo.data = {"Liferaft Ticket": []}

    def act(self, prices, moves, day):
        self.algo.day = day
        self.algo.data["Liferaft Ticket"] = list(prices)
        frac = self.algo._sig_liferaft()
        # reproduce the integer packing _allocate would apply at limit 1
        return int(round(max(-1.0, min(1.0, frac)) * 1))


def reference():
    return RegimeContrarian(k=LIFERAFT_K, warmup=0, probe=0, min_n=LIFERAFT_MIN_N,
                            pooled=False, use_floor=True)


print("Constants shipped in algorithm.py")
print(f"  LIFERAFT_K      = {LIFERAFT_K}   (tested value: 2.0)")
print(f"  LIFERAFT_MIN_N  = {LIFERAFT_MIN_N}   (tested value: 5)")
print(f"  LIFERAFT_FLOOR  = {LIFERAFT_FLOOR}  (spec value: 20000)")
assert LIFERAFT_K == 2.0 and LIFERAFT_MIN_N == 5 and LIFERAFT_FLOOR == 20000

print("\nRun-for-run equivalence against the tested strategy")
mismatch = 0
ship_pnls, ref_pnls = [], []
for i in range(200):
    opps_a = random_room(np.random.default_rng(300_000 + i))
    opps_b = random_room(np.random.default_rng(300_000 + i))
    a = run(ShippedAgent(), opps_a, 365, rngf(300_000 + i))
    b = run(reference(), opps_b, 365, rngf(300_000 + i))
    ship_pnls.append(a.pnl)
    ref_pnls.append(b.pnl)
    if a.pnl != b.pnl or a.actions != b.actions:
        mismatch += 1
        if mismatch <= 3:
            diff = [d for d, (x, y) in enumerate(zip(a.actions, b.actions)) if x != y]
            print(f"  room {i}: pnl {a.pnl} vs {b.pnl}, first differing day {diff[:3]}")

print(f"  rooms compared      : 200")
print(f"  mismatched rooms    : {mismatch}")
print(f"  shipped mean P&L    : {np.mean(ship_pnls):,.0f}")
print(f"  reference mean P&L  : {np.mean(ref_pnls):,.0f}")

print("\nOutput type contract (grader uses `type(x) != type(1)`)")
algo = Algorithm({})
algo.data = {"Liferaft Ticket": [100000.0, 95000.0, 103000.0, 98000.0,
                                 106000.0, 101000.0, 109000.0, 104000.0]}
algo.day = 7
frac = algo._sig_liferaft()
pos = int(round(frac * 1))
print(f"  signal returns {frac!r} -> position {pos!r}, type {type(pos).__name__}")
assert type(pos) is int, "position must be a builtin int"
assert pos in (-1, 0, 1)

print("\nEdge cases")
for label, series in [("empty history", []),
                      ("one price", [100000]),
                      ("two prices", [100000, 95000]),
                      ("at the floor", [100000, 20000]),
                      ("below floor (defensive)", [100000, 15000]),
                      ("flat forever", [100000] * 40)]:
    algo = Algorithm({})
    algo.data = {"Liferaft Ticket": list(series)}
    algo.day = max(0, len(series) - 1)
    v = algo._sig_liferaft()
    assert v in (-1.0, 0.0, 1.0), f"{label} returned {v}"
    print(f"  {label:<26} -> {v:+.0f}")

algo = Algorithm({})
algo.data = {}
print(f"  {'instrument missing':<26} -> {algo._sig_liferaft():+.0f}")

if mismatch == 0:
    print("\nShipped code is behaviourally identical to the tested strategy.")
else:
    print(f"\nWARNING: {mismatch} rooms diverged.")
    raise SystemExit(1)
