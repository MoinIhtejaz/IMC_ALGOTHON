"""
AlgoJam 3 — competition submission.

Single-file entry. Defines `Algorithm` with `get_positions()` and imports
nothing at all, so `from algorithm import Algorithm` works on any stock CPython
with no third-party packages present. (requirements.txt lists numpy, pandas and
matplotlib; none of them is needed here, and depending on none of them is
strictly safer than depending on three.)

Each instrument gets a model chosen from its stated behaviour in the
Instrument Specification, validated on Round 1 data:

  UQ Dollar        pegged at $100      -> revert to the peg
  Sausage Sizzle   cost = bread + sausage + labour, priced off *yesterday's*
                   shopping -> tomorrow's price is largely known today
  MenuDash         noisy read of the same labour cost -> revert to the fair
                   value implied by the sizzle
  Fintech Token    flat stretches punctuated by jumps -> short-horizon reversion,
                   with a drift regime that rides sustained repricings
  Boat Party       semester seasonality + sharp overreaction -> reversion plus a
                   day-of-year seasonal tilt fitted on Round 1
  Bread / Sausage  slow climb, noisy week to week -> medium-horizon momentum
  Thrifted Jeans   random walk with drift -> NOT TRADED, switched off entirely.
                   Indistinguishable from its own shuffle, so the budget goes
                   elsewhere
  Liferaft Ticket  no price history, payoff decided by the room -> fade the
                   room's persistent lean, conditioned on the current regime,
                   with a standard-error haircut and abstention by default.
                   Two risk controls on top: exit a dead floor after 15 days,
                   and widen the haircut when our own recent decisions have
                   been losing money (the observable symptom of being crowded)

Positions are then packed into the $600k daily budget in order of signal
reliability. The cap is maintained dynamically: budget is claimed greedily
against the live remaining balance, so capacity a flat or cheap instrument does
not use flows straight to the next one, and a final pass recomputes the book
exactly the way the grader does and trims until it is genuinely under the cap.
"""


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

# Order in which instruments claim the $600k daily budget. Ordered by how
# reliable the signal is, not by Round 1 profit per dollar -- a near-certain
# small gain is worth more than an uncertain large one, and Round 1 P&L per
# dollar is itself an in-sample quantity.
#
# Liferaft is first: its per-day payoff (+8000 / -5000 on a $100k position)
# dominates the board. It is also a lighter claim on the budget than it used to
# be -- the estimator stands down on roughly 40% of days, and every one of those
# hands its ~$100k back to the rest of the book. Sausage Sizzle is second and
# always fully funded -- IC 0.96, by far the most reliable signal here, and the
# previous ordering was starving it (it only cleared $50.2k of the $78.4k
# available).
#
# Thrifted Jeans is last and is not traded at all. It is a random walk with
# drift: ADF cannot reject a unit root (p = 0.49 on log price), Hurst is 0.52 by
# R/S and 0.53 by aggregated variance, every variance ratio has |z| < 0.1, and
# the drift itself is t = 0.76 with one quarter carrying the whole year. There
# is nothing to trade, so its signal is hard-zero and it never claims budget.
BUDGET_PRIORITY = [
    "Liferaft Ticket",
    "Sausage Sizzle",        # IC 0.96 -- fund at full capacity, always
    "Boat Party Ticket",
    "Fintech Token",
    "UQ Dollar",
    "MenuDash",
    "Sausage",
    "Bread",
    "Thrifted Jeans",        # NOT TRADED; kept in the list only for ordering
]

# Switched off entirely. Named here rather than buried in a signal function so
# that the exclusion is visible from one place and enforced in three: the signal
# returns zero, the allocator skips the instrument, and the final clamp zeroes
# it regardless of anything above.
DISABLED_INSTRUMENTS = ("Thrifted Jeans",)

TOTAL_BUDGET = 600000

