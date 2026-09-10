"""Engine unit tests against the stated specification. Run before trusting any result."""

import numpy as np

from engine import FLOOR, LONG_MOVE, SHORT_MOVE, START_PRICE, Agent, resolve_day, run
from strategies import AlwaysFlat, AlwaysLong, AlwaysShort, FloorOnly, candidate

FAILS = []


def check(label, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    if not cond:
        FAILS.append(label)
    print(f"  [{status}] {label}" + (f"  {detail}" if detail else ""))


class Fixed(Agent):
    def __init__(self, a):
        self.a = a

    def act(self, prices, moves, day):
        return self.a


def rngf(seed):
    return lambda i: np.random.default_rng(seed * 1000 + i)


print("Majority resolution")
check("majority long falls 5000", resolve_day([1, 1, -1]) == LONG_MOVE)
check("majority short rises 8000", resolve_day([-1, -1, 1]) == SHORT_MOVE)
check("tie leaves price unchanged", resolve_day([1, -1]) == 0)
check("empty room leaves price unchanged", resolve_day([0, 0, 0]) == 0)
check("flat teams excluded from count", resolve_day([1, 0, 0, 0, 0, -1, -1]) == SHORT_MOVE,
      "2 short beats 1 long despite 4 abstainers")

print("\nFloor behaviour")
r = run(Fixed(1), [Fixed(1)] * 4, 40, rngf(1))
check("price never breaches floor", min(r.prices) >= FLOOR, f"min={min(r.prices)}")
check("price pins at floor", r.prices[-1] == FLOOR)
n_steps = (START_PRICE - FLOOR) // 5000
check("floor reached in exactly 16 steps", r.prices[n_steps] == FLOOR, f"n={n_steps}")
check("long riding to floor loses 80,000", r.pnl == -(START_PRICE - FLOOR), f"pnl={r.pnl}")

print("\nFloor payoff asymmetry")
r_long = run(Fixed(1), [Fixed(1)] * 4, 40, rngf(2))
tail = [r_long.prices[i + 1] - r_long.prices[i] for i in range(20, 39)]
check("at floor, majority long realises 0", all(t == 0 for t in tail))
r_short = run(Fixed(1), [Fixed(-1)] * 4, 3, rngf(3))
check("at normal price, majority short pays long 8000",
      r_short.pnl == 3 * SHORT_MOVE, f"pnl={r_short.pnl}")

# a long sitting at the floor when the room flips short
class FloorThenShort(Agent):
    def act(self, prices, moves, day):
        return 1 if day < 20 else -1

r_mix = run(FloorOnly(), [FloorThenShort() for _ in range(5)], 40, rngf(4))
check("floor-only strategy never loses money", r_mix.pnl >= 0, f"pnl={r_mix.pnl}")

print("\nTiming and determinism")
class Peeker(Agent):
    def __init__(self):
        self.seen = []

    def act(self, prices, moves, day):
        self.seen.append(len(prices))
        return 0

p = Peeker()
run(p, [Fixed(1)] * 3, 10, rngf(5))
check("agent sees exactly day+1 prices (no lookahead)",
      p.seen == list(range(1, 11)), f"{p.seen[:3]}...")

a = run(candidate(), [Fixed(1), Fixed(-1), Fixed(1)], 365, rngf(6))
b = run(candidate(), [Fixed(1), Fixed(-1), Fixed(1)], 365, rngf(6))
check("identical re-run gives identical P&L", a.pnl == b.pnl, f"{a.pnl} vs {b.pnl}")

print("\nP&L accounting")
class Osc(Agent):
    def act(self, prices, moves, day):
        return 1 if day % 2 == 0 else -1

r_osc = run(AlwaysLong(), [Osc() for _ in range(3)], 364, rngf(7))
# room alternates long/short; a long earns -5000 then +8000 = +3000 per 2 days,
# i.e. the 1500/day quoted in the research log
check("always-long nets 3000 per 2-day cycle in an oscillating room",
      r_osc.pnl == 182 * 3000, f"pnl={r_osc.pnl} expected={182*3000}")

r_flat = run(AlwaysFlat(), [Fixed(1)] * 5, 365, rngf(8))
check("flat strategy earns exactly zero", r_flat.pnl == 0)
check("flat strategy uses zero notional", r_flat.max_notional == 0)

print("\nOur own vote cannot break the floor property")
# our single long can turn a majority-short day into a tie, never into a fall
check("one vote cannot create a majority-long from a majority-short",
      resolve_day([1] + [-1]) == 0 and resolve_day([1] + [-1, -1]) == SHORT_MOVE)

print("\nBudget")
r_b = run(AlwaysLong(), [Fixed(-1)] * 3, 5, rngf(9))
check("notional measured at decision-time price",
      r_b.max_notional == START_PRICE + 4 * SHORT_MOVE,
      f"max_notional={r_b.max_notional}")
check("single ticket always within 600k cap", r_b.max_notional <= 600_000)

print("\nAction legality")
class Bad(Agent):
    def act(self, prices, moves, day):
        return 2

try:
    run(Bad(), [Fixed(1)], 3, rngf(10))
    check("illegal action rejected", False)
except ValueError:
    check("illegal action rejected", True)

print()
if FAILS:
    print(f"{len(FAILS)} CHECK(S) FAILED: {FAILS}")
    raise SystemExit(1)
print("All engine checks passed.")
