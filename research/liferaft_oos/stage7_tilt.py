"""
Stage 7: should abstention default to flat, or to long?

Motivation, and it is an honest one rather than a fishing expedition. On the
Round 1 scaffolding series the room goes long on 214 of 364 sided days, q = 0.588,
just inside the q = 8/13 = 0.615 break-even. That is a genuine edge for a long
worth about +$357 a day, but daily noise has a standard deviation of $6,399, so
a 2-standard-error haircut correctly rules it undetectable and the strategy sits
flat for the whole year, earning nothing where a constant long would have taken
roughly $130,000.

That series is scaffolding and proves nothing on its own. But it points at a
real design question: when no edge clears the haircut, is flat the right default,
given that long carries the lower bar (right 38.5% of the time versus 61.5%)?

Tested once, on a seed stream (base 400,000) untouched by stages 1-6, paired by
room. The variants:

    flat-default   what currently ships: no edge, no position
    long-default   no edge -> long anyway
    long-if-close  no edge -> long only if the undiscounted mean is positive
"""

import numpy as np

from engine import FLOOR, Agent, run
from harness import DAYS, rngf
from opponents import random_room
from strategies import _regime

N = 400
SEED = 400_000
K = 2.0
MIN_N = 5


class Variant(Agent):
    def __init__(self, default="flat"):
        self.default = default

    def reset(self, rng):
        self.rng = rng
        self.n = [0, 0, 0]
        self.s = [0.0, 0.0, 0.0]
        self.ss = [0.0, 0.0, 0.0]

    def observe(self, prices, moves, my_action):
        m = len(moves)
        if m >= 2:
            r = _regime(moves[m - 2])
            x = moves[m - 1]
            self.n[r] += 1
            self.s[r] += x
            self.ss[r] += x * x

    def act(self, prices, moves, day):
        if prices[-1] <= FLOOR:
            return 1
        if not moves:
            return 0
        i = _regime(moves[-1])
        n = self.n[i]
        if n < MIN_N:
            return 0
        mean = self.s[i] / n
        var = (self.ss[i] - n * mean * mean) / (n - 1)
        se = (max(var, 0.0) / n) ** 0.5
        if mean - K * se > 0:
            return 1
        if -mean - K * se > 0:
            return -1
        if self.default == "long":
            return 1
        if self.default == "long_if_positive":
            return 1 if mean > 0 else 0
        return 0


VARIANTS = {
    "flat-default (shipping)": "flat",
    "long-default": "long",
    "long-if-mean-positive": "long_if_positive",
}

pnl = {k: [] for k in VARIANTS}
notional_days = {k: [] for k in VARIANTS}
for i in range(N):
    for label, mode in VARIANTS.items():
        opps = random_room(np.random.default_rng(SEED + i))
        r = run(Variant(mode), opps, DAYS, rngf(SEED + i))
        pnl[label].append(r.pnl)
        notional_days[label].append(r.days_traded)

base = np.array(pnl["flat-default (shipping)"], dtype=float)

print("=" * 118)
print(f"STAGE 7  DEFAULT WHEN NO EDGE CLEARS  ({N} fresh rooms, base seed {SEED:,}, paired)")
print("=" * 118)
print(f"{'variant':<28}{'mean':>13}{'median':>13}{'p05':>13}{'worst':>13}"
      f"{'P(loss)':>9}{'days':>7}{'paired diff':>22}")
print("-" * 118)

for label in VARIANTS:
    a = np.array(pnl[label], dtype=float)
    if label.startswith("flat-default"):
        note = "reference"
    else:
        d = a - base
        rng = np.random.default_rng(77)
        idx = rng.integers(0, N, size=(4000, N))
        boot = d[idx].mean(axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        note = f"{d.mean():>+11,.0f}{'  *' if not (lo < 0 < hi) else '   '}"
    print(f"{label:<28}{a.mean():>13,.0f}{np.median(a):>13,.0f}"
          f"{np.percentile(a, 5):>13,.0f}{a.min():>13,.0f}"
          f"{(a < 0).mean():>9.2f}{np.mean(notional_days[label]):>7.0f}{note:>22}")

print("-" * 118)
print("  * = paired 95% bootstrap interval on the difference excludes zero")
print("  days = mean days holding a position, i.e. mean days consuming ~$100k of budget")