# The grader's check is `sum(abs(position * price)) > 600000`, evaluated at the
# decision-time price, and a breach zeroes the entire book for that day rather
# than trimming the offending line. So the cost of going one dollar over is the
# whole day's P&L, and the cost of staying under is only the interest on unused
# capacity. That asymmetry justifies a reserve, but not a large one.
#
# A 3% multiplicative safety margin would cost $18,000 of capacity every single
# day. It is replaced by a small absolute reserve. The only error worth guarding
# against is floating point: the grader sums in dict order and we sum in
# priority order, and float addition is not associative, so the two totals can
# disagree in the last few bits. For nine terms of order 1e5 that disagreement
# is around 1e-10 dollars. Ten dollars is roughly eleven orders of magnitude of
# headroom, and costs 0.0017% of the book.
BUDGET_RESERVE = 10.0

# Fintech Token regime switch. The token mean-reverts day to day even while it
# is drifting, so the drift is only visible over a multi-week window: on Round 1
# the variance ratio runs 0.87 at a 2-day horizon and 1.53 at 20 days. Scoring
# the 20-day move as a t-statistic against its own daily noise separates the two
# cases. Entering at 2.0 and holding until it decays to 1.6 puts the book in
# drift mode on 31 of 365 days, which is the intended behaviour: rare, and
# decisive when it fires.
FT_DRIFT_LOOKBACK = 20
FT_DRIFT_ENTER = 2.0
FT_DRIFT_EXIT_FRAC = 0.8

# Boat Party Ticket: how hard the calendar tilts the daily reversion trade.
# Not a hold-from-the-floor rule -- the position limit is already saturated by
# reversion every day, and reversion is worth ~5x the seasonal round trip
# ($101k/yr vs $20k), so any rule that holds through the seasonal move pays for
# it out of the more valuable book. Everything from 0.75 to 3.0 beats 0.5 on
# Round 1; 1.5 is the middle of that plateau and splits its profit evenly across
# both halves of the year.
BOAT_SEASONAL_WEIGHT = 1.5

# UQ Dollar: the peg is reliable enough in both directions that skipping small
# deviations costs more than the budget it frees. A zero deadband is worth
# $64.1k on Round 1 against $56.3k at 0.15, and wins in both halves.
UQ_DOLLAR_DEADBAND = 0.0

LIFERAFT_FLOOR = 20000
LIFERAFT_UP = 8000        # price move when the majority is short
LIFERAFT_DOWN = 5000      # price move when the majority is long
# Long beats short whenever P(majority long) < 8000/13000
LIFERAFT_BREAKEVEN = LIFERAFT_UP / float(LIFERAFT_UP + LIFERAFT_DOWN)

# Liferaft estimator. Settings below are the ones that survived an out-of-sample
# test against 15 opponent archetypes and randomly generated rooms; none of them
# is fitted to Round 1, because Round 1 contains no real Liferaft data to fit to.
#
#   k = 2 standard-error haircut on the edge. The mean is flat across k in
#   [1, 3] (spread under 3%) while P(a losing year) falls from 0.23 at k=0 to
#   0.07 at k=2 and the worst room improves from -$1.1M to -$197k. It is a risk
#   dial, not a fitted parameter. Its real job shows up in a zero-edge room,
#   where it trades 20 days out of 365 against 270 for the undiscounted rule.
#
#   min_n = 5 observations before a bucket is trusted. Inert anywhere from 2 to
#   15; the standard-error term is what actually handles thin samples.
#
# Deliberately absent, both measured on a fresh seed stream and rejected:
#   a warmup period      cost $33k/yr, and duplicates what the k term does
#   scheduled probe days cost $112k/yr for a 4-point change in P(loss)
LIFERAFT_K = 2.0
LIFERAFT_MIN_N = 5

