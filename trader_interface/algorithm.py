"""
AlgoJam 3 — trading algorithm.

Each instrument gets a model chosen from its stated behaviour in the
Instrument Specification, validated on Round 1 data:

  UQ Dollar        pegged at $100      -> revert to the peg
  Sausage Sizzle   cost = bread + sausage + labour, priced off *yesterday's*
                   shopping -> tomorrow's price is largely known today
  MenuDash         noisy read of the same labour cost -> revert to the fair
                   value implied by the sizzle
  Fintech Token    flat stretches punctuated by jumps -> short-horizon reversion
  Boat Party       semester seasonality + sharp overreaction -> reversion plus a
                   day-of-year seasonal tilt fitted on Round 1
  Bread / Sausage  slow climb, noisy week to week -> medium-horizon momentum
  Thrifted Jeans   steady upward drift -> long
  Liferaft Ticket  no price history, payoff decided by the room -> adaptive
                   contrarian with a long tilt for the +8k/-5k asymmetry

Positions are then packed into the $600k daily budget in order of historical
profit per dollar of budget consumed.
"""

import numpy as np


# ----------------------------------------------------------------------------
# Constants fitted on Round 1
# ----------------------------------------------------------------------------

# Sausage Sizzle recipe: sizzle[t] = A*bread[t-1] + B*sausage[t-1] + labour[t-1]
PRIOR_A = 0.07692
PRIOR_B = 1.76921

# Boat Party Ticket: smoothed Round 1 day-of-year shape. Only the sign of its
# day-to-day slope is used, since the spec says the calendar repeats but the
# height of each peak does not.
BOAT_SEASONAL = [
    44.97, 44.97, 44.98, 45.02, 45.09, 45.21, 45.36, 45.54, 45.75, 46.00,
    46.29, 46.64, 47.01, 47.38, 47.76, 48.16, 48.58, 49.02, 49.44, 49.82,
    50.15, 50.47, 50.75, 51.01, 51.24, 51.43, 51.59, 51.75, 51.91, 52.09,
    52.25, 52.42, 52.59, 52.75, 52.90, 53.07, 53.24, 53.41, 53.57, 53.72,
    53.86, 54.00, 54.11, 54.22, 54.30, 54.35, 54.36, 54.35, 54.32, 54.28,
    54.21, 54.12, 53.98, 53.81, 53.63, 53.42, 53.20, 52.94, 52.66, 52.35,
    52.02, 51.69, 51.36, 51.02, 50.67, 50.32, 49.97, 49.65, 49.35, 49.08,
    48.82, 48.58, 48.35, 48.13, 47.93, 47.73, 47.54, 47.34, 47.15, 46.95,
    46.76, 46.58, 46.40, 46.24, 46.07, 45.91, 45.75, 45.58, 45.44, 45.31,
    45.20, 45.11, 45.03, 44.97, 44.95, 44.96, 45.01, 45.08, 45.17, 45.28,
    45.40, 45.56, 45.77, 45.98, 46.21, 46.45, 46.71, 46.99, 47.28, 47.54,
    47.75, 47.93, 48.07, 48.19, 48.26, 48.29, 48.24, 48.13, 48.01, 47.85,
    47.67, 47.46, 47.20, 46.90, 46.61, 46.31, 46.02, 45.73, 45.43, 45.12,
    44.84, 44.59, 44.37, 44.13, 43.92, 43.72, 43.55, 43.43, 43.36, 43.33,
    43.31, 43.33, 43.39, 43.46, 43.52, 43.57, 43.58, 43.56, 43.52, 43.44,
    43.31, 43.14, 42.94, 42.73, 42.49, 42.24, 41.97, 41.69, 41.45, 41.24,
    41.07, 40.96, 40.91, 40.91, 40.98, 41.12, 41.31, 41.52, 41.77, 42.04,
    42.33, 42.68, 43.08, 43.51, 43.98, 44.49, 45.02, 45.59, 46.19, 46.84,
    47.47, 48.10, 48.74, 49.36, 49.97, 50.59, 51.17, 51.68, 52.14, 52.55,
    52.91, 53.22, 53.47, 53.63, 53.71, 53.74, 53.75, 53.71, 53.64, 53.52,
    53.35, 53.14, 52.91, 52.66, 52.39, 52.10, 51.78, 51.44, 51.10, 50.77,
    50.44, 50.12, 49.79, 49.47, 49.17, 48.91, 48.67, 48.44, 48.23, 48.03,
    47.84, 47.67, 47.51, 47.36, 47.21, 47.05, 46.89, 46.75, 46.62, 46.52,
    46.43, 46.36, 46.30, 46.25, 46.26, 46.31, 46.41, 46.54, 46.70, 46.90,
    47.13, 47.41, 47.70, 47.99, 48.27, 48.53, 48.78, 49.02, 49.23, 49.39,
    49.49, 49.55, 49.57, 49.55, 49.49, 49.35, 49.16, 48.94, 48.70, 48.42,
    48.13, 47.81, 47.46, 47.10, 46.74, 46.38, 46.01, 45.64, 45.30, 44.95,
    44.64, 44.37, 44.11, 43.88, 43.67, 43.49, 43.35, 43.24, 43.18, 43.15,
    43.16, 43.21, 43.29, 43.35, 43.41, 43.44, 43.44, 43.41, 43.34, 43.23,
    43.08, 42.88, 42.67, 42.44, 42.20, 41.94, 41.67, 41.41, 41.18, 40.99,
    40.85, 40.77, 40.74, 40.77, 40.86, 41.03, 41.24, 41.48, 41.73, 42.01,
    42.30, 42.61, 42.93, 43.22, 43.50, 43.76, 43.99, 44.20, 44.40, 44.55,
    44.67, 44.77, 44.86, 44.92, 44.97, 44.99, 44.99, 44.99, 44.98, 44.98,
    44.98, 44.99, 45.00, 45.02, 45.04, 45.07, 45.08, 45.10, 45.12, 45.13,
    45.15, 45.16, 45.16, 45.15, 45.15, 45.15, 45.15, 45.14, 45.14, 45.13,
    45.12, 45.12, 45.11, 45.10, 45.09, 45.08, 45.07, 45.06, 45.04, 45.04,
    45.01, 45.01, 45.01, 45.01, 45.00,
]

