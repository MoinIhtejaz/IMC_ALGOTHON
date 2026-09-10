"""
Liferaft risk management -- design and testing.

Fast harness: simulates ONLY the Liferaft (the room + our vote), with no full
book. That is enough to rank risk overlays against each other, because the
overlay only ever changes the Liferaft position. The winner is then re-tested in
the full joint simulation, where budget coupling matters.

Every variant sees the SAME rooms with the SAME seeds, so all comparisons are
paired and the differences are not sampling noise.
"""

import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "research", "liferaft_oos"))

from opponents import random_room  # noqa: E402

START = 100_000
FLOOR = 20_000
LONG = -5_000
SHORT = +8_000
DAYS = 365
MIN_N = 5


def regime(m):
    return -1 if m < 0 else (1 if m > 0 else 0)


# ---------------------------------------------------------------------------
# The base signal, extracted verbatim from algorithm.py so the harness cannot
# quietly diverge from what is shipped.
# ---------------------------------------------------------------------------

def base_signal(prices, moves, k=2.0, window=None, min_n=MIN_N):
    if prices[-1] <= FLOOR:
        return 1
    if len(moves) < 2:
        return 0

    hist = moves if window is None else moves[-window:]
    if len(hist) < 2:
        return 0

    cur = regime(moves[-1])
    n = 0
    tot = 0.0
    tsq = 0.0
    for t in range(1, len(hist)):
        if regime(hist[t - 1]) == cur:
            x = float(hist[t])
            n += 1
            tot += x
            tsq += x * x
    if n < min_n:
        return 0

    mean = tot / n
    var = (tsq - n * mean * mean) / (n - 1)
    if var < 0:
        var = 0.0
    se = (var / n) ** 0.5
    if mean - k * se > 0:
        return 1
    if -mean - k * se > 0:
        return -1
    return 0


# ---------------------------------------------------------------------------
# Risk overlays. Each is a callable taking a small state dict and returning the
# action actually taken.
# ---------------------------------------------------------------------------

class Strategy:
    def __init__(self, name, **kw):
        self.name = name
        self.kw = kw

    def reset(self):
        self.pnl = 0.0
        self.peak = 0.0
        self.halt_until = -1
        self.recent = []

    def act(self, prices, moves, day):
        kw = self.kw
        mode = kw.get("mode", "base")

        # The floor long is exempt from every risk control. At $20,000 the
        # downside is clipped to zero while the +$8,000 upside is untouched, so
        # it is a free option -- suppressing it during a stand-down gives away
        # profit without removing any risk. Worth being explicit about, because
        # the naive way to write a stop-loss switches this off too.
        if prices[-1] <= FLOOR:
            return 1

        # realised P&L bookkeeping happens in run(); here we only decide
        if mode == "base":
            return base_signal(prices, moves, k=kw.get("k", 2.0))

        if mode == "window":
            return base_signal(prices, moves, k=kw.get("k", 2.0),
                               window=kw["window"])

        if mode == "stop":
            # hard stop: once cumulative Liferaft P&L breaches -limit, flat for
            # the rest of the year. Maximal protection, zero recovery.
            if self.pnl <= -kw["limit"]:
                return 0
            return base_signal(prices, moves, k=kw.get("k", 2.0))

        if mode == "stop_reentry":
            # stand down for `cool` days after a breach of trailing drawdown,
            # then resume with the drawdown mark reset
            if day < self.halt_until:
                return 0
            dd = self.pnl - self.peak
            if dd <= -kw["limit"]:
                self.halt_until = day + kw["cool"]
                self.peak = self.pnl
                return 0
            return base_signal(prices, moves, k=kw.get("k", 2.0))

        if mode == "adaptive_k":
            # widen the confidence haircut in proportion to how much we are
            # down. Losing means the room is not behaving the way the bucket
            # says, so demand more evidence before betting again.
            dd = max(0.0, self.peak - self.pnl)
            k = kw.get("k", 2.0) + kw["c"] * (dd / 100_000.0)
            k = min(k, kw.get("kmax", 8.0))
            return base_signal(prices, moves, k=k)

        if mode == "hitgate":
            # Track how our OWN recent bets actually did. A regime bucket can
            # look statistically fine while the room has adapted around us --
            # realised performance notices that, the bucket does not.
            r = self.recent
            if len(r) >= kw["n"]:
                w = r[-kw["n"]:]
                if sum(w) <= kw.get("floor_pnl", 0):
                    return 0
            return base_signal(prices, moves, k=kw.get("k", 2.0))

        if mode == "adapt_hit":
            r = self.recent
            dd = max(0.0, self.peak - self.pnl)
            k = min(kw.get("k", 2.0) + kw["c"] * (dd / 100_000.0), kw.get("kmax", 8.0))
            if len(r) >= kw["n"]:
                w = r[-kw["n"]:]
                if sum(w) <= kw.get("floor_pnl", 0):
                    k = min(k + kw.get("bump", 2.0), kw.get("kmax", 8.0))
            return base_signal(prices, moves, k=k)

        if mode == "combo":
            # adaptive haircut + trailing stop with re-entry + rolling window
            if day < self.halt_until:
                return 0
            dd_stop = self.pnl - self.peak
            if dd_stop <= -kw["limit"]:
                self.halt_until = day + kw["cool"]
                self.peak = self.pnl
                return 0
            dd = max(0.0, self.peak - self.pnl)
            k = min(kw.get("k", 2.0) + kw["c"] * (dd / 100_000.0), kw.get("kmax", 8.0))
            return base_signal(prices, moves, k=k, window=kw.get("window"))

        raise ValueError(mode)


