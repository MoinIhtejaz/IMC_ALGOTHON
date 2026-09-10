"""
Whole-portfolio comparison of Liferaft rules.

Round 1 price paths for the eight generated instruments; the Liferaft price
evolves live from a random held-out room including our own vote. Every variant
sees the SAME rooms with the SAME opponent seeds, so differences are paired.

Two readings of the floor rule are simulated, because Change 1 exists precisely
to hedge the difference between them:

  clipped      P&L is marked on the clipped price. A majority-long day at the
               floor realises exactly $0. This is what the spec implies and what
               every earlier run assumed.
  notional     the -$5,000 is booked before clipping, so a long at the floor
               bleeds $5,000 a day. Strictly worse, and unfalsifiable from the
               Round 1 CSV alone.
"""

import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "research", "liferaft_oos"))
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

from opponents import random_room                     # noqa: E402
from algo_variants import VARIANTS                    # noqa: E402
from algorithm import Algorithm as ShippedAlgorithm   # noqa: E402
from scenario_liferaft import load_round1, LIMITS, CAP, START_PRICE, FLOOR  # noqa: E402

LONG_MOVE = -5_000
SHORT_MOVE = +8_000
SHARDS = os.path.join(HERE, "shards")


class CloneOfBase:
    """Another team running the ORIGINAL un-patched rule. This is the right
    clone to model: teams copy the published idea, not our risk controls."""
    name = "clone-base"

    def reset(self, rng):
        self.rng = rng
        self._a = VARIANTS["base"]({k: 0 for k in LIMITS})
        self._a.positionLimits = LIMITS

    def act(self, prices, moves, day):
        self._a.day = day
        self._a.data = {"Liferaft Ticket": list(prices)}
        f = self._a._sig_liferaft()
        return 1 if f > 0 else (-1 if f < 0 else 0)

    def observe(self, prices, moves, a):
        return None


def run_year(cls, price_data, room, rng, floor_mode="clipped", days=365):
    for o in room:
        o.reset(np.random.default_rng(rng.integers(0, 2**63 - 1)))

    algo = cls({k: 0 for k in LIMITS})
    algo.positionLimits = LIMITS

    lr_prices = [START_PRICE]
    lr_moves = []
    prev = {k: 0 for k in LIMITS}
    price_pnl = 0.0
    lr_pnl = 0.0
    breaches = 0
    traded = 0
    floor_days = 0

    for day in range(days):
        hist = {k: v[:day + 1] for k, v in price_data.items()}
        hist["Liferaft Ticket"] = list(lr_prices)
        algo.day, algo.data, algo.positions = day, hist, prev
        pos = algo.get_positions()

        my = int(pos["Liferaft Ticket"])
        book = sum(abs(pos[k] * hist[k][-1]) for k in LIMITS if hist.get(k))
        if book > CAP:
            breaches += 1
            pos = {k: 0 for k in LIMITS}
            my = 0
        if my:
            traded += 1
        if lr_prices[-1] <= FLOOR:
            floor_days += 1

        longs = 1 if my > 0 else 0
        shorts = 1 if my < 0 else 0
        oa = []
        for o in room:
            x = int(o.act(lr_prices, lr_moves, day))
            oa.append(x)
            if x > 0:
                longs += 1
            elif x < 0:
                shorts += 1

        delta = LONG_MOVE if longs > shorts else (SHORT_MOVE if shorts > longs else 0)
        new_price = max(FLOOR, lr_prices[-1] + delta)
        clipped_move = new_price - lr_prices[-1]
        # the two readings differ ONLY when the floor bites
        realised = clipped_move if floor_mode == "clipped" else delta
        lr_pnl += my * realised

        lr_prices.append(new_price)
        lr_moves.append(clipped_move)     # public price path is the same either way
        for o, x in zip(room, oa):
            o.observe(lr_prices, lr_moves, x)

        if day:
            for k in LIMITS:
                if k != "Liferaft Ticket":
                    price_pnl += prev[k] * (price_data[k][day] - price_data[k][day - 1])
        prev = pos

    return price_pnl, lr_pnl, breaches, traded, floor_days


def shard(k, count, variant, floor_mode="clipped", clones=0):
    os.makedirs(SHARDS, exist_ok=True)
    tag = f"var_{variant}_{floor_mode}_c{clones}_n{count}_{k:04d}.npz"
    out = os.path.join(SHARDS, tag)
    if os.path.exists(out):
        return "skip"

    data = load_round1()
    cls = VARIANTS[variant]
    master = np.random.default_rng(20260809 + 1000 * k)   # SAME seeds as A/A2
    tot, pri, lrp, trd, fld = [], [], [], [], []
    for _ in range(count):
        rng = np.random.default_rng(master.integers(0, 2**63 - 1))
        room = random_room(rng)
        if clones:
            room = room + [CloneOfBase() for _ in range(clones)]
        p, l, br, t, f = run_year(cls, data, room, rng, floor_mode)
        assert br == 0, "budget breach"
        tot.append(p + l); pri.append(p); lrp.append(l); trd.append(t); fld.append(f)
    np.savez(out, total=tot, price=pri, liferaft=lrp, traded=trd, floor=fld)
    return "done"


def gather(variant, floor_mode="clipped", clones=0, count=2):
    pre = f"var_{variant}_{floor_mode}_c{clones}_n{count}_"
    fs = sorted(f for f in os.listdir(SHARDS) if f.startswith(pre))
    if not fs:
        return None
    ps = [np.load(os.path.join(SHARDS, f)) for f in fs]
    return {k: np.concatenate([p[k] for p in ps]) for k in ps[0].files}


if __name__ == "__main__":
    _, k0, k1, cnt, var = sys.argv[1:6]
    fm = sys.argv[6] if len(sys.argv) > 6 else "clipped"
    cl = int(sys.argv[7]) if len(sys.argv) > 7 else 0
    for k in range(int(k0), int(k1)):
        print(f"  {var}/{fm}/c{cl} shard {k} -> {shard(k, int(cnt), var, fm, cl)}", flush=True)
