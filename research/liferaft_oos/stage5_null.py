"""
Stage 5: a true zero-edge null.

An i.i.d. room of independent voters is NOT a null. With 20 voters at p=0.62
each, the room goes long about 87% of days, which is a large exploitable edge.
The sharpest test of whether a strategy manufactures P&L out of noise is a room
where the expected payoff of every action is exactly zero.

Construction: all opponents follow one shared daily coin that lands long with
probability 8/13 and short otherwise. Then

    E[move] = (8/13)(-5000) + (5/13)(+8000) = 0

so a long, a short and a flat all have expectation zero, the draws are i.i.d.
so no regime structure exists, and the block is large enough that our single
vote is never pivotal. A correctly calibrated strategy should trade rarely and
finish near zero. Systematic profit here would mean the estimator is reading
noise as signal; a large loss would mean it is being farmed by its own variance.
"""

import numpy as np

from engine import Agent
from harness import RULE, evaluate, fmt, save
from strategies import AlwaysFlat, AlwaysLong, AlwaysShort, candidate

HEAD = (f"{'case':<26}{'mean':>12} {'95% CI':>25} {'median':>11} {'p05':>11} "
        f"{'p95':>11} {'worst':>12} {'P(loss)':>8} {'days':>6}")

P_LONG = 8 / 13


class SharedCoin(Agent):
    """
    All copies in a room share one seeded coin sequence, so the block votes as a
    unit and the daily majority is an exact Bernoulli(P_LONG) draw.
    """
    name = "shared-coin"

    def __init__(self, seq):
        self.seq = seq

    def act(self, prices, moves, day):
        return 1 if self.seq[day] else -1


def null_room(rng, n=21, p=P_LONG, days=366):
    seq = rng.random(days) < p
    return [SharedCoin(seq) for _ in range(n)]


print("=" * 132)
print("STAGE 5  TRUE ZERO-EDGE NULL: room votes as a block, P(long) = 8/13 exactly")
print("=" * 132)
print(f"  theoretical E[daily move] = (8/13)(-5000) + (5/13)(+8000) = "
      f"{P_LONG * -5000 + (1 - P_LONG) * 8000:.1f}")
print()
print(HEAD)
print(RULE)

out = {}
for label, mk in [("candidate (k=2)", lambda: candidate()),
                  ("regime k=0", lambda: candidate(k=0.0)),
                  ("pooled k=2", lambda: candidate(pooled=True)),
                  ("always-long", lambda: AlwaysLong()),
                  ("always-short", lambda: AlwaysShort()),
                  ("always-flat", lambda: AlwaysFlat())]:
    row = evaluate(mk, 400, 80_000, room_builder=null_room)
    out[label] = row
    print(fmt(label, row))

print(RULE)
print("  a calibrated strategy should sit near zero here and trade rarely.")
print("  the floor is reachable by chance, so a small positive mean is legitimate;")
print("  a large one is not.")

# how often does the null room drift to the floor by luck alone?
hits = 0
for i in range(400):
    rng = np.random.default_rng(80_000 + i)
    seq = rng.random(366) < P_LONG
    p = 100_000
    for d in range(365):
        p = max(20_000, p + (-5000 if seq[d] else 8000))
    hits += p <= 20_000
print(f"\n  null rooms ending pinned at the floor: {100 * hits / 400:.1f}%")

save("null_true", out)