def run(strat, room, rng, days=DAYS):
    strat.reset()
    for i, o in enumerate(room):
        o.reset(np.random.default_rng(rng.integers(0, 2**63 - 1)))

    prices = [START]
    moves = []
    prev = 0
    traded = 0
    worst_dd = 0.0

    for day in range(days):
        a = int(strat.act(prices, moves, day))
        if a:
            traded += 1

        longs = 1 if a > 0 else 0
        shorts = 1 if a < 0 else 0
        oa = []
        for o in room:
            x = int(o.act(prices, moves, day))
            oa.append(x)
            if x > 0:
                longs += 1
            elif x < 0:
                shorts += 1

        delta = LONG if longs > shorts else (SHORT if shorts > longs else 0)
        new = max(FLOOR, prices[-1] + delta)
        realised = new - prices[-1]

        strat.pnl += a * realised
        if a:
            strat.recent.append(a * realised)
        strat.peak = max(strat.peak, strat.pnl)
        worst_dd = min(worst_dd, strat.pnl - strat.peak)

        prices.append(new)
        moves.append(realised)
        for o, x in zip(room, oa):
            o.observe(prices, moves, x)
        prev = a

    return strat.pnl, traded, worst_dd


def make_rooms(n, seed=4242, clones=0):
    master = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        s = int(master.integers(0, 2**63 - 1))
        out.append(s)
    return out


VARIANTS = [
    Strategy("A. baseline (no risk mgmt)", mode="base", k=2.0),
    Strategy("B. adaptive k c=4", mode="adaptive_k", k=2.0, c=4.0),
    Strategy("C. adaptive c=4 + hit-gate", mode="adapt_hit", k=2.0, c=4.0, n=40, bump=3.0, kmax=12.0),
    Strategy("D. adaptive c=8 + hit-gate", mode="adapt_hit", k=2.0, c=8.0, n=40, bump=3.0, kmax=12.0),
]


def evaluate(n_rooms=600, seed=4242, clones=0, variants=None):
    variants = variants or VARIANTS
    seeds = make_rooms(n_rooms, seed)
    res = {v.name: [] for v in variants}
    traded = {v.name: [] for v in variants}

    for s in seeds:
        for v in variants:
            rng = np.random.default_rng(s)          # identical room per variant
            room = random_room(rng)
            if clones:
                room = room + [CloneAgent() for _ in range(clones)]
            rng2 = np.random.default_rng(s)         # identical opponent seeds
            p, t, _ = run(v, room, rng2)
            res[v.name].append(p)
            traded[v.name].append(t)
    return {k: np.array(v) for k, v in res.items()}, {k: np.array(v) for k, v in traded.items()}


class CloneAgent:
    """Another team running the same base signal."""
    name = "clone"

    def reset(self, rng):
        self.rng = rng

    def act(self, prices, moves, day):
        return base_signal(list(prices), list(moves), k=2.0)

    def observe(self, prices, moves, a):
        return None


def table(res, traded, base="baseline (shipped)"):
    b = res[base]
    print(f"{'variant':<26}{'mean':>11}{'median':>11}{'p05':>11}{'worst':>11}"
          f"{'P(loss)':>9}{'days':>7}{'vs base':>11}")
    for name, v in res.items():
        print(f"{name:<26}{v.mean():>11,.0f}{np.median(v):>11,.0f}"
              f"{np.percentile(v,5):>11,.0f}{v.min():>11,.0f}"
              f"{float((v<0).mean()):>9.3f}{np.mean(traded[name]):>7.0f}"
              f"{v.mean()-b.mean():>+11,.0f}")


SH = os.path.join(HERE, "shards")


def shard(k, count, clones=0):
    os.makedirs(SH, exist_ok=True)
    tag = f"risk_c{clones}_{k:04d}.npz"
    out = os.path.join(SH, tag)
    if os.path.exists(out):
        return "skip"
    r, t = evaluate(count, seed=4242 + 7919 * k, clones=clones)
    names = list(r.keys())
    np.savez(out, names=names,
             res=np.array([r[n] for n in names]),
             traded=np.array([t[n] for n in names]))
    return "done"


def gather(clones=0):
    pre = f"risk_c{clones}_"
    fs = sorted(f for f in os.listdir(SH) if f.startswith(pre))
    if not fs:
        return None, None
    ps = [np.load(os.path.join(SH, f), allow_pickle=True) for f in fs]
    names = [str(x) for x in ps[0]["names"]]
    res = {n: np.concatenate([p["res"][i] for p in ps]) for i, n in enumerate(names)}
    trd = {n: np.concatenate([p["traded"][i] for p in ps]) for i, n in enumerate(names)}
    return res, trd


if __name__ == "__main__":
    if sys.argv[1] == "shard":
        k0, k1, cnt = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        cl = int(sys.argv[5]) if len(sys.argv) > 5 else 0
        for k in range(k0, k1):
            print(f"  risk shard c{cl}:{k} -> {shard(k, cnt, cl)}", flush=True)
    else:
        cl = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        r, t = gather(cl)
        print(f"LIFERAFT RISK OVERLAYS -- {len(next(iter(r.values())))} paired rooms, {cl} clones\n")
        table(r, t)
