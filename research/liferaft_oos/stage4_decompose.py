"""
Stage 4: where does the money actually come from?

Two failure modes that a headline mean cannot distinguish:

  (a) The edge is real only against deterministic opponents. Several held-out
      archetypes (alternator, price-anchor, late-entrant, anti-contrarian,
      window-follower, streak-breaker, floor-camper) are perfectly predictable
      once observed. Real teams will be messier. If the P&L disappears when
      every opponent carries randomness, the result is an artefact of the
      opponent model, exactly the weakness the original log flagged.

  (b) The edge is really the floor option in disguise. If most of the P&L is
      earned on days the price sits at $20,000, the estimator is decoration.
"""

import sys

import numpy as np

from engine import FLOOR, run
from harness import RULE, SEEDS, evaluate, fmt, rngf, save, summarise
from opponents import (HELD_OUT, BayesianBeta, BiasedRandom, EpsilonGreedy,
                       EWMAContrarian, FictitiousPlay, NoisyRegimeContrarian,
                       ThresholdHerder, _instantiate)
from strategies import AlwaysFlat, AlwaysLong, FloorOnly, candidate

HEAD = (f"{'case':<26}{'mean':>12} {'95% CI':>25} {'median':>11} {'p05':>11} "
        f"{'p95':>11} {'worst':>12} {'P(loss)':>8} {'days':>6}")

# archetypes that carry genuine randomness or adaptive state, i.e. the ones a
# real competing team is more likely to resemble
STOCHASTIC = [NoisyRegimeContrarian, EpsilonGreedy, BiasedRandom, ThresholdHerder,
              EWMAContrarian, FictitiousPlay, BayesianBeta]
DETERMINISTIC = [c for c in HELD_OUT if c not in STOCHASTIC]


def make_room(pool):
    def builder(rng, pool=pool):
        size = int(rng.integers(6, 46))
        conc = float(rng.choice([0.15, 0.4, 1.0, 3.0]))
        w = rng.dirichlet([conc] * len(pool))
        picks = rng.choice(len(pool), size=size, p=w)
        return [_instantiate(pool[i], rng) for i in picks]
    return builder


which = sys.argv[1] if len(sys.argv) > 1 else "pools"
out = {}

if which == "pools":
    print("=" * 132)
    print("STAGE 4a  DOES THE EDGE SURVIVE WITHOUT DETERMINISTIC OPPONENTS?  (250 rooms each)")
    print("=" * 132)
    print(HEAD)
    print(RULE)
    for pool_name, pool in [("all 15 archetypes", HELD_OUT),
                            ("stochastic only (7)", STOCHASTIC),
                            ("deterministic only (8)", DETERMINISTIC)]:
        for sname, mk in [("candidate", lambda: candidate()),
                          ("always-long", lambda: AlwaysLong()),
                          ("floor-only", lambda: FloorOnly())]:
            row = evaluate(mk, 250, SEEDS["headline"], room_builder=make_room(pool))
            out[f"{pool_name}/{sname}"] = row
            print(fmt(f"{sname:<12} {pool_name}", row))
        print(RULE)
    save("pools", out)

elif which == "attrib":
    print("=" * 132)
    print("STAGE 4b  P&L ATTRIBUTION: floor days vs live days  (300 rooms)")
    print("=" * 132)
    floor_pnl, live_pnl, tot, floor_frac = [], [], [], []
    from opponents import random_room
    for i in range(300):
        room_rng = np.random.default_rng(SEEDS["headline"] + i)
        opps = random_room(room_rng)
        r = run(candidate(), opps, 365, rngf(SEEDS["headline"] + i))
        f = l = 0
        for d, a in enumerate(r.actions):
            move = r.prices[d + 1] - r.prices[d]
            if r.prices[d] <= FLOOR:
                f += a * move
            else:
                l += a * move
        floor_pnl.append(f)
        live_pnl.append(l)
        tot.append(r.pnl)
        floor_frac.append(r.floor_days / 365)

    fp, lp, tt = np.array(floor_pnl), np.array(live_pnl), np.array(tot)
    print(f"  mean total P&L                 {tt.mean():>14,.0f}")
    print(f"  mean earned on floor days      {fp.mean():>14,.0f}  "
          f"({100 * fp.mean() / tt.mean():.1f}% of total)")
    print(f"  mean earned on live days       {lp.mean():>14,.0f}  "
          f"({100 * lp.mean() / tt.mean():.1f}% of total)")
    print(f"  rooms that ever reached floor  {100 * (np.array(floor_frac) > 0).mean():>13.1f}%")
    print(f"  mean share of year at floor    {100 * np.mean(floor_frac):>13.1f}%")
    print()
    print(f"  live-day P&L: median {np.median(lp):,.0f}  p05 {np.percentile(lp, 5):,.0f}  "
          f"worst {lp.min():,.0f}  P(loss) {(lp < 0).mean():.2f}")
    out = {"mean_total": float(tt.mean()), "mean_floor": float(fp.mean()),
           "mean_live": float(lp.mean()), "live_p_loss": float((lp < 0).mean())}
    save("attrib", out)

elif which == "null":
    print("=" * 132)
    print("STAGE 4c  NULL TEST: strategy against opponents with provably no exploitable pattern")
    print("=" * 132)
    print(HEAD)
    print(RULE)

    def iid_room(rng, p_long=0.5, n=20):
        return [BiasedRandom(p_long=p_long, p_flat=0.0) for _ in range(n)]

    for p in [0.5, 0.55, 0.62, 0.7]:
        row = evaluate(lambda: candidate(), 200, SEEDS["adversarial"],
                       room_builder=lambda rng, p=p: iid_room(rng, p))
        out[f"iid p_long={p}"] = row
        print(fmt(f"i.i.d. p_long = {p}", row))
    print(RULE)
    print("  an i.i.d. room has no regime structure, so a correct estimator should")
    print("  approach always-flat. Anything large here is the floor option or luck.")
    save("null", out)
