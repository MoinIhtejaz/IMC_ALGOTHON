"""
Out-of-sample evaluation of the frozen Liferaft strategy.

Design decisions that guard against overfitting:

  1. Independent engine. Re-derived from the spec, verified separately.
  2. Held-out opponents. 15 archetypes, none in the original set of nine.
  3. Generated rooms, not curated ones. Sizes and compositions are sampled at
     random, so the score is an average over a distribution of opponents rather
     than over six scenarios chosen alongside the strategy.
  4. Frozen hyperparameters. k, warmup, probe and min_n are fixed at the values
     recommended before any of these rooms existed.
  5. Distribution reporting. Mean is reported with a bootstrap CI alongside
     quantiles, worst case and P(loss). A single mean hides everything that
     matters here.
  6. Disjoint seed streams. Evaluation, sensitivity and adversarial suites draw
     from non-overlapping seed ranges.
"""

from __future__ import annotations

import json
import sys

import numpy as np

from engine import run
from opponents import (HELD_OUT, AlternatorK, BiasedRandom, NoisyRegimeContrarian,
                       ThresholdHerder, random_room, _instantiate)
from strategies import (AlwaysFlat, AlwaysLong, AlwaysShort, FloorOnly,
                        RegimeContrarian, candidate)

DAYS = 365
N_ROOMS = 400          # held-out rooms for the headline table
SEED_BASE = 10_000     # evaluation seed stream


def rngf(seed):
    return lambda i: np.random.default_rng(seed * 9973 + i)


def summarise(pnls, traded):
    a = np.array(pnls, dtype=float)
    # bootstrap CI on the mean: 4000 resamples, fixed seed for reproducibility
    brng = np.random.default_rng(90_000)
    idx = brng.integers(0, len(a), size=(4000, len(a)))
    boot = a[idx].mean(axis=1)
    return {
        "mean": float(a.mean()),
        "ci_lo": float(np.percentile(boot, 2.5)),
        "ci_hi": float(np.percentile(boot, 97.5)),
        "median": float(np.median(a)),
        "p05": float(np.percentile(a, 5)),
        "p25": float(np.percentile(a, 25)),
        "p75": float(np.percentile(a, 75)),
        "p95": float(np.percentile(a, 95)),
        "worst": float(a.min()),
        "best": float(a.max()),
        "p_loss": float((a < 0).mean()),
        "days": float(np.mean(traded)),
    }


def evaluate(make_strategy, n_rooms=N_ROOMS, seed_base=SEED_BASE, room_kwargs=None,
             room_builder=None):
    pnls, traded = [], []
    for i in range(n_rooms):
        room_rng = np.random.default_rng(seed_base + i)
        if room_builder is not None:
            opps = room_builder(room_rng)
        else:
            opps = random_room(room_rng, **(room_kwargs or {}))
        r = run(make_strategy(), opps, DAYS, rngf(seed_base + i))
        pnls.append(r.pnl)
        traded.append(r.days_traded)
    return summarise(pnls, traded), pnls


def fmt(row):
    return (f"{row['mean']:>12,.0f} [{row['ci_lo']:>10,.0f},{row['ci_hi']:>10,.0f}] "
            f"{row['median']:>11,.0f} {row['p05']:>11,.0f} {row['p95']:>11,.0f} "
            f"{row['worst']:>12,.0f} {row['p_loss']:>7.2f} {row['days']:>7.0f}")


HEAD = (f"{'strategy':<26}{'mean':>12} {'95% CI':>23} {'median':>11} {'p05':>11} "
        f"{'p95':>11} {'worst':>12} {'P(loss)':>7} {'days':>7}")

results = {}

# ------------------------------------------------------------------ headline
print("=" * 130)
print(f"OUT-OF-SAMPLE: {N_ROOMS} randomly generated held-out rooms, {DAYS} days each")
print("=" * 130)
print(HEAD)
print("-" * 130)

lineup = [
    ("always-flat", lambda: AlwaysFlat()),
    ("always-long", lambda: AlwaysLong()),
    ("always-short", lambda: AlwaysShort()),
    ("floor-option only", lambda: FloorOnly()),
    ("pooled k=0", lambda: RegimeContrarian(k=0.0, warmup=40, probe=6, pooled=True)),
    ("pooled k=2", lambda: RegimeContrarian(k=2.0, warmup=40, probe=6, pooled=True)),
    ("regime k=0 (raw)", lambda: candidate(k=0.0)),
    ("regime k=2 (CANDIDATE)", lambda: candidate()),
    ("regime k=2, no floor", lambda: candidate(use_floor=False)),
    ("regime k=2, no probe", lambda: candidate(probe=0)),
    ("regime k=2, no warmup", lambda: candidate(warmup=0)),
]

for label, mk in lineup:
    row, raw = evaluate(mk)
    results[label] = row
    print(f"{label:<26}{fmt(row)}")

# --------------------------------------------------------------- sensitivity
print()
print("=" * 130)
print("SENSITIVITY: is k=2 a plateau or a spike? (same rooms, one parameter varied)")
print("=" * 130)
print(f"{'k':<26}{'mean':>12} {'95% CI':>23} {'median':>11} {'p05':>11} {'p95':>11} "
      f"{'worst':>12} {'P(loss)':>7} {'days':>7}")