# ---------------------------------------------------------------------------
# Liferaft risk management. Two controls, each earning its place on measured
# whole-portfolio results across 400 paired rooms (identical rooms and opponent
# seeds for every variant, so these are paired differences, not sampling noise).
#
#   variant                        mean         p01       worst
#   no risk control           1,118,833     468,181     231,492
#   drawdown-based haircut    1,111,073     519,935     381,223
#   these two controls        1,119,636     517,531     411,255   <- shipped
#
# The controls are free: the mean is $803 ABOVE the un-patched rule while the
# worst case improves by $179,763. The Liferaft is traded on 174 days a year
# instead of 220, so this abstains more and earns more, which is what a filter
# that removes the right days looks like.
# ---------------------------------------------------------------------------

# Control 1 -- floor exit. Stand down after this many consecutive unchanged days
# sitting at the floor.
#
# The rules are ambiguous about how the floor is marked, and the ambiguity is
# worth real money. Under the reading we assume, P&L is marked on the CLIPPED
# price, so a majority-long day at $20,000 realises exactly $0: those days pay
# nothing and cost nothing. Under the other reading the notional -$5,000 is
# booked before clipping, and a long parked at the floor bleeds $5,000 a day for
# the rest of the year. Round 1's CSV cannot distinguish the two.
#
# Exiting after 15 dead days measures identically under our assumption -- the
# days given up were earning zero anyway -- and caps the damage under the other.
# Over 72 rooms simulated with the pessimistic marking:
#
#   variant                        mean         worst    P(losing year)
#   no floor exit               775,983    -1,126,391        0.208
#   drawdown haircut only       770,286    -1,137,391        0.208
#   with floor exit           1,062,515        +1,790        0.000
#
# Note what that middle row says. An earlier version of this file EXEMPTED the
# floor long from all risk controls, reasoning that at $20,000 it cannot lose.
# That reasoning silently assumes the clipped reading, i.e. it assumes its own
# conclusion. Under the other reading the exemption is exactly the thing that
# lets the position bleed all year, and the risk control guarantees the bleed
# continues. There is no exemption now.
LIFERAFT_MAX_DEAD_FLOOR = 15

# Control 2 -- crowding defence.
#
# If other teams run similar regime-conditioned logic, the copies read the same
# public history, act together, herd onto the same side and all lose. Nothing
# inside this function can see the other teams. It can, however, see whether its
# own past decisions actually made money: the daily move IS the P&L of one long
# ticket, and we know what we held. So mark our own book from the public price
# path and widen the standard-error haircut when recent realised P&L is poor.
# Being repeatedly wrong is the observable symptom of being crowded, whatever
# the underlying cause.
#
# Against 8 other teams running the un-patched rule, whole portfolio:
#   no defence   mean 483,664   worst -245,528   (liferaft leg worst -813,000)
#   with defence mean 605,870   worst +477,177   (liferaft leg worst  -90,000)
#
# LIFERAFT_ADAPT is flat anywhere from 0.25 to 4.0 -- crowded-room loss moves
# between -$6.8k and -$20.2k and the normal-room mean does not move at all. 1.0
# is the middle of that plateau. It is a risk dial, not a fitted parameter.
#
# The control is inert in a room where we are doing fine, which is the property
# that makes it safe to leave switched on.
LIFERAFT_ADAPT = 1.0
LIFERAFT_ADAPT_WINDOW = 60
LIFERAFT_ADAPT_SCALE = 25000.0
LIFERAFT_ADAPT_MIN_DAYS = 30


def _mean(seq):
    return sum(seq) / float(len(seq))


def _liferaft_regime(move):
    """Which state the room was in yesterday, read off the one observable
    symbol the price prints: a fall means the majority went long, a rise means
    it went short, no change means a tie, an empty room, or the floor masking
    the result."""
    if move < 0:
        return -1
    if move > 0:
        return 1
    return 0


