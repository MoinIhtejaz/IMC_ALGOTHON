"""
Candidate strategy and baselines.

PRE-REGISTRATION NOTE
---------------------
Every hyperparameter below is frozen at the value recommended in the original
research log BEFORE any held-out room was run:

    k (confidence discount)   = 2.0
    warmup (flat observation) = 40 days
    probe cadence             = every 6th day flat
    min sample per bucket     = 5
    floor rule                = long whenever price <= 20,000

Nothing here is refitted on the out-of-sample results. The sensitivity sweep in
run_oos.py varies these values only to test whether the reported optimum is a
plateau or a spike; the headline number always uses the frozen set.
"""

from __future__ import annotations

import math

from engine import FLOOR, Agent

# ---------------------------------------------------------------- baselines


class AlwaysFlat(Agent):
    name = "always-flat"

    def act(self, prices, moves, day):
        return 0


class AlwaysLong(Agent):
    name = "always-long"

    def act(self, prices, moves, day):
        return 1


class AlwaysShort(Agent):
    name = "always-short"

    def act(self, prices, moves, day):
        return -1


class FloorOnly(Agent):
    name = "floor-option-only"

    def act(self, prices, moves, day):
        return 1 if prices[-1] <= FLOOR else 0


# ------------------------------------------------------- the estimator core


def _regime(move):
    if move < 0:
        return 0      # crowd was long  (price fell)
    if move > 0:
        return 1      # crowd was short (price rose)
    return 2          # tie, empty room, or floor-masked


class RegimeContrarian(Agent):
    """
    The candidate. Conditions the crowd estimate on the current regime, applies
    a k-standard-error haircut to the edge, and abstains unless the discounted
    edge is still positive.

    A long's per-day payoff is exactly the realised price move, so the estimator
    runs directly on realised moves and needs no separate payoff model. The
    floor is handled for free: a majority-long day at the floor realises 0, and
    that zero enters the sample honestly.

    Buckets are maintained incrementally as (n, sum, sumsq) per regime.
    """

    def __init__(self, k=2.0, warmup=40, probe=6, min_n=5, pooled=False,
                 use_floor=True):
        self.k = k
        self.warmup = warmup
        self.probe = probe
        self.min_n = min_n
        self.pooled = pooled
        self.use_floor = use_floor
        self.name = f"{'pooled' if pooled else 'regime'}-k{k}"

    def reset(self, rng):
        self.rng = rng
        # index 0/1/2 = regime buckets, index 3 = pooled
        self.n = [0, 0, 0, 0]
        self.s = [0.0, 0.0, 0.0, 0.0]
        self.ss = [0.0, 0.0, 0.0, 0.0]

    def observe(self, prices, moves, my_action):
        # a (regime, outcome) pair becomes available once two moves exist
        m = len(moves)
        if m >= 2:
            r = _regime(moves[m - 2])
            x = moves[m - 1]
            for idx in (r, 3):
                self.n[idx] += 1
                self.s[idx] += x
                self.ss[idx] += x * x

    def _mean_se(self, idx):
        n = self.n[idx]
        if n < 2:
            return 0.0, float("inf"), n
        mean = self.s[idx] / n
        var = (self.ss[idx] - n * mean * mean) / (n - 1)
        if var < 0:
            var = 0.0
        return mean, math.sqrt(var / n), n

    def act(self, prices, moves, day):
        # layer 1: the floor is a free option and outranks everything else
        if self.use_floor and prices[-1] <= FLOOR:
            return 1

        # layer 2: observe without voting before trusting any estimate
        if day < self.warmup:
            return 0

        # layer 4: keep feeding the estimator uncontaminated reads
        if self.probe and day % self.probe == 0:
            return 0

        if not moves:
            return 0

        idx = 3 if self.pooled else _regime(moves[-1])
        mean, se, n = self._mean_se(idx)
        if n < self.min_n:
            return 0

        # layer 3: haircut the edge by k standard errors; both sides pay it
        if mean - self.k * se > 0:
            return 1
        if -mean - self.k * se > 0:
            return -1
        return 0


def candidate(**overrides):
    """The frozen recommended configuration."""
    cfg = dict(k=2.0, warmup=40, probe=6, min_n=5, pooled=False, use_floor=True)
    cfg.update(overrides)
    return RegimeContrarian(**cfg)
