"""
Stage 6: confirmation of a hypothesis on a fresh seed stream.

Stage 1 suggested that two of the five recommended layers cost money on held-out
rooms: the 40-day warmup and the every-6th-day probe. Acting on that observation
using the same rooms that produced it would be exactly the overfitting this
exercise is meant to detect.

So the hypothesis is stated first and then tested once, on a seed stream
(seed base 200,000) that has not been touched by any earlier stage:

    H1  removing the probe layer does not reduce mean P&L
    H2  removing the warmup layer does not reduce mean P&L
    H3  the k=2 discount still beats k=0 on tail risk

Both P&L differences are evaluated paired, room by room, so the comparison is
not contaminated by variation between rooms.
"""

import numpy as np

from engine import run
from harness import DAYS, rngf
from opponents import random_room
from strategies import candidate

N = 400
SEED = 200_000  # untouched by stages 1-5

CONFIGS = {
    "recommended (warmup 40, probe 6)": dict(),
    "no probe": dict(probe=0),
    "no warmup": dict(warmup=0),
    "no probe, no warmup": dict(probe=0, warmup=0),
    "k=0, recommended layers": dict(k=0.0),
    "k=0, no probe no warmup": dict(k=0.0, probe=0, warmup=0),
}

pnl = {name: [] for name in CONFIGS}
for i in range(N):
    room_rng = np.random.default_rng(SEED + i)
    spec = random_room(room_rng)
    for name, kw in CONFIGS.items():
        # rebuild the room per config so every config meets identical opponents
        opps = random_room(np.random.default_rng(SEED + i))
        pnl[name].append(run(candidate(**kw), opps, DAYS, rngf(SEED + i)).pnl)

base = np.array(pnl["recommended (warmup 40, probe 6)"], dtype=float)

print("=" * 118)
print(f"STAGE 6  CONFIRMATION ON FRESH SEEDS (base {SEED:,}), {N} rooms, paired by room")
print("=" * 118)
print(f"{'config':<34}{'mean':>13}{'median':>13}{'worst':>13}{'P(loss)':>10}"
      f"{'paired diff vs recommended':>32}")
print("-" * 118)

for name in CONFIGS:
    a = np.array(pnl[name], dtype=float)
    d = a - base
    if name.startswith("recommended"):
        note = "reference"
    else:
        # paired bootstrap on the mean difference
        rng = np.random.default_rng(1234)
        idx = rng.integers(0, N, size=(4000, N))
        boot = d[idx].mean(axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        sig = "" if lo < 0 < hi else "  *"
        note = f"{d.mean():>+12,.0f} [{lo:>+10,.0f},{hi:>+10,.0f}]{sig}"
    print(f"{name:<34}{a.mean():>13,.0f}{np.median(a):>13,.0f}{a.min():>13,.0f}"
          f"{(a < 0).mean():>10.2f}{note:>32}")

print("-" * 118)
print("  * = paired 95% bootstrap interval on the difference excludes zero")
