"""
Liferaft Ticket - independent engine reimplementation.

Written from the instrument specification rules only, deliberately NOT ported
from the original research code, so that engine bugs cannot be shared between
the strategy's development environment and its test environment.

Rules implemented (AlgoJam3 Instrument Specification p.10):
    start price   $100,000
    floor         $20,000 (price cannot fall below)
    position      -1, 0 or +1 (integer, indivisible)
    majority      computed ONLY over teams taking a side; flat teams excluded
    majority long  -> price falls $5,000
    majority short -> price rises $8,000
    tie / no votes -> price unchanged
    P&L           position * (newPrice - oldPrice), marked to market

Simultaneity: every agent sees prices[0..d] and returns its action before any
action is resolved.

Note on `moves`: moves[i] = prices[i+1] - prices[i] is the realised daily move,
which is also exactly the P&L of one long ticket held that day. It is maintained
incrementally and handed to agents so nobody has to rescan history each day.
"""

from __future__ import annotations

from dataclasses import dataclass, field

START_PRICE = 100_000
FLOOR = 20_000
LONG_MOVE = -5_000   # majority long -> price falls
SHORT_MOVE = +8_000  # majority short -> price rises


class Agent:
    """Base agent. Subclasses implement act()."""

    name = "agent"

    def reset(self, rng):
        """Called once at the start of a run. rng is a seeded numpy Generator."""
        self.rng = rng

    def act(self, prices: list[int], moves: list[int], day: int) -> int:
        """Return -1, 0 or +1 having seen prices[0..day] only."""
        raise NotImplementedError

    def observe(self, prices, moves, my_action: int) -> None:
        """Called after the day resolves, with the new price and move appended."""
        return None


@dataclass
class RunResult:
    pnl: int
    prices: list[int]
    actions: list[int]
    days_traded: int
    days_long: int
    days_short: int
    max_notional: int
    floor_days: int


def resolve_day(actions) -> int:
    """Given every agent's action, return the price delta before flooring."""
    longs = 0
    shorts = 0
    for a in actions:
        if a > 0:
            longs += 1
        elif a < 0:
            shorts += 1
    if longs > shorts:
        return LONG_MOVE
    if shorts > longs:
        return SHORT_MOVE
    return 0


def run(us: Agent, opponents: list[Agent], days: int, rng_factory) -> RunResult:
    """
    Run one year. `us` is scored; opponents move the price but are not scored.
    rng_factory(i) returns an independent seeded Generator for agent i.
    """
    us.reset(rng_factory(0))
    for i, opp in enumerate(opponents):
        opp.reset(rng_factory(i + 1))

    prices = [START_PRICE]
    moves: list[int] = []
    actions: list[int] = []
    pnl = 0
    max_notional = 0
    floor_days = 0

    for day in range(days):
        price = prices[-1]

        # --- simultaneous decision phase: nobody sees anyone else's action ---
        my_action = int(us.act(prices, moves, day))
        if my_action not in (-1, 0, 1):
            raise ValueError(f"illegal action {my_action!r} on day {day}")
        opp_actions = [o.act(prices, moves, day) for o in opponents]

        # budget is checked at the decision-time price
        if my_action:
            if price > max_notional:
                max_notional = price
        if price <= FLOOR:
            floor_days += 1

        # --- resolution phase ---
        longs = 1 if my_action > 0 else 0
        shorts = 1 if my_action < 0 else 0
        for a in opp_actions:
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

        new_price = price + delta
        if new_price < FLOOR:
            new_price = FLOOR
        realised = new_price - price
        pnl += my_action * realised

        prices.append(new_price)
        moves.append(realised)
        actions.append(my_action)

        us.observe(prices, moves, my_action)
        for o, a in zip(opponents, opp_actions):
            o.observe(prices, moves, a)

    return RunResult(
        pnl=pnl,
        prices=prices,
        actions=actions,
        days_traded=sum(1 for a in actions if a != 0),
        days_long=sum(1 for a in actions if a > 0),
        days_short=sum(1 for a in actions if a < 0),
        max_notional=max_notional,
        floor_days=floor_days,
    )
