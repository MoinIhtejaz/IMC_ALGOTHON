"""
Budget and position-validity test suite.

The grader's contract, read off simulation.py:

    breach      sum(abs(position * decision_time_price)) > 600000
    penalty     every position in the book set to zero for that day
    type check  type(position) != type(1)  ->  that position zeroed
    limit check abs(position) > positionLimits[i]  ->  that position zeroed

A breach costs the whole day, not just the offending line, so "probably under"
is not good enough. These tests check the invariant on every day of real data
and then on adversarial price paths that Round 1 never produces.

Run:  python3 test_budget.py
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TI = os.path.abspath(os.path.join(HERE, "..", "..", "trader_interface"))
sys.path.insert(0, TI)

os.environ.setdefault("MPLBACKEND", "Agg")

from algorithm import (BUDGET_PRIORITY, BUDGET_RESERVE, TOTAL_BUDGET,  # noqa: E402
                       Algorithm)

FAILS = []


def check(label, cond, detail=""):
    if not cond:
        FAILS.append(label)
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))


def book_value(positions, data):
    """Exactly the grader's formula."""
    return sum(abs(positions[i] * data[i][-1]) for i in positions if i in data and data[i])


def validate(positions, data, limits, label):
    """Every contract the grader enforces, checked at once."""
    ok_type = all(type(v) is int for v in positions.values())
    ok_limit = all(abs(v) <= limits[i] for i, v in positions.items())
    total = book_value(positions, data)
    ok_budget = total <= TOTAL_BUDGET
    return ok_type, ok_limit, ok_budget, total


LIMITS = {
    "Fintech Token": 100, "UQ Dollar": 650, "Thrifted Jeans": 800,
    "Sausage Sizzle": 3000, "Bread": 500, "MenuDash": 75000,
    "Sausage": 5000, "Liferaft Ticket": 1, "Boat Party Ticket": 1000,
}

# ---------------------------------------------------------------- real data
print("1. Every day of the Round 1 backtest")

import simulation as sim  # noqa: E402

# the engine resolves its data folder relative to the working directory
engine = sim.TradingEngine(dataFolder=os.path.join(TI, "data") + os.sep)
algo = Algorithm(engine.positions)

worst_util = 0.0
worst_day = -1
breaches = 0
bad_type = 0
bad_limit = 0
utils = []

for day in range(engine.totalDays):
    hist = {ins: pd["Price"][:day + 1].tolist() for ins, pd in engine.data.items()}
    algo.day = day
    algo.data = hist
    algo.positions = engine.positions
    algo.positionLimits = engine.positionLimits
    pos = algo.get_positions()

    t, l, b, total = validate(pos, hist, engine.positionLimits, f"day {day}")
    if not t:
        bad_type += 1
    if not l:
        bad_limit += 1
    if not b:
        breaches += 1
    utils.append(total)
    if total > worst_util:
        worst_util, worst_day = total, day

check("no budget breach on any of 365 days", breaches == 0, f"{breaches} breaches")
check("all positions are builtin int", bad_type == 0, f"{bad_type} days with wrong type")
check("all positions within limits", bad_limit == 0, f"{bad_limit} days over limit")
check("peak utilisation stays under cap", worst_util <= TOTAL_BUDGET,
      f"peak ${worst_util:,.2f} on day {worst_day} "
      f"({100 * worst_util / TOTAL_BUDGET:.2f}% of cap)")
print(f"       mean utilisation ${np.mean(utils):,.0f} "
      f"({100 * np.mean(utils) / TOTAL_BUDGET:.1f}%), "
      f"headroom at peak ${TOTAL_BUDGET - worst_util:,.2f}")

# ------------------------------------------------------- adversarial prices
print("\n2. Adversarial price paths Round 1 never produces")


def synth(price_map, day=120, hist_len=200):
    """Build a fake history where each instrument sits at a chosen price."""
    data = {}
    for ins, p in price_map.items():
        data[ins] = [float(p)] * hist_len
    a = Algorithm({})
    a.day = day
    a.data = data
    a.positionLimits = dict(LIMITS)
    a.positions = {i: 0 for i in LIMITS}
    return a


