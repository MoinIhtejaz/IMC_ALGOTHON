"""
Scenario B -- Round 2 price-path risk.

The Liferaft is set aside here (Scenario A covers it). What varies instead is
the one thing we cannot see: the actual realisation of Round 2's eight
generated price series.

Each instrument is regenerated from *its own stated mechanism*, fitted on Round
1, rather than by reshuffling returns. Reshuffling would destroy the very
structure the strategy trades -- a shuffled UQ Dollar is no longer pegged -- and
would answer the wrong question. The question here is: the mechanism is the
same next year, the dice are not; how much does the P&L move?

Fitted mechanisms
-----------------
  UQ Dollar       100 + AR(1) noise, phi 0.055, sd 0.429. Near-white deviation
                  around the peg, which is what "pegged" means.
  labour cost     random walk, increments resampled from Round 1's implied
                  labour increments (preserves drift and fat tails).
  Bread, Sausage  random walk, increments resampled from Round 1.
  Sausage Sizzle  A*bread[t-1] + B*sausage[t-1] + labour[t-1], EXACTLY. The
                  Round 1 residual of this identity is 0.00000, so the recipe
                  is not an approximation, it is the generating rule.
  MenuDash        0.10422*labour - 0.0459 + an AR(1) surge residual, rounded to
                  the cent (Round 1 prints only 31 distinct values, i.e. a
                  tick). The AR(1) matters enormously: Round 1's residual has
                  ACF1 = 0.765, because surge pricing persists for days. Drawing
                  it iid instead makes the gap revert fully every day and hands
                  the strategy $480k of fantasy profit against the $134k it
                  actually earned. Persistence is what makes this instrument
                  hard, so it has to be in the generator.
  Fintech Token   random-walk level plus an AR(1) deviation. Rather than trust a
                  filter to split the two, the split is moment-matched to Round
                  1's sd(diff) = 13.25 and ACF1(diff) = -0.133, which are the
                  two statistics the reversion signal actually consumes.
  Boat Party      Round 1 seasonal shape on the SAME calendar (the spec says the
                  semester pattern repeats day-of-year) with a RANDOMISED
                  amplitude each year (it also says the height of each peak does
                  not repeat), plus AR(1) overreaction noise, moment-matched to
                  ACF1(diff) = -0.168.
  Thrifted Jeans  random walk. Not traded, included only so the instrument set
                  is complete.

Calibration is checked, not assumed: `validate()` regenerates the diagnostic
statistics from synthetic years and compares them against Round 1.
"""

import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from algorithm import Algorithm  # noqa: E402

LIMITS = {
    "Fintech Token": 100, "Thrifted Jeans": 800, "UQ Dollar": 650,
    "Sausage Sizzle": 3000, "Bread": 500, "MenuDash": 75000,
    "Sausage": 5000, "Liferaft Ticket": 1, "Boat Party Ticket": 1000,
}
CAP = 600_000
A, B = 0.07692, 1.76921
DAYS = 365


def load_round1():
    folder = os.path.join(REPO, "trader_interface", "data")
    out = {}
    for f in os.listdir(folder):
        if f.endswith("_price_history.csv"):
            out[f.split("_")[0]] = pd.read_csv(os.path.join(folder, f))["Price"].tolist()
    return out


def _acf1(x):
    x = np.asarray(x, float)
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def _split_level_dev(var_diff, acf1_diff, phi):
    """Split a series into (random-walk level, AR(1) deviation) so that the sum
    reproduces an observed sd(diff) and ACF1(diff).

    For p = L + D with L a random walk of variance s_l^2 and D an AR(1) with
    stationary variance s_d^2:
        Var(dp)      = s_l^2 + 2 s_d^2 (1 - phi)
        Cov(dp, dp1) = -s_d^2 (1 - phi)^2
    Writing u = s_d^2 (1 - phi), ACF1 = -u(1-phi)/Var, so u is pinned by the
    observed ACF1 and phi is the only free choice. Returns None if the requested
    phi implies a negative level variance."""
    u = -acf1_diff * var_diff / (1.0 - phi)
    s_l2 = var_diff - 2.0 * u
    if s_l2 < 0 or u <= 0:
        return None
    s_d2 = u / (1.0 - phi)
    return float(np.sqrt(s_l2)), float(np.sqrt(s_d2))