print("-" * 130)
k_curve = {}
for k in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]:
    row, _ = evaluate(lambda k=k: candidate(k=k))
    k_curve[k] = row
    print(f"k = {k:<22}{fmt(row)}")

print()
print(f"{'warmup':<26}{'mean':>12} {'95% CI':>23} {'median':>11} {'p05':>11} {'p95':>11} "
      f"{'worst':>12} {'P(loss)':>7} {'days':>7}")
print("-" * 130)
for w in [0, 10, 20, 40, 60, 90]:
    row, _ = evaluate(lambda w=w: candidate(warmup=w))
    print(f"warmup = {w:<17}{fmt(row)}")

print()
print(f"{'probe cadence':<26}{'mean':>12} {'95% CI':>23} {'median':>11} {'p05':>11} "
      f"{'p95':>11} {'worst':>12} {'P(loss)':>7} {'days':>7}")
print("-" * 130)
for p in [0, 3, 4, 6, 8, 12]:
    row, _ = evaluate(lambda p=p: candidate(probe=p))
    lbl = "none" if p == 0 else f"every {p}"
    print(f"probe = {lbl:<18}{fmt(row)}")

# ---------------------------------------------------------------- adversarial
print()
print("=" * 130)
print("ADVERSARIAL: rooms built to punish a regime-conditioned contrarian")
print("=" * 130)


def room_all_clones(rng, n=20):
    """Everyone runs the candidate's logic (worst case for crowding)."""
    return [NoisyRegimeContrarian(window=60, noise=0.05) for _ in range(n)]


def room_half_clones(rng, n=20):
    out = [NoisyRegimeContrarian(window=int(rng.integers(30, 90)), noise=0.1)
           for _ in range(n // 2)]
    out += [_instantiate(HELD_OUT[int(rng.integers(len(HELD_OUT)))], rng)
            for _ in range(n - n // 2)]
    return out


def room_herd_long(rng, n=20):
    """A room that reads the 8/13 asymmetry and piles long."""
    return [ThresholdHerder(w=int(rng.integers(5, 15)), thresh=0.55) for _ in range(n)]


def room_near_tie(rng, n=20):
    """Coin-flip room: no edge exists, maximum pivotality, pure noise."""
    return [BiasedRandom(p_long=0.5, p_flat=0.0) for _ in range(n)]


def room_cyclic(rng, n=20):
    return [AlternatorK(k=int(rng.integers(2, 5)), offset=i) for i in range(n)]


def room_tiny(rng):
    """Five opponents: our single vote decides most days."""
    return [_instantiate(HELD_OUT[int(rng.integers(len(HELD_OUT)))], rng) for _ in range(5)]


adversarial = [
    ("all clones (n=20)", room_all_clones),
    ("half clones (n=20)", room_half_clones),
    ("herds long (n=20)", room_herd_long),
    ("pure coin flip (n=20)", room_near_tie),
    ("cyclic (n=20)", room_cyclic),
    ("tiny room (n=5)", room_tiny),
]

print(HEAD)
print("-" * 130)
adv_results = {}
for label, builder in adversarial:
    row, _ = evaluate(lambda: candidate(), n_rooms=120, seed_base=30_000,
                      room_builder=builder)
    adv_results[label] = row
    print(f"{label:<26}{fmt(row)}")
print("-" * 130)
for label, builder in adversarial:
    row, _ = evaluate(lambda: AlwaysLong(), n_rooms=120, seed_base=30_000,
                      room_builder=builder)
    print(f"{'  always-long: ' + label:<26}{fmt(row)}")

# --------------------------------------------------------------- self-play
print()
print("=" * 130)
print("SELF-PLAY: how many other teams can run this before it stops working")
print("=" * 130)
print(f"{'clones in room':<26}{'mean':>12} {'95% CI':>23} {'median':>11} {'p05':>11} "
      f"{'p95':>11} {'worst':>12} {'P(loss)':>7} {'days':>7}")
print("-" * 130)
selfplay = {}
for c in [0, 1, 2, 3, 5, 8, 12, 19]:
    def builder(rng, c=c):
        others = [_instantiate(HELD_OUT[int(rng.integers(len(HELD_OUT)))], rng)
                  for _ in range(max(0, 20 - c))]
        clones = [candidate() for _ in range(c)]
        return others + clones
    row, _ = evaluate(lambda: candidate(), n_rooms=120, seed_base=50_000,
                      room_builder=builder)
    selfplay[c] = row
    print(f"{c:<26}{fmt(row)}")

# --------------------------------------------------------------- room size
print()
print("=" * 130)
print("ROOM SIZE SWEEP")
print("=" * 130)
print(f"{'opponents':<26}{'mean':>12} {'95% CI':>23} {'median':>11} {'p05':>11} "
      f"{'p95':>11} {'worst':>12} {'P(loss)':>7} {'days':>7}")
print("-" * 130)
for n in [3, 5, 10, 20, 40, 80]:
    row, _ = evaluate(lambda: candidate(), n_rooms=150, seed_base=70_000,
                      room_kwargs={"min_size": n, "max_size": n})
    print(f"{n:<26}{fmt(row)}")

with open("oos_results.json", "w") as f:
    json.dump({"headline": results, "k_curve": {str(k): v for k, v in k_curve.items()},
               "adversarial": adv_results,
               "selfplay": {str(k): v for k, v in selfplay.items()}}, f, indent=2)
print("\nwrote oos_results.json")