scenarios = {
    "all instruments 10x normal": {
        "Fintech Token": 1500, "UQ Dollar": 1000, "Thrifted Jeans": 500,
        "Sausage Sizzle": 100, "Bread": 60, "MenuDash": 30,
        "Sausage": 40, "Liferaft Ticket": 100000, "Boat Party Ticket": 450},
    "all instruments 100x normal": {
        "Fintech Token": 15000, "UQ Dollar": 10000, "Thrifted Jeans": 5000,
        "Sausage Sizzle": 1000, "Bread": 600, "MenuDash": 300,
        "Sausage": 400, "Liferaft Ticket": 100000, "Boat Party Ticket": 4500},
    "everything near zero": {i: 0.01 for i in LIMITS},
    "one instrument enormous": {
        "Fintech Token": 150, "UQ Dollar": 100, "Thrifted Jeans": 50,
        "Sausage Sizzle": 10, "Bread": 6, "MenuDash": 3,
        "Sausage": 4, "Liferaft Ticket": 5_000_000, "Boat Party Ticket": 45},
    "liferaft at the floor": {
        "Fintech Token": 150, "UQ Dollar": 100, "Thrifted Jeans": 50,
        "Sausage Sizzle": 10, "Bread": 6, "MenuDash": 3,
        "Sausage": 4, "Liferaft Ticket": 20000, "Boat Party Ticket": 45},
    "menudash cheap, limit 75000": {
        "Fintech Token": 150, "UQ Dollar": 100, "Thrifted Jeans": 50,
        "Sausage Sizzle": 10, "Bread": 6, "MenuDash": 0.5,
        "Sausage": 4, "Liferaft Ticket": 100000, "Boat Party Ticket": 45},
}

for label, pm in scenarios.items():
    a = synth(pm)
    pos = a.get_positions()
    t, l, b, total = validate(pos, a.data, a.positionLimits, label)
    check(f"{label}", t and l and b,
          f"book ${total:,.2f} ({100 * total / TOTAL_BUDGET:.1f}% of cap)")

# ------------------------------------------- the enforcement pass in isolation
print("\n3. Enforcement pass repairs a deliberately over-budget book")

a = synth({"Fintech Token": 900, "UQ Dollar": 300, "Thrifted Jeans": 400,
           "Sausage Sizzle": 60, "Bread": 40, "MenuDash": 9,
           "Sausage": 30, "Liferaft Ticket": 100000, "Boat Party Ticket": 250})

# hand-build a book that is massively over the cap, bypassing _allocate
overbudget = {i: LIMITS[i] for i in LIMITS}
before = book_value(overbudget, a.data)
assert before > TOTAL_BUDGET, "test setup must actually breach the cap"
repaired = a._enforce_budget(dict(overbudget))
after = book_value(repaired, a.data)
check("over-budget book is brought under the cap",
      after <= TOTAL_BUDGET, f"${before:,.0f} -> ${after:,.0f} "
                             f"(needed to shed ${before - TOTAL_BUDGET:,.0f})")
check("repair sheds low priority first and keeps Liferaft intact",
      repaired["Liferaft Ticket"] == 1
      and repaired["Thrifted Jeans"] < overbudget["Thrifted Jeans"]
      and repaired["Sausage Sizzle"] == overbudget["Sausage Sizzle"],
      f"liferaft {repaired['Liferaft Ticket']}, "
      f"jeans {overbudget['Thrifted Jeans']}->{repaired['Thrifted Jeans']}, "
      f"sizzle {repaired['Sausage Sizzle']}")

# a book that is already fine must be left untouched
fine = {i: 0 for i in LIMITS}
fine["Liferaft Ticket"] = 1
untouched = a._enforce_budget(dict(fine))
check("a compliant book is left unchanged", untouched == fine)

# pathological: single position alone exceeds the cap
huge = {i: 0 for i in LIMITS}
huge["Liferaft Ticket"] = 1
a2 = synth({**{i: 1.0 for i in LIMITS}, "Liferaft Ticket": 5_000_000})
fixed = a2._enforce_budget(dict(huge))
check("a single unaffordable position is zeroed",
      book_value(fixed, a2.data) <= TOTAL_BUDGET,
      f"liferaft {fixed['Liferaft Ticket']}, book ${book_value(fixed, a2.data):,.0f}")

# ---------------------------------------------------------- dynamic behaviour
print("\n4. Dynamic reallocation")

base = {"Fintech Token": 150, "UQ Dollar": 100, "Thrifted Jeans": 50,
        "Sausage Sizzle": 10, "Bread": 6, "MenuDash": 3,
        "Sausage": 4, "Liferaft Ticket": 100000, "Boat Party Ticket": 45}

a_flat = synth(base)
pos_flat = a_flat.get_positions()
spent_when_lr_flat = book_value(pos_flat, a_flat.data)