def _block_boot(inc, n, rng, block=10):
    """Moving-block bootstrap. An iid resample of increments would flatten
    ACF1(diff), and for Bread and Sausage that autocorrelation (+0.06, +0.09) is
    precisely what the momentum signal trades -- destroying it would understate
    those two lines. Blocks keep local structure while randomising the year."""
    inc = np.asarray(inc, float)
    out = []
    while len(out) < n:
        s = int(rng.integers(0, max(1, len(inc) - block)))
        out.extend(inc[s:s + block])
    return np.array(out[:n])


def _solve_phi(target_acf1, sim, lo=0.0, hi=0.98, iters=18):
    """Bisect on phi so a simulated series reproduces a target ACF1(diff).
    ACF1(diff) increases with phi (more persistence = less apparent reversion),
    so plain bisection is safe. Used where a closed form is unavailable because
    rounding or a seasonal term also touches the diff."""
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if sim(mid) < target_acf1:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _pick_phi(var_diff, acf1_diff):
    """Largest feasible persistence, backed off for headroom. Higher phi means a
    slower-reverting deviation, which is the conservative direction: it gives
    the reversion signal less to eat."""
    for phi in np.arange(0.90, -0.01, -0.02):
        got = _split_level_dev(var_diff, acf1_diff, float(phi))
        if got is not None and got[0] > 0.05 * np.sqrt(var_diff):
            return float(phi), got[0], got[1]
    phi = 0.0
    s_l, s_d = _split_level_dev(var_diff, acf1_diff, phi)
    return phi, s_l, s_d


def fit(d):
    """Extract every parameter the generator needs from Round 1."""
    sz, br, sa, md = d["Sausage Sizzle"], d["Bread"], d["Sausage"], d["MenuDash"]
    labour = [sz[t] - A * br[t - 1] - B * sa[t - 1] for t in range(1, len(sz))]

    n = min(len(md) - 1, len(labour))
    xs, ys = np.array(labour[:n]), np.array(md[1:n + 1])
    slope = np.cov(xs, ys, bias=True)[0, 1] / xs.var()
    inter = ys.mean() - slope * xs.mean()
    md_res = ys - (inter + slope * xs)
    # Surge pricing persists; drawing this iid is the single biggest way to
    # accidentally overstate the strategy. The raw residual ACF1 is only a
    # starting point -- rounding to the cent adds its own reversion to the
    # printed series, so phi is solved against the printed ACF1(diff).
    # Estimate the surge process directly from the residual, not by solving
    # against the printed ACF1(diff). The printed diff mixes three things --
    # surge reversion, the labour fair value, and cent rounding -- so fitting to
    # it pushed phi up to ~0.97, produced a gap twice as wide as Round 1's that
    # barely reverted, and cut the signal's information coefficient from 0.28 to
    # 0.10. The residual's own ACF1 is the parameter that actually governs how
    # fast the gap closes, and it is directly observable.
    md_phi = float(_acf1(md_res))
    md_sd = float(md_res.std())
    md_innov = float(md_sd * np.sqrt(max(1e-6, 1 - md_phi ** 2)))
    # residual is near-Gaussian in Round 1 (skew -0.14, kurtosis 3.01), so a
    # normal innovation is appropriate rather than a resample

    ft = np.array(d["Fintech Token"])
    dft = np.diff(ft)
    ft_phi, ft_slevel, ft_sdev = _pick_phi(float(dft.var()), _acf1(dft))
    ft_innov = ft_sdev * np.sqrt(max(1e-6, 1 - ft_phi ** 2))

    bp = np.array(d["Boat Party Ticket"])
    seas = pd.Series(bp).rolling(21, min_periods=1, center=True).mean().to_numpy()
    dbp = np.diff(bp)
    bp_target = _acf1(dbp)
    # The closed form ACF1 = -(1-phi)/2 ignores the seasonal slope, which is not
    # negligible once the amplitude is randomised, so solve numerically against
    # the full generated series instead.
    bp_var = float(dbp.var())

    def _bp_sim(phi):
        r = np.random.default_rng(999)
        sd = np.sqrt(bp_var / (2.0 * max(1e-6, 1.0 - phi)))
        innov = sd * np.sqrt(max(1e-6, 1 - phi ** 2))
        acc = []
        for _ in range(6):
            res = np.zeros(DAYS)
            e = r.normal(0, innov, DAYS)
            for t in range(1, DAYS):
                res[t] = phi * res[t - 1] + e[t]
            amp = r.uniform(0.6, 1.4)
            base = seas.mean()
            bs = base + amp * (seas - base)
            acc.append(_acf1(np.diff(np.round(bs[:DAYS] + res, 2))))
        return float(np.mean(acc))

    bp_phi = _solve_phi(bp_target, _bp_sim)
    bp_sd = float(np.sqrt(bp_var / (2.0 * max(1e-6, 1.0 - bp_phi))))
    bp_innov = bp_sd * np.sqrt(max(1e-6, 1 - bp_phi ** 2))

    uq = np.array(d["UQ Dollar"]) - 100.0
    ph_uq = float(np.dot(uq[:-1], uq[1:]) / np.dot(uq[:-1], uq[:-1]))
    uq_innov = float((uq[1:] - ph_uq * uq[:-1]).std())

    return {
        "labour0": labour[0],
        "labour_inc": np.diff(labour),
        "bread0": br[0], "bread_inc": np.diff(br),
        "saus0": sa[0], "saus_inc": np.diff(sa),
        "md_slope": slope, "md_inter": inter,
        "md_phi": md_phi, "md_innov": md_innov,
        "ft0": float(ft[0]), "ft_slevel": ft_slevel,
        "ft_phi": ft_phi, "ft_innov": ft_innov,
        "bp_seas": seas, "bp_phi": bp_phi, "bp_innov": bp_innov,
        "uq_phi": ph_uq, "uq_innov": uq_innov,
        "jeans0": d["Thrifted Jeans"][0],
        "jeans_inc": np.diff(d["Thrifted Jeans"]),
    }


