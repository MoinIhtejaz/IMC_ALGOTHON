"""
Shared evaluation harness.

Anti-overfitting design:
  1. Independent engine, verified separately against the spec.
  2. Held-out opponents: 15 archetypes, none in the original set of nine.
  3. Generated rooms, not curated ones. Sizes and compositions are sampled at
     random, so the score is an average over a distribution of opponents rather
     than over six scenarios chosen alongside the strategy.
  4. Frozen hyperparameters, fixed before any of these rooms existed.
  5. Distribution reporting: bootstrap CI on the mean plus quantiles, worst
     case and P(loss). A mean on its own hides everything that matters here.
  6. Disjoint seed streams per suite, listed in SEEDS below.

Room recipes are cached per (suite, index) so every strategy meets exactly the
same sequence of opponents. Agents are rebuilt for each run because they carry
state; only the sampling of the composition is cached.
"""

from __future__ import annotations

import json

import numpy as np

from engine import run
from opponents import HELD_OUT, _instantiate, random_room

DAYS = 365

SEEDS = {
    "headline": 10_000,
    "sensitivity": 10_000,   # same rooms as headline, on purpose: one variable at a time
    "adversarial": 30_000,
    "selfplay": 50_000,
    "roomsize": 70_000,
}


def rngf(seed):
    return lambda i: np.random.default_rng(seed * 9973 + i)


def summarise(pnls, traded):
    a = np.array(pnls, dtype=float)
    brng = np.random.default_rng(90_000)
    idx = brng.integers(0, len(a), size=(4000, len(a)))
    boot = a[idx].mean(axis=1)
    return {
        "n": int(len(a)),
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


def evaluate(make_strategy, n_rooms, seed_base, room_builder=None, room_kwargs=None):
    pnls, traded = [], []
    for i in range(n_rooms):
        room_rng = np.random.default_rng(seed_base + i)
        opps = (room_builder(room_rng) if room_builder is not None
                else random_room(room_rng, **(room_kwargs or {})))
        r = run(make_strategy(), opps, DAYS, rngf(seed_base + i))
        pnls.append(r.pnl)
        traded.append(r.days_traded)
    return summarise(pnls, traded)


HEAD = (f"{'strategy':<26}{'mean':>12} {'95% CI':>25} {'median':>11} {'p05':>11} "
        f"{'p95':>11} {'worst':>12} {'P(loss)':>8} {'days':>6}")
RULE = "-" * 132


def fmt(label, row):
    return (f"{label:<26}{row['mean']:>12,.0f} "
            f"[{row['ci_lo']:>10,.0f},{row['ci_hi']:>11,.0f}] "
            f"{row['median']:>11,.0f} {row['p05']:>11,.0f} {row['p95']:>11,.0f} "
            f"{row['worst']:>12,.0f} {row['p_loss']:>8.2f} {row['days']:>6.0f}")


def save(name, data):
    with open(f"stage_{name}.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nwrote stage_{name}.json")


def random_pick(rng):
    return _instantiate(HELD_OUT[int(rng.integers(len(HELD_OUT)))], rng)
