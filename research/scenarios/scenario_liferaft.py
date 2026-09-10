"""
Scenario A -- Liferaft room risk.

Round 1 price paths are held fixed for the eight generated instruments. The
only thing that varies is the room: who else is in the competition and what
they do. The Liferaft price is evolved live, day by day, from the actual
majority rule, with our own vote included, so the feedback loop is real.

This is a *joint* simulation, not a bolt-on: the full Algorithm runs each day,
its Liferaft vote comes out of the same budget allocation as everything else,
and the notional the Liferaft position consumes is taken away from the rest of
the book exactly as it would be during marking.
"""

import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "research", "liferaft_oos"))
sys.path.insert(0, REPO)

from opponents import random_room          # noqa: E402
from algorithm import Algorithm            # noqa: E402

START_PRICE = 100_000
FLOOR = 20_000
LONG_MOVE = -5_000
SHORT_MOVE = +8_000

LIMITS = {
    "Fintech Token": 100, "Thrifted Jeans": 800, "UQ Dollar": 650,
    "Sausage Sizzle": 3000, "Bread": 500, "MenuDash": 75000,
    "Sausage": 5000, "Liferaft Ticket": 1, "Boat Party Ticket": 1000,
}
CAP = 600_000


class CloneOfUs:
    """Another team that reached the same conclusion we did.

    This is the strategy's one documented structural weakness: the edge comes
    from being on the minority side, so anyone running the same regime-
    conditioned rule votes the same way we do on the same days, and the copies
    push each other into the majority. Modelled by running the real signal.
    """
    name = "clone-of-us"

    def reset(self, rng):
        self.rng = rng
        self._a = Algorithm({k: 0 for k in LIMITS})
        self._a.positionLimits = LIMITS

    def act(self, prices, moves, day):
        self._a.day = day
        self._a.data = {"Liferaft Ticket": list(prices)}
        f = self._a._sig_liferaft()
        return 1 if f > 0 else (-1 if f < 0 else 0)

    def observe(self, prices, moves, my_action):
        return None


def load_round1():
    folder = os.path.join(REPO, "trader_interface", "data")
    out = {}
    for f in os.listdir(folder):
        if f.endswith("_price_history.csv"):
            out[f.split("_")[0]] = pd.read_csv(os.path.join(folder, f))["Price"].tolist()
    return out


def run_year(price_data, room, rng, days=365):
    """One simulated year. Returns (total, price_book, liferaft, diagnostics)."""
    for i, opp in enumerate(room):
        opp.reset(np.random.default_rng(rng.integers(0, 2**63 - 1)))

    algo = Algorithm({k: 0 for k in LIMITS})
    algo.positionLimits = LIMITS

    lr_prices = [START_PRICE]
    lr_moves = []
    prev = {k: 0 for k in LIMITS}

    price_pnl = 0.0
    lr_pnl = 0.0
    breaches = 0
    lr_days_traded = 0
    lr_days_long = 0

    for day in range(days):
        hist = {k: v[:day + 1] for k, v in price_data.items()}
        hist["Liferaft Ticket"] = list(lr_prices)

        algo.day = day
        algo.data = hist
        algo.positions = prev
        pos = algo.get_positions()

        my = int(pos["Liferaft Ticket"])
        if my not in (-1, 0, 1):
            raise ValueError(f"illegal liferaft action {my} on day {day}")

        # grader's budget check, at decision-time prices
        book = sum(abs(pos[k] * hist[k][-1]) for k in LIMITS if hist.get(k))
        if book > CAP:
            breaches += 1
            pos = {k: 0 for k in LIMITS}
            my = 0

        if my:
            lr_days_traded += 1
            if my > 0:
                lr_days_long += 1

        # --- resolve the room (simultaneous; nobody saw our action) ---
        longs = 1 if my > 0 else 0
        shorts = 1 if my < 0 else 0
        opp_actions = []
        for o in room:
            a = int(o.act(lr_prices, lr_moves, day))
            opp_actions.append(a)
            if a > 0:
                longs += 1
            elif a < 0:
                shorts += 1

        if longs > shorts:
            delta = LONG_MOVE
        elif shorts > longs:
            delta = SHORT_MOVE
        else:
            delta = 0

        new_price = max(FLOOR, lr_prices[-1] + delta)
        realised = new_price - lr_prices[-1]
        lr_pnl += my * realised

        lr_prices.append(new_price)
        lr_moves.append(realised)
        for o, a in zip(room, opp_actions):
            o.observe(lr_prices, lr_moves, a)

        # --- P&L on the generated instruments, marked to market ---
        if day:
            for k in LIMITS:
                if k == "Liferaft Ticket":
                    continue
                price_pnl += prev[k] * (price_data[k][day] - price_data[k][day - 1])

        prev = pos

    return price_pnl, lr_pnl, {
        "breaches": breaches,
        "lr_days_traded": lr_days_traded,
        "lr_days_long": lr_days_long,
        "lr_final_price": lr_prices[-1],
    }


def main(n_rooms=400, seed=20260809):
    data = load_round1()
    master = np.random.default_rng(seed)

    totals, price_parts, lr_parts, diags = [], [], [], []
    for i in range(n_rooms):
        rng = np.random.default_rng(master.integers(0, 2**63 - 1))
        room = random_room(rng)
        p, l, d = run_year(data, room, rng)
        totals.append(p + l)
        price_parts.append(p)
        lr_parts.append(l)
        d["room_size"] = len(room)
        diags.append(d)
        if (i + 1) % 50 == 0:
            print(f"  ...{i + 1}/{n_rooms} rooms", flush=True)

    np.save(os.path.join(HERE, "scenarioA_totals.npy"), np.array(totals))
    np.save(os.path.join(HERE, "scenarioA_liferaft.npy"), np.array(lr_parts))
    np.save(os.path.join(HERE, "scenarioA_price.npy"), np.array(price_parts))

    t = np.array(totals)
    l = np.array(lr_parts)
    p = np.array(price_parts)
    q = lambda a, x: float(np.percentile(a, x))

    print("\n" + "=" * 74)
    print(f"SCENARIO A -- Liferaft room risk ({n_rooms} random held-out rooms)")
    print("Round 1 price paths fixed; only the competition varies")
    print("=" * 74)
    print(f"{'':<22}{'TOTAL':>16}{'price book':>16}{'liferaft':>16}")
    for label, fn in [("best (max)", lambda a: float(a.max())),
                      ("p95", lambda a: q(a, 95)),
                      ("p75", lambda a: q(a, 75)),
                      ("median", lambda a: q(a, 50)),
                      ("mean", lambda a: float(a.mean())),
                      ("p25", lambda a: q(a, 25)),
                      ("p05", lambda a: q(a, 5)),
                      ("worst (min)", lambda a: float(a.min()))]:
        print(f"{label:<22}{fn(t):>16,.0f}{fn(p):>16,.0f}{fn(l):>16,.0f}")
    print(f"\nP(total < 0)          {float((t < 0).mean()):.3f}")
    print(f"P(liferaft < 0)       {float((l < 0).mean()):.3f}")
    print(f"P(total < price-only) {float((t < p).mean()):.3f}")
    print(f"budget breaches       {sum(d['breaches'] for d in diags)}")
    print(f"liferaft days traded  median {np.median([d['lr_days_traded'] for d in diags]):.0f} / 365")
    return t, p, l


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    main(n)