def synth_year(f, rng, days=DAYS):
    pick = lambda arr, n: rng.choice(arr, size=n, replace=True)
    boot = lambda arr, n: _block_boot(arr, n, rng)

    labour = f["labour0"] + np.concatenate([[0.0], np.cumsum(boot(f["labour_inc"], days))])
    bread = f["bread0"] + np.concatenate([[0.0], np.cumsum(boot(f["bread_inc"], days))])
    saus = f["saus0"] + np.concatenate([[0.0], np.cumsum(boot(f["saus_inc"], days))])

    # Round the inputs BEFORE applying the recipe. Round 1's sizzle satisfies the
    # identity to 0.00000 on the printed 2dp series, which is only possible if
    # the generator worked from printed inputs. Rounding afterwards instead
    # leaves ~0.01 of slop and quietly blunts the sizzle signal.
    bread = np.round(np.maximum(bread, 1.0), 2)
    saus = np.round(np.maximum(saus, 0.1), 2)
    labour = np.round(np.maximum(labour, 1.0), 2)

    sizzle = np.empty(days)
    sizzle[0] = round(A * bread[0] + B * saus[0] + labour[0], 2)
    for t in range(1, days):
        sizzle[t] = round(A * bread[t - 1] + B * saus[t - 1] + labour[t - 1], 2)

    md_fair = f["md_inter"] + f["md_slope"] * np.concatenate([[labour[0]], labour[:days - 1]])
    surge = np.empty(days)
    surge[0] = 0.0
    em = rng.normal(0, f["md_innov"], days)
    for t in range(1, days):                        # persistent surge, ACF1 0.765
        surge[t] = f["md_phi"] * surge[t - 1] + em[t]
    md = np.round(np.maximum(md_fair + surge, 0.05), 2)   # cent tick, as in Round 1

    lvl = f["ft0"] + np.concatenate([[0.0], np.cumsum(rng.normal(0, f["ft_slevel"], days - 1))])
    dev = np.empty(days)
    dev[0] = 0.0
    e = rng.normal(0, f["ft_innov"], days)
    for t in range(1, days):
        dev[t] = f["ft_phi"] * dev[t - 1] + e[t]
    ft = np.maximum(lvl + dev, 1.0)

    # The calendar repeats on the same day-of-year -- the spec is explicit about
    # this, and it is the whole basis of the seasonal tilt. Only the HEIGHT of
    # each peak varies. Randomising the phase as well was a modelling error: it
    # silently deleted a signal the strategy is entitled to have, and dragged
    # the whole price book roughly $100k below Round 1.
    seas = f["bp_seas"]
    amp = rng.uniform(0.6, 1.4)
    base = seas.mean()
    bseas = base + amp * (seas - base)
    bres = np.empty(days)
    bres[0] = 0.0
    eb = rng.normal(0, f["bp_innov"], days)
    for t in range(1, days):
        bres[t] = f["bp_phi"] * bres[t - 1] + eb[t]
    bp = np.maximum(bseas[:days] + bres, 1.0)

    uq = np.empty(days)
    uq[0] = 0.0
    eu = rng.normal(0, f["uq_innov"], days)
    for t in range(1, days):
        uq[t] = f["uq_phi"] * uq[t - 1] + eu[t]
    uqd = 100.0 + uq

    jeans = np.maximum(
        f["jeans0"] + np.concatenate([[0.0], np.cumsum(boot(f["jeans_inc"], days - 1))]), 1.0)

    return {
        "UQ Dollar": np.round(uqd, 2).tolist(),
        "Bread": bread[:days].tolist(),
        "Sausage": saus[:days].tolist(),
        "Sausage Sizzle": sizzle.tolist(),
        "MenuDash": md.tolist(),
        "Fintech Token": np.round(ft, 2).tolist(),
        "Boat Party Ticket": np.round(bp, 2).tolist(),
        "Thrifted Jeans": np.round(jeans[:days], 2).tolist(),
    }