class Algorithm():

    def __init__(self, positions):
        self.data = {}
        self.positionLimits = {}
        self.day = 0
        self.positions = positions
        self._recipe = (PRIOR_A, PRIOR_B)
        # Fintech Token regime: 0 = reverting, +1 / -1 = riding an up / down drift
        self._ft_mode = 0
        # Liferaft: what we decided each day. _lr_actions[i] is the position
        # held on day i, which earned prices[i+1] - prices[i]. Used to mark our
        # own book from the public price path.
        self._lr_actions = []

    def get_current_price(self, instrument):
        return self.data[instrument][-1]

    def _ready(self, *instruments, **kwargs):
        """True only if every named instrument has at least `minimum` prices.

        Every signal below indexes its series directly, so a missing or empty
        history raises IndexError inside get_positions, which the grader does
        not catch. Round 1 always supplies data from day 0, but nothing in the
        contract promises Round 2 will, and the cost of being wrong is the whole
        run rather than one instrument."""
        minimum = kwargs.get("minimum", 1)
        for ins in instruments:
            series = self.data.get(ins)
            if not series or len(series) < minimum:
                return False
        return True

    # ------------------------------------------------------------------
    # Sausage Sizzle cost model
    # ------------------------------------------------------------------

    def _fit_recipe(self):
        """Re-fit the bread/sausage coefficients from Round 2 data once there is
        enough of it. The implied labour cost moves slowly, so the right
        coefficients are the ones that make it smoothest."""
        if not self._ready("Sausage Sizzle", "Bread", "Sausage", minimum=2):
            return
        sz = self.data["Sausage Sizzle"]
        br = self.data["Bread"]
        sa = self.data["Sausage"]
        n = len(sz)
        if n < 90 or self.day % 30 != 0:
            return
        if len(br) < n or len(sa) < n:
            return
        a0, b0 = PRIOR_A, PRIOR_B
        best = None
        for a in [a0 * (1 + i * 0.05) for i in range(-8, 9)]:
            for b in [b0 * (1 + i * 0.05) for i in range(-8, 9)]:
                lab = [sz[t] - a * br[t - 1] - b * sa[t - 1] for t in range(1, n)]
                rough = _mean([abs(lab[i] - lab[i - 1]) for i in range(1, len(lab))])
                if best is None or rough < best[0]:
                    best = (rough, a, b)
        if best is None:
            return
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
        n = min(len(sz), len(br), len(sa))
        return [sz[t] - a * br[t - 1] - b * sa[t - 1] for t in range(1, n)]

    # ------------------------------------------------------------------
    # Per-instrument signals, each returning a target fraction in [-1, 1]
    # ------------------------------------------------------------------

    def _sig_uq_dollar(self):
        if not self._ready("UQ Dollar"):
            return 0.0
        # Pegged at $100 and reliably pulled back in both directions. A deadband
        # would skip the coin-flip days and free that budget for others, but it
        # is set to zero: the peg pays on the small deviations too.
        dev = self.data["UQ Dollar"][-1] - 100.0
        if abs(dev) < UQ_DOLLAR_DEADBAND:
            return 0.0
        return -1.0 if dev > 0 else 1.0

    def _sig_sausage_sizzle(self, labour):
        if not self._ready("Bread", "Sausage", "Sausage Sizzle", minimum=2):
            return 0.0
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
        if not self._ready("MenuDash", minimum=2):
            return 0.0
        # MenuDash is a rounded, surged read of the labour cost that the sizzle
        # reveals exactly. Trade the gap between the two.
        md = self.data["MenuDash"]
        if self.day < 50 or len(labour) < 40:
            return 0.0
        window = min(60, len(labour) - 1, len(md) - 1)
        if window < 2:
            return 0.0
        xs = labour[-window - 1:-1]
        ys = md[len(md) - 1 - window:len(md) - 1]
        n = min(len(xs), len(ys))
        if n < 2:
            return 0.0
        xs, ys = xs[:n], ys[:n]
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
        if not self._ready("Fintech Token"):
            return 0.0
        # Two regimes, as the spec promises. On the plateaus the token oscillates
        # around a level and the trade is reversion; during a repricing it slides
        # in one direction for weeks and reversion is on the wrong side of it.
        # The 130->155 slide in Round 1 cost the reversion book $22k on its own.
        p = self.data["Fintech Token"]
        if self.day < 12 or len(p) < 12:
            return 0.0

        # --- regime detection -------------------------------------------------
        lb = FT_DRIFT_LOOKBACK
        if len(p) > lb:
            window = p[-lb - 1:]
            steps = [window[i] - window[i - 1] for i in range(1, len(window))]
            mu = _mean(steps)
            var = _mean([(s - mu) ** 2 for s in steps])
            sd = var ** 0.5
            if sd > 1e-9:
                # Total move over the window, scaled by the move a random walk of
                # the same daily noise would produce. Large |t| = real drift.
                t_stat = (p[-1] - p[-1 - lb]) / (sd * (lb ** 0.5))
                if self._ft_mode == 0:
                    if abs(t_stat) > FT_DRIFT_ENTER:
                        self._ft_mode = 1 if t_stat > 0 else -1
                else:
                    decayed = abs(t_stat) < FT_DRIFT_ENTER * FT_DRIFT_EXIT_FRAC
                    reversed_ = (t_stat > 0) != (self._ft_mode > 0)
                    if decayed or reversed_:
                        self._ft_mode = 0

        # --- drift regime: ride it at the full limit --------------------------
        if self._ft_mode != 0:
            return float(self._ft_mode)

        # --- stable regime: reversion over three windows ----------------------
        score = 0.0
        for w in (5, 7, 10):
            score += _mean(p[-w:]) - p[-1]
        if abs(score) < 1e-9:
            return 0.0
        return 1.0 if score > 0 else -1.0

    def _sig_boat_party(self):
        if not self._ready("Boat Party Ticket"):
            return 0.0
        # Resale prices overshoot day to day, on top of a semester shape that
        # repeats on the same calendar each year.
        p = self.data["Boat Party Ticket"]
        if self.day < 5 or len(p) < 3:
            return 0.0
        reversion = _mean(p[-3:]) - p[-1]
        d = self.day
        seasonal = 0.0
        if 0 < d < len(BOAT_SEASONAL) - 1:
            seasonal = (BOAT_SEASONAL[d + 1] - BOAT_SEASONAL[d - 1]) / 2.0
        score = reversion + BOAT_SEASONAL_WEIGHT * seasonal
        if abs(score) < 1e-9:
            return 0.0
        return 1.0 if score > 0 else -1.0

    def _sig_momentum(self, instrument, window):
        if not self._ready(instrument):
            return 0.0
        # Bread and Sausage climb slowly with unpredictable weekly jumps; the
        # climb is the only tradeable part.
        p = self.data[instrument]
        if self.day < window + 2 or len(p) < window:
            return 0.0
        score = p[-1] - _mean(p[-window:])
        if abs(score) < 1e-9:
            return 0.0
        return 1.0 if score > 0 else -1.0

    def _sig_thrifted_jeans(self):
        # SWITCHED OFF. Not because the evidence says it definitely loses, but
        # because it does not clear the bar for taking a position at all.
        #
        # This was previously left on as a residual claim on leftover budget,
        # which was defensible while BUDGET_PRIORITY held it near $4k of
        # notional on 66 days. That is no longer what happens. Once the Liferaft
        # estimator started standing down on days it has no edge, roughly $100k
        # a day was released, Jeans is last in the priority list and therefore
        # absorbed most of it, and its footprint went to $42,300 of notional on
        # 351 days. An 11x change in size is not something a "spend the
        # leftovers" argument can carry.
        #
        # At that size it supplied $88,148 of the $110,397 the local backtest
        # gained, so it stopped being a rounding error and became the single
        # largest driver of the number. Re-testing at the new allocation:
        # shuffling the Jeans daily returns 200 times, preserving their
        # distribution and total drift and destroying only their ordering, then
        # rerunning the whole book each time, puts the real ordering at the
        # 96.5th percentile of the null, p = 0.040. That is one marginal result
        # among roughly 43 tests run on this instrument, so it does not survive
        # any correction for multiple testing. The Bonferroni threshold here is
        # 0.0012.
        #
        # The decisive number is that a shuffled, structureless Jeans series
        # still returns $570,010, against $568,609 with the instrument switched
        # off entirely. Trading noise and trading nothing pay the same. What
        # differs is the spread: the null runs from $488,938 to $645,380 at the
        # 5th and 95th percentiles, so keeping Jeans injects a +/- $78k band
        # into the total for an expected gain indistinguishable from zero.
        #
        # Switching it off gives the best Sharpe of the three variants (14.85
        # against 12.47 with it on) and roughly a third of the drawdown
        # (-$4,898 against -$12,544), while still beating the previous
        # always-long-Liferaft book by $22,249. Sharpe is the competition
        # tie-breaker.
        #
        # The freed budget now goes to instruments with a stated mechanism and a
        # measured signal rather than to a series that cannot be distinguished
        # from its own shuffle.
        #
        # Original evidence that it is a random walk, unchanged and still the
        # reason this was never a real signal:
        #
        # ADF p = 0.49 (log price, const) and 0.15 (raw price) -- cannot reject
        # a unit root; KPSS rejects level stationarity at p = 0.010; Hurst =
        # 0.524 (R/S, Anis-Lloyd) and 0.533 (aggregated variance), neither
        # distinguishable from 0.5 against a shuffled-returns null;
        # Lo-MacKinlay variance ratios carry |z| < 0.1 at every horizon from 2
        # to 30 days. Across 43 tests only three came in under p = 0.05 --
        # about what 43 tests produce by chance -- and none survived Bonferroni
        # or a split-half check.
        #
        # The 12-day momentum this used to run was drift capture, not trend.
        # Reshuffling Round 1's own returns 200 times (same distribution, same
        # drift, order destroyed) gives it a mean of -$2.6k and a loss 52% of
        # the time; the $89.8k it booked on Round 1 sits at the 96th percentile
        # of that null. It also consumed $43k of notional and cost Sausage
        # Sizzle $21.3k of foregone profit.
        return 0.0

    def _sig_liferaft(self):
        # A minority game: whichever side the room crowds onto is the side that
        # loses. Nothing here is fitted to Round 1, whose Liferaft CSV is
        # scaffolding -- the price is computed live during marking, and the
        # local engine forces this instrument's P&L to zero anyway.
        #
        # The one observable is the daily move, which is exactly the P&L of one
        # long ticket: -5,000 when the room went long, +8,000 when it went
        # short, 0 on a tie. So the estimator runs directly on realised moves
        # and needs no separate payoff model, and the floor is handled for free
        # (a majority-long day at $20,000 realises 0, and that zero enters the
        # sample honestly).
        #
        # Three things do the work, in order of how much they matter:
        #
        #   1. Conditioning on the current regime rather than pooling the year.
        #      A room that alternates long/short pools to an exact coin flip and
        #      looks unplayable while being perfectly predictable. Out of sample
        #      this is worth 4.4x over pooling ($588k vs $133k) with
        #      non-overlapping confidence intervals. It is the entire edge.
        #
        #   2. Requiring the edge to clear k standard errors. One regime bucket
        #      holds well under the 150-200 observations needed to tell a 60/40
        #      room from a coin flip, so we are permanently in the range where
        #      the estimate is unreliable. Acting on the raw sample mean means
        #      systematically selecting the noisiest favourable readings.
        #
        #   3. Returning zero when neither side clears. Abstention is the only
        #      state that observes without voting, and it is what produces every
        #      good tail number: adding it alone moved the worst simulated year
        #      from -$940k to -$55k.
        #
        # Crowding used to be listed here as an unfixable weakness. It is now
        # partly fixed -- see LIFERAFT_ADAPT. The break-even against copies of
        # the un-patched rule moves from roughly three to beyond eight.
        # Keep the log indexed by day rather than by call count. Blindly
        # appending assumes get_positions is called exactly once per day with
        # the day advancing by one -- true for the reference grader, but a
        # repeated or skipped call would silently shift every past action
        # against the price it earned, and the crowding defence reads that
        # alignment. Padding and overwriting costs nothing and cannot desync.
        while len(self._lr_actions) < self.day:
            self._lr_actions.append(0)

        prices = self.data.get("Liferaft Ticket")
        action = 0 if not prices else int(self._liferaft_decide(prices))

        if len(self._lr_actions) > self.day:
            self._lr_actions[self.day] = action
        else:
            self._lr_actions.append(action)
        return float(action)

    def _liferaft_decide(self, prices):
        """Returns 1 (long), -1 (short) or 0 (stand down)."""
        # --- our own realised P&L, read straight off the public price path ---
        # _lr_actions[i] is what we held on day i; it earned prices[i+1]-prices[i].
        acts = self._lr_actions
        settled = min(len(acts), len(prices) - 1)
        recent = 0.0
        for i in range(max(0, settled - LIFERAFT_ADAPT_WINDOW), settled):
            recent += acts[i] * (prices[i + 1] - prices[i])

        # --- floor: a long cannot lose here, but do not sit in a dead one ----
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

        # --- regime-conditioned sample ---------------------------------------
        # Tally past moves in the bucket matching today's regime, where the
        # regime is simply what the room did yesterday.
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

        # --- haircut, widened when our own recent decisions have been wrong ---
        # Both sides pay the same haircut; act only if an edge survives it,
        # otherwise stand down.
        k = LIFERAFT_K
        if settled >= LIFERAFT_ADAPT_MIN_DAYS and recent < 0.0:
            k += LIFERAFT_ADAPT * (-recent / LIFERAFT_ADAPT_SCALE)

        if mean - k * se > 0:
            return 1
        if -mean - k * se > 0:
            return -1
        return 0

    # ------------------------------------------------------------------
    # Budget packing -- the $600k cap, maintained dynamically
    # ------------------------------------------------------------------

    def _funding_order(self):
        """Instruments in the order they get to claim budget. Anything not named
        in BUDGET_PRIORITY is appended, so a new instrument appearing in Round 2
        is funded last rather than silently dropped."""
        order = [i for i in BUDGET_PRIORITY
                 if i in self.positionLimits and i in self.data and self.data[i]]
        order += [i for i in self.positionLimits
                  if i not in BUDGET_PRIORITY and i in self.data and self.data[i]]
        return order

    def _book_value(self, positions):
        """Total portfolio value exactly as the grader computes it:
        sum of abs(position * decision-time price) across every instrument."""
        total = 0.0
        for ins, pos in positions.items():
            if pos and ins in self.data and self.data[ins]:
                total += abs(pos * self.data[ins][-1])
        return total

    def _enforce_budget(self, positions):
        """Last line of defence, run after allocation regardless of how the
        positions were arrived at.

        The greedy pass below already tracks spending, but it trusts its own
        running total. This recomputes the book the way the grader does and
        trims until it is genuinely under the cap, giving up the least valuable
        exposure first by walking the funding order backwards. It is written to
        be correct even if the allocator above is later changed or broken.

        Each pass removes at least one unit, and there are finitely many units,
        so this always terminates."""
        order = self._funding_order()
        cap = TOTAL_BUDGET - BUDGET_RESERVE
        guard = 0
        while guard < 500:
            guard += 1
            excess = self._book_value(positions) - cap
            if excess <= 0:
                return positions

            trimmed = False
            for ins in reversed(order):
                pos = positions.get(ins, 0)
                if not pos:
                    continue
                price = self.data[ins][-1]
                if price <= 0:
                    positions[ins] = 0
                    trimmed = True
                    break
                # drop just enough units to clear the excess, plus one for the
                # reserve, but never more than we are holding
                units = int(excess // price) + 1
                units = min(units, abs(pos))
                positions[ins] = pos - units if pos > 0 else pos + units
                trimmed = True
                break

            if not trimmed:
                # nothing left to trim; the book is already flat
                return positions
        return positions

    def _allocate(self, fractions):
        """Convert target fractions into integer positions that respect the
        per-instrument limits and the total daily budget.

        Budget is claimed greedily in priority order against the *live*
        remaining balance, so the book adapts by itself: whenever a high
        priority instrument is flat, or is cheap that day, the capacity it does
        not use flows to whatever comes next. Nothing is sized against a fixed
        allowance. An instrument that cannot afford a single unit is skipped
        rather than aborting the pass, so a cheaper instrument further down the
        list can still be funded from what is left."""
        cap = TOTAL_BUDGET - BUDGET_RESERVE
        positions = {ins: 0 for ins in self.positionLimits}
        spent = 0.0

        for ins in self._funding_order():
            if ins in DISABLED_INSTRUMENTS:
                continue

            limit = self.positionLimits[ins]
            price = self.data[ins][-1]
            if price <= 0 or limit <= 0:
                continue

            frac = fractions.get(ins, 0.0)
            if frac != frac:          # NaN guard; NaN fails every comparison
                continue
            frac = max(-1.0, min(1.0, frac))
            want = int(round(frac * limit))
            if want == 0:
                continue

            remaining = cap - spent
            if remaining <= 0:
                break
            affordable = int(remaining // price)
            size = min(abs(want), affordable, int(limit))
            if size <= 0:
                continue

            positions[ins] = size if want > 0 else -size
            spent += size * price

        positions = self._enforce_budget(positions)

        # The grader tests `type(x) != type(1)`, an exact type check: a numpy
        # integer or a float is silently zeroed rather than rejected loudly. Any
        # position limit arriving as a numpy type would propagate through min()
        # and poison the result, so cast on the way out and clamp to the limit
        # one final time. Disabled instruments are forced flat here too, so no
        # change further up this file can put a position on them by accident.
        clean = {}
        for ins in self.positionLimits:
            if ins in DISABLED_INSTRUMENTS:
                clean[ins] = 0
                continue
            pos = int(positions.get(ins, 0))
            limit = int(self.positionLimits[ins])
            if pos > limit:
                pos = limit
            elif pos < -limit:
                pos = -limit
            clean[ins] = pos
        return clean

    # ------------------------------------------------------------------

    def _flat(self):
        """A valid all-zero book. Used as the failure mode of last resort: the
        grader does not wrap get_positions in a try/except, so an unhandled
        exception on any single day ends the whole run. Sitting out one day
        costs that day's P&L; raising costs the year."""
        try:
            return {ins: 0 for ins in self.positionLimits}
        except Exception:
            return {}

    def _compute_positions(self):
        # Round 2 restarts the clock; make sure no regime state carries over.
        if self.day == 0:
            self._ft_mode = 0
            self._recipe = (PRIOR_A, PRIOR_B)
            # Round 2 restarts the clock; without this the action log from a
            # previous year poisons the trailing window on day 0.
            self._lr_actions = []

        self._fit_recipe()
        labour = (self._labour_series()
                  if self._ready("Sausage Sizzle", "Bread", "Sausage", minimum=2)
                  else [])

        fractions = {
            "UQ Dollar": self._sig_uq_dollar(),
            "Sausage Sizzle": self._sig_sausage_sizzle(labour),
            "MenuDash": self._sig_menudash(labour),
            "Fintech Token": self._sig_fintech_token(),
            "Boat Party Ticket": self._sig_boat_party(),
            "Bread": self._sig_momentum("Bread", 10),
            "Sausage": self._sig_momentum("Sausage", 10),
            "Thrifted Jeans": self._sig_thrifted_jeans(),   # always 0.0
            "Liferaft Ticket": self._sig_liferaft(),
        }

        return self._allocate(fractions)

    def get_positions(self):
        try:
            return self._compute_positions()
        except Exception:
            return self._flat()