# Order in which instruments claim the $600k daily budget: historical Round 1
# profit divided by the budget the position consumes. Liferaft is first because
# its per-day payoff (+8000 / -5000 on a $100k position) dominates everything
# else on the board.
BUDGET_PRIORITY = [
    "Liferaft Ticket",
    "Boat Party Ticket",
    "Fintech Token",
    "UQ Dollar",
    "MenuDash",
    "Sausage Sizzle",
    "Thrifted Jeans",
    "Sausage",
    "Bread",
]

TOTAL_BUDGET = 600000
BUDGET_SAFETY = 0.97      # leave headroom so integer rounding can never tip us over

LIFERAFT_FLOOR = 20000
LIFERAFT_UP = 8000        # price move when the majority is short
LIFERAFT_DOWN = 5000      # price move when the majority is long
# Long beats short whenever P(majority long) < 8000/13000
LIFERAFT_BREAKEVEN = LIFERAFT_UP / float(LIFERAFT_UP + LIFERAFT_DOWN)


def _mean(seq):
    return sum(seq) / float(len(seq))


class Algorithm():

    def __init__(self, positions):
        self.data = {}
        self.positionLimits = {}
        self.day = 0
        self.positions = positions
        self._recipe = (PRIOR_A, PRIOR_B)

    def get_current_price(self, instrument):
        return self.data[instrument][-1]

    # ------------------------------------------------------------------
    # Sausage Sizzle cost model
    # ------------------------------------------------------------------

    def _fit_recipe(self):
        """Re-fit the bread/sausage coefficients from Round 2 data once there is
        enough of it. The implied labour cost moves slowly, so the right
        coefficients are the ones that make it smoothest."""
        sz = self.data["Sausage Sizzle"]
        br = self.data["Bread"]
        sa = self.data["Sausage"]
        n = len(sz)
        if n < 90 or self.day % 30 != 0:
            return
        a0, b0 = PRIOR_A, PRIOR_B
        best = None
        for a in [a0 * (1 + i * 0.05) for i in range(-8, 9)]:
            for b in [b0 * (1 + i * 0.05) for i in range(-8, 9)]:
                lab = [sz[t] - a * br[t - 1] - b * sa[t - 1] for t in range(1, n)]
                rough = _mean([abs(lab[i] - lab[i - 1]) for i in range(1, len(lab))])
                if best is None or rough < best[0]:
                    best = (rough, a, b)
        # blend toward the Round 1 prior so a noisy fit cannot run away
        w = min(1.0, (n - 90) / 180.0) * 0.6
        self._recipe = (
            (1 - w) * PRIOR_A + w * best[1],
            (1 - w) * PRIOR_B + w * best[2],
        )

    def _labour_series(self):
        """labour[i] is the labour cost on day i; it is only revealed by the
        sizzle price printed on day i+1, so this list is one day shorter than
        the price history."""
        a, b = self._recipe
        sz = self.data["Sausage Sizzle"]
        br = self.data["Bread"]
        sa = self.data["Sausage"]
        return [sz[t] - a * br[t - 1] - b * sa[t - 1] for t in range(1, len(sz))]

    # ------------------------------------------------------------------
    # Per-instrument signals, each returning a target fraction in [-1, 1]
    # ------------------------------------------------------------------

    def _sig_uq_dollar(self):
        # Pegged at $100 and reliably pulled back in both directions. A small
        # deadband skips the coin-flip days and frees that budget for others.
        dev = self.data["UQ Dollar"][-1] - 100.0
        if abs(dev) < 0.15:
            return 0.0
        return -1.0 if dev > 0 else 1.0

    def _sig_sausage_sizzle(self, labour):
        # Tomorrow's sizzle is priced off today's bread and sausage, which are
        # already printed. Only the labour drift is unknown, so estimate it from
        # the recent slope of the implied labour cost.
        drift_window = 10
        if self.day < 15 or len(labour) < drift_window + 2:
            return 0.0
        a, b = self._recipe
        br = self.data["Bread"]
        sa = self.data["Sausage"]
        known = a * (br[-1] - br[-2]) + b * (sa[-1] - sa[-2])
        drift = (labour[-1] - labour[-1 - drift_window]) / float(drift_window)
        pred = known + drift
        if abs(pred) < 1e-9:
            return 0.0
        return 1.0 if pred > 0 else -1.0

    def _sig_menudash(self, labour):
        # MenuDash is a rounded, surged read of the labour cost that the sizzle
        # reveals exactly. Trade the gap between the two.
        md = self.data["MenuDash"]
        if self.day < 50 or len(labour) < 40:
            return 0.0
        window = min(60, len(labour) - 1)
        xs = labour[-window - 1:-1]
        ys = md[len(md) - 1 - window:len(md) - 1]
        n = len(xs)
        mx, my = _mean(xs), _mean(ys)
        var = sum((x - mx) ** 2 for x in xs)
        if var <= 0:
            return 0.0
        slope = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / var
        fair = my + slope * (labour[-1] - mx)
        gap = fair - md[-1]
        if abs(gap) < 1e-9:
            return 0.0
        return 1.0 if gap > 0 else -1.0

    def _sig_fintech_token(self):
        # Long flat stretches and abrupt repricings both mean-revert on a
        # one-week horizon. Average three windows rather than picking one.
        p = self.data["Fintech Token"]
        if self.day < 12:
            return 0.0
        score = 0.0
        for w in (5, 7, 10):
            score += _mean(p[-w:]) - p[-1]
        if abs(score) < 1e-9:
            return 0.0
        return 1.0 if score > 0 else -1.0

    def _sig_boat_party(self):
        # Resale prices overshoot day to day, on top of a semester shape that
        # repeats on the same calendar each year.
        p = self.data["Boat Party Ticket"]
        if self.day < 5:
            return 0.0
        reversion = _mean(p[-3:]) - p[-1]
        d = self.day
        seasonal = 0.0
        if 0 < d < len(BOAT_SEASONAL) - 1:
            seasonal = (BOAT_SEASONAL[d + 1] - BOAT_SEASONAL[d - 1]) / 2.0
        score = reversion + 0.5 * seasonal
        if abs(score) < 1e-9:
            return 0.0
        return 1.0 if score > 0 else -1.0

    def _sig_momentum(self, instrument, window):
        # Bread and Sausage climb slowly with unpredictable weekly jumps; the
        # climb is the only tradeable part.
        p = self.data[instrument]
        if self.day < window + 2:
            return 0.0
        score = p[-1] - _mean(p[-window:])
        if abs(score) < 1e-9:
            return 0.0
        return 1.0 if score > 0 else -1.0

    def _sig_thrifted_jeans(self):
        # A drifting random walk. One year of Round 1 data cannot prove the
        # drift is real, so hold a partial long rather than the full limit.
        if self.day < 5:
            return 0.0
        return 0.6

    def _sig_liferaft(self):
        # The crowd that piles onto either vessel is the side that loses.
        # A price drop of 5000 means the majority was long yesterday; a rise of
        # 8000 means it was short. Bet against whichever way the room has been
        # leaning, with a long tilt because +8000 beats -5000.
        p = self.data.get("Liferaft Ticket")
        if not p:
            return 1.0

        votes = []
        for t in range(1, len(p)):
            move = p[t] - p[t - 1]
            if move < -1e-9:
                votes.append(1.0)       # majority went long
            elif move > 1e-9:
                votes.append(0.0)       # majority went short
            # unchanged: a tie or an empty room, no information

        # At the floor the price can only hold or rise, so long is free.
        if p[-1] <= LIFERAFT_FLOOR + LIFERAFT_DOWN:
            return 1.0

        if not votes:
            return 1.0                  # no reads yet; the asymmetry favours long

        recent = votes[-10:]
        # Shrink toward an even room so a short streak cannot flip us on its own.
        q = (sum(recent) + 2.0) / (len(recent) + 4.0)
        long_edge = LIFERAFT_UP - (LIFERAFT_UP + LIFERAFT_DOWN) * q
        return 1.0 if long_edge >= 0 else -1.0

    # ------------------------------------------------------------------
    # Budget packing
    # ------------------------------------------------------------------

    def _allocate(self, fractions):
        """Convert target fractions into integer positions that respect both the
        per-instrument limits and the total daily budget."""
        cap = TOTAL_BUDGET * BUDGET_SAFETY
        positions = {ins: 0 for ins in self.positionLimits}
        spent = 0.0

        for ins in BUDGET_PRIORITY:
            if ins not in self.positionLimits or ins not in self.data:
                continue
            limit = self.positionLimits[ins]
            price = self.data[ins][-1]
            frac = max(-1.0, min(1.0, fractions.get(ins, 0.0)))
            want = int(round(frac * limit))
            if want == 0 or price <= 0:
                continue

            affordable = int((cap - spent) / price)
            size = min(abs(want), affordable, limit)
            if size <= 0:
                continue
            positions[ins] = size if want > 0 else -size
            spent += size * price

        # Anything not named in the priority list still gets whatever is left.
        for ins in self.positionLimits:
            if ins in BUDGET_PRIORITY or ins not in self.data:
                continue
            limit = self.positionLimits[ins]
            price = self.data[ins][-1]
            want = int(round(max(-1.0, min(1.0, fractions.get(ins, 0.0))) * limit))
            if want == 0 or price <= 0:
                continue
            size = min(abs(want), int((cap - spent) / price), limit)
            if size > 0:
                positions[ins] = size if want > 0 else -size
                spent += size * price

        return positions

    # ------------------------------------------------------------------

    def get_positions(self):
        self._fit_recipe()
        labour = self._labour_series() if len(self.data.get("Sausage Sizzle", [])) > 1 else []

        fractions = {
            "UQ Dollar": self._sig_uq_dollar(),
            "Sausage Sizzle": self._sig_sausage_sizzle(labour),
            "MenuDash": self._sig_menudash(labour),
            "Fintech Token": self._sig_fintech_token(),
            "Boat Party Ticket": self._sig_boat_party(),
            "Bread": self._sig_momentum("Bread", 10),
            "Sausage": self._sig_momentum("Sausage", 10),
            "Thrifted Jeans": self._sig_thrifted_jeans(),
            "Liferaft Ticket": self._sig_liferaft(),
        }

        return self._allocate(fractions)