def score(prices, days=DAYS, liferaft=None):
    """Run the real Algorithm over a synthetic year. Liferaft held flat unless
    a price series is supplied, so this isolates the generated-instrument book."""
    algo = Algorithm({k: 0 for k in LIMITS})
    algo.positionLimits = LIMITS
    prev = {k: 0 for k in LIMITS}
    per = {k: 0.0 for k in LIMITS}
    breaches = 0
    eq = []
    total = 0.0
    lr = liferaft if liferaft is not None else [100_000] * days

    for day in range(days):
        hist = {k: v[:day + 1] for k, v in prices.items()}
        hist["Liferaft Ticket"] = lr[:day + 1]
        algo.day, algo.data, algo.positions = day, hist, prev
        pos = algo.get_positions()

        book = sum(abs(pos[k] * hist[k][-1]) for k in LIMITS if hist.get(k))
        if book > CAP:
            breaches += 1
            pos = {k: 0 for k in LIMITS}

        if day:
            for k in prices:
                dp = prev[k] * (prices[k][day] - prices[k][day - 1])
                per[k] += dp
                total += dp
        eq.append(total)
        prev = pos

    peak, dd = -1e18, 0.0
    for v in eq:
        peak = max(peak, v)
        dd = min(dd, v - peak)
    return total, per, breaches, dd


