"""
Three Liferaft rules, wrapped so the full Algorithm can be run with any of them.

  base      the original shipped rule: constant k = 2.0, no risk management,
            always long at the floor
  dd        adaptive haircut driven by peak-to-trough drawdown on the Liferaft
            (k = 2 + 4*dd/100k, capped at 12)
  user      floor exit after 15 dead days + adaptive haircut driven by trailing
            60-day realised P&L (k = 2 + 1.0*loss/25k)

Everything outside _sig_liferaft is identical in all three, so any difference in
the whole-portfolio result is attributable to the Liferaft rule alone (plus the
budget it does or does not consume).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from algorithm import (Algorithm, LIFERAFT_FLOOR, LIFERAFT_MIN_N,  # noqa: E402
                       LIFERAFT_K, _liferaft_regime)

# ---- user's constants, verbatim -------------------------------------------
LIFERAFT_MAX_DEAD_FLOOR = 15
LIFERAFT_ADAPT = 1.0
LIFERAFT_ADAPT_WINDOW = 60
LIFERAFT_ADAPT_SCALE = 25000.0
LIFERAFT_ADAPT_MIN_DAYS = 30


class BaseVariant(Algorithm):
    """Original rule: constant haircut, no risk management."""

    def _liferaft_k(self):
        return LIFERAFT_K


class DrawdownVariant(Algorithm):
    """Currently shipped: haircut widens with drawdown. Inherited as-is."""
    pass


class UserVariant(Algorithm):
    """Floor exit + trailing-realised-P&L haircut."""

    def _sig_liferaft(self):
        if not hasattr(self, "_lr_actions"):
            self._lr_actions = []
        # Round 2 restarts the clock; without this the action log from a
        # previous year would poison the trailing window.
        if self.day == 0:
            self._lr_actions = []

        prices = self.data.get("Liferaft Ticket")
        if not prices:
            self._lr_actions.append(0)
            return 0.0
        action = self._liferaft_decide(prices)
        self._lr_actions.append(int(action))
        return float(action)

    def _liferaft_decide(self, prices):
        acts = self._lr_actions
        settled = min(len(acts), len(prices) - 1)
        recent = 0.0
        for i in range(max(0, settled - LIFERAFT_ADAPT_WINDOW), settled):
            recent += acts[i] * (prices[i + 1] - prices[i])

        if prices[-1] <= LIFERAFT_FLOOR:
            if LIFERAFT_MAX_DEAD_FLOOR:
                dead, t = 0, len(prices) - 1
                while t >= 1 and prices[t] <= LIFERAFT_FLOOR and prices[t] == prices[t - 1]:
                    dead += 1
                    t -= 1
                if dead >= LIFERAFT_MAX_DEAD_FLOOR:
                    return 0
            return 1

        moves = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
        if len(moves) < 2:
            return 0

        current = _liferaft_regime(moves[-1])
        n = 0
        total = 0.0
        total_sq = 0.0
        for t in range(1, len(moves)):
            if _liferaft_regime(moves[t - 1]) == current:
                x = float(moves[t])
                n += 1
                total += x
                total_sq += x * x
        if n < LIFERAFT_MIN_N:
            return 0

        mean = total / n
        var = (total_sq - n * mean * mean) / (n - 1)
        if var < 0.0:
            var = 0.0
        se = (var / n) ** 0.5

        k = LIFERAFT_K
        if settled >= LIFERAFT_ADAPT_MIN_DAYS and recent < 0.0:
            k += LIFERAFT_ADAPT * (-recent / LIFERAFT_ADAPT_SCALE)

        if mean - k * se > 0:
            return 1
        if -mean - k * se > 0:
            return -1
        return 0


class UserPlusDrawdown(Algorithm):
    """Both risk controls at once: the user's floor exit and trailing window,
    layered on the drawdown haircut. Takes the wider of the two haircuts."""

    def _sig_liferaft(self):
        if not hasattr(self, "_lr_actions"):
            self._lr_actions = []
        if self.day == 0:
            self._lr_actions = []
        prices = self.data.get("Liferaft Ticket")
        if not prices:
            self._lr_actions.append(0)
            return 0.0
        a = UserVariant._liferaft_decide(self, prices)
        self._lr_actions.append(int(a))
        return float(a)

    def _liferaft_decide(self, prices):
        # widen by whichever control is more cautious right now
        base_k = Algorithm._liferaft_k(self)
        saved = globals()["LIFERAFT_K"]
        try:
            globals()["LIFERAFT_K"] = base_k
            return UserVariant._liferaft_decide(self, prices)
        finally:
            globals()["LIFERAFT_K"] = saved


VARIANTS = {
    "base": BaseVariant,
    "dd": DrawdownVariant,
    "user": UserVariant,
    "userdd": UserPlusDrawdown,
}