# force liferaft long and see the rest of the book give way
a_long = synth(base)
orig = a_long._sig_liferaft
a_long._sig_liferaft = lambda: 1.0
pos_long = a_long.get_positions()
spent_when_lr_long = book_value(pos_long, a_long.data)

check("book stays under cap whether Liferaft trades or not",
      spent_when_lr_flat <= TOTAL_BUDGET and spent_when_lr_long <= TOTAL_BUDGET,
      f"flat ${spent_when_lr_flat:,.0f} vs long ${spent_when_lr_long:,.0f}")

# Displacement has to be tested with demand that actually saturates the cap.
# On flat synthetic prices most signals return zero, so the book never reaches
# the limit and there is nothing to displace. Drive _allocate directly instead,
# with every instrument asking for its full limit.
tight = {"Fintech Token": 900, "UQ Dollar": 300, "Thrifted Jeans": 400,
         "Sausage Sizzle": 60, "Bread": 40, "MenuDash": 9,
         "Sausage": 30, "Liferaft Ticket": 100000, "Boat Party Ticket": 250}

demand_all = {i: 1.0 for i in LIMITS}
t = synth(tight)
p_flat = t._allocate({**demand_all, "Liferaft Ticket": 0.0})
p_long = t._allocate({**demand_all, "Liferaft Ticket": 1.0})

low = BUDGET_PRIORITY[1:]          # everything below Liferaft
low_flat = sum(abs(p_flat[i]) * tight[i] for i in low)
low_long = sum(abs(p_long[i]) * tight[i] for i in low)
check("saturating demand fills the cap without breaching",
      book_value(p_flat, t.data) <= TOTAL_BUDGET
      and book_value(p_long, t.data) <= TOTAL_BUDGET
      and book_value(p_flat, t.data) > 0.98 * TOTAL_BUDGET,
      f"flat ${book_value(p_flat, t.data):,.2f}, long ${book_value(p_long, t.data):,.2f}")
check("funding Liferaft displaces lower priority instruments",
      p_long["Liferaft Ticket"] == 1 and low_long < low_flat,
      f"lower-priority notional ${low_flat:,.0f} -> ${low_long:,.0f} "
      f"(displaced ${low_flat - low_long:,.0f} to fund a $100,000 ticket)")
check("displacement comes off the bottom of the priority list",
      abs(p_long["Sausage Sizzle"]) == abs(p_flat["Sausage Sizzle"]),
      f"sizzle held at {p_long['Sausage Sizzle']} through the squeeze")

# rising prices must shrink unit counts, not breach
prev_units = None
print("       price shock sweep (all prices scaled up):")
for mult in [1, 2, 5, 10, 50, 200]:
    a_s = synth({k: v * mult for k, v in base.items()})
    p = a_s.get_positions()
    tot = book_value(p, a_s.data)
    units = sum(abs(v) for v in p.values())
    ok = tot <= TOTAL_BUDGET
    if not ok:
        FAILS.append(f"shock x{mult}")
    print(f"         x{mult:<4} book ${tot:>12,.0f}  total units {units:>7}  "
          f"{'ok' if ok else 'BREACH'}")
    prev_units = units

# ------------------------------------------------------------ malformed input
print("\n5. Malformed signals cannot produce an illegal book")

a_bad = synth(base)
bad_fracs = {"Liferaft Ticket": float("nan"), "Sausage Sizzle": 1e9,
             "Bread": -1e9, "MenuDash": float("inf"), "UQ Dollar": -float("inf"),
             "Sausage": 0.5, "Boat Party Ticket": None}
try:
    pos = a_bad._allocate({k: v for k, v in bad_fracs.items() if v is not None})
    t, l, b, total = validate(pos, a_bad.data, a_bad.positionLimits, "malformed")
    check("NaN / inf / out-of-range fractions still yield a legal book",
          t and l and b, f"book ${total:,.2f}")
except Exception as exc:  # noqa: BLE001
    check("NaN / inf / out-of-range fractions still yield a legal book", False,
          f"raised {type(exc).__name__}: {exc}")

a_empty = synth(base)
a_empty.data = {i: [] for i in LIMITS}
try:
    pos = a_empty.get_positions()
    check("empty price history yields a flat book",
          all(v == 0 for v in pos.values()) and all(type(v) is int for v in pos.values()))
except Exception as exc:  # noqa: BLE001
    check("empty price history yields a flat book", False,
          f"raised {type(exc).__name__}: {exc}")

print()
if FAILS:
    print(f"{len(FAILS)} CHECK(S) FAILED: {FAILS}")
    raise SystemExit(1)
print("All budget and validity checks passed.")