def validate(n=60, seed=99):
    """Does a synthetic year look like Round 1 on the statistics the strategy
    actually consumes? If not, every best/worst number below is fiction."""
    d = load_round1()
    f = fit(d)
    rng0 = np.random.default_rng(seed)
    years = [synth_year(f, np.random.default_rng(rng0.integers(0, 2**63 - 1)))
             for _ in range(n)]

    print("=" * 74)
    print("GENERATOR CALIBRATION -- Round 1 vs synthetic (mean over %d years)" % n)
    print("=" * 74)
    print(f"{'instrument':<20}{'stat':<12}{'Round 1':>12}{'synthetic':>12}{'':>6}")
    rows = []
    for k in ["UQ Dollar", "Fintech Token", "Boat Party Ticket", "MenuDash",
              "Bread", "Sausage", "Sausage Sizzle"]:
        real = np.array(d[k])
        for stat, fn, rel in [("sd(diff)", lambda a: np.diff(a).std(), 0.20),
                              ("ACF1(diff)", lambda a: _acf1(np.diff(a)), None)]:
            r = float(fn(real))
            s = float(np.mean([fn(np.array(y[k])) for y in years]))
            # relative tolerance for scale stats (an absolute floor would let a
            # 2.4x error on a small-priced instrument pass); absolute for ACF
            tol = rel * abs(r) if rel is not None else 0.05
            flag = "ok" if abs(s - r) <= tol else "OFF"
            rows.append(flag)
            print(f"{k:<20}{stat:<12}{r:>12.4f}{s:>12.4f}{flag:>6}")

    # NOT a check that "sizzle = recipe + labour" holds: that is a tautology,
    # since labour is *defined* as the recipe residual. What actually determines
    # whether the sizzle signal works is how fast the implied labour cost moves
    # relative to the known bread/sausage part -- a slow labour series makes
    # tomorrow's sizzle nearly known today. So compare that.
    def labour_inc_sd(series):
        sz, br, sa = (np.array(series["Sausage Sizzle"]), np.array(series["Bread"]),
                      np.array(series["Sausage"]))
        lab = sz[1:] - A * br[:-1] - B * sa[:-1]
        return float(np.diff(lab).std())

    r1 = labour_inc_sd(d)
    sy = float(np.mean([labour_inc_sd(y) for y in years]))
    flag = "ok" if abs(sy - r1) <= 0.25 * r1 else "OFF"
    rows.append(flag)
    print(f"\n{'implied labour':<20}{'sd(diff)':<12}{r1:>12.4f}{sy:>12.4f}{flag:>6}"
          f"   <- what makes the sizzle predictable")
    print(f"checks passed: {rows.count('ok')}/{len(rows)}")
    return rows.count("OFF") == 0


def main(n=300, seed=7770809):
    d = load_round1()
    f = fit(d)
    master = np.random.default_rng(seed)

    totals, dds, allper = [], [], []
    for i in range(n):
        rng = np.random.default_rng(master.integers(0, 2**63 - 1))
        prices = synth_year(f, rng)
        t, per, br, dd = score(prices)
        assert br == 0, f"budget breach in synthetic year {i}"
        totals.append(t)
        dds.append(dd)
        allper.append(per)
        if (i + 1) % 50 == 0:
            print(f"  ...{i + 1}/{n} synthetic years", flush=True)

    t = np.array(totals)
    np.save(os.path.join(HERE, "scenarioB_totals.npy"), t)
    np.save(os.path.join(HERE, "scenarioB_dd.npy"), np.array(dds))
    q = lambda x: float(np.percentile(t, x))

    print("\n" + "=" * 74)
    print(f"SCENARIO B -- Round 2 price-path risk ({n} synthetic years)")
    print("Liferaft held flat; only the generated instruments vary")
    print("=" * 74)
    print(f"  best (max)   {t.max():>12,.0f}")
    print(f"  p95          {q(95):>12,.0f}")
    print(f"  p75          {q(75):>12,.0f}")
    print(f"  median       {q(50):>12,.0f}")
    print(f"  mean         {t.mean():>12,.0f}")
    print(f"  p25          {q(25):>12,.0f}")
    print(f"  p05          {q(5):>12,.0f}")
    print(f"  worst (min)  {t.min():>12,.0f}")
    print(f"\n  P(loss on the price book)  {float((t < 0).mean()):.3f}")
    print(f"  worst drawdown seen        {min(dds):,.0f}")
    print(f"  budget breaches            0 / {n} years")

    print("\n  Per-instrument, mean and worst across synthetic years:")
    keys = sorted(allper[0], key=lambda k: -np.mean([p[k] for p in allper]))
    for k in keys:
        v = np.array([p[k] for p in allper])
        if abs(v).max() == 0 and k in ("Thrifted Jeans", "Liferaft Ticket"):
            print(f"    {k:<20} {'flat -- not traded':>34}")
            continue
        print(f"    {k:<20} mean {v.mean():>10,.0f}   p05 {np.percentile(v,5):>10,.0f}"
              f"   worst {v.min():>10,.0f}   P(loss) {float((v<0).mean()):.2f}")
    return t


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
