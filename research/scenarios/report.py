"""Best case / worst case, assembled from the two scenario Monte Carlos."""

import os
import numpy as np
import run_shard as R

HERE = os.path.dirname(os.path.abspath(__file__))
R1 = 568_609


def q(a, p):
    return float(np.percentile(a, p))


def line(label, v, w=14):
    return f"{label:<26}" + "".join(f"{x:>{w},.0f}" for x in v)


def main():
    A = R.collect("A")
    B = R.collect("B3")
    tA, pA, lA = A["total"], A["price"], A["liferaft"]
    tB, ddB, perB = B["total"], B["dd"], B["per"]
    keys = list(B["keys"])

    print("=" * 92)
    print("BEST CASE / WORST CASE".center(92))
    print(f"Round 1 backtest for reference: ${R1:,}".center(92))
    print("=" * 92)

    print(f"\nScenario A -- the room varies, prices are Round 1 ({len(tA)} random held-out rooms)")
    print(f"{'':<26}{'TOTAL':>14}{'price book':>14}{'liferaft':>14}")
    for lab, p in [("BEST (max)", 100), ("p95", 95), ("p75", 75), ("median", 50),
                   ("p25", 25), ("p05", 5), ("WORST (min)", 0)]:
        print(line(lab, [q(tA, p), q(pA, p), q(lA, p)]))
    print(line("mean", [tA.mean(), pA.mean(), lA.mean()]))
    print(f"\n  P(total loss) {float((tA < 0).mean()):.3f}   "
          f"P(liferaft loss) {float((lA < 0).mean()):.3f}   "
          f"P(liferaft = 0, stood down all year) {float((lA == 0).mean()):.3f}")
    print(f"  liferaft traded a median of {np.median(A['traded']):.0f} of 365 days")

    print(f"\nScenario B -- prices vary, liferaft flat ({len(tB)} synthetic years)")
    print(f"{'':<26}{'TOTAL':>14}")
    for lab, p in [("BEST (max)", 100), ("p95", 95), ("p75", 75), ("median", 50),
                   ("p25", 25), ("p05", 5), ("WORST (min)", 0)]:
        print(line(lab, [q(tB, p)]))
    print(line("mean", [tB.mean()]))
    print(f"\n  P(loss on the price book) {float((tB < 0).mean()):.3f}")
    print(f"  worst drawdown across all years  ${min(ddB):,.0f}")

    print("\n  Per-instrument across synthetic years:")
    print(f"    {'instrument':<20}{'mean':>12}{'best':>12}{'p05':>12}{'worst':>12}{'P(loss)':>10}")
    order = np.argsort(-perB.mean(axis=0))
    for i in order:
        v = perB[:, i]
        if np.abs(v).max() == 0:
            print(f"    {keys[i]:<20}{'flat -- not traded':>58}")
            continue
        print(f"    {keys[i]:<20}{v.mean():>12,.0f}{v.max():>12,.0f}"
              f"{np.percentile(v,5):>12,.0f}{v.min():>12,.0f}{float((v<0).mean()):>10.2f}")

    # ---- combined: price risk and room risk are independent draws ----
    rng = np.random.default_rng(11)
    comb = (rng.choice(tB, 200_000, replace=True)
            + rng.choice(lA, 200_000, replace=True))
    print("\n" + "-" * 92)
    print("COMBINED -- both vary (price paths x rooms, 200,000 pairings)")
    print("-" * 92)
    for lab, p in [("BEST (p99.9)", 99.9), ("great (p95)", 95), ("good (p75)", 75),
                   ("EXPECTED (median)", 50), ("poor (p25)", 25), ("bad (p05)", 5),
                   ("WORST (p00.1)", 0.1)]:
        print(line(lab, [q(comb, p)]))
    print(line("mean", [comb.mean()]))
    print(f"\n  P(total < 0)          {float((comb < 0).mean()):.4f}")
    print(f"  P(total < Round 1)    {float((comb < R1).mean()):.4f}")
    print(f"  P(total > $1,000,000) {float((comb > 1e6).mean()):.4f}")

    # ---- crowding stress ----
    print("\n" + "-" * 92)
    print("ADVERSARIAL -- other teams running the same Liferaft logic")
    print("-" * 92)
    print(f"{'clones':<10}{'mean total':>14}{'median':>14}{'p05':>14}{'worst':>14}{'P(loss)':>10}")
    base = tA
    print(f"{'0':<10}{base.mean():>14,.0f}{q(base,50):>14,.0f}{q(base,5):>14,.0f}"
          f"{base.min():>14,.0f}{float((base<0).mean()):>10.2f}")
    for c in range(1, 6):
        C = R.collect(f"A_c{c}")
        if C is None:
            continue
        t = C["total"]
        print(f"{c:<10}{t.mean():>14,.0f}{q(t,50):>14,.0f}{q(t,5):>14,.0f}"
              f"{t.min():>14,.0f}{float((t<0).mean()):>10.2f}")

    print("\n" + "=" * 92)
    print("Floor for the whole book: if the Liferaft estimator stands down all year,")
    print(f"the eight generated instruments alone give a median of ${q(tB,50):,.0f}")
    print(f"and were profitable in {100*float((tB>0).mean()):.1f}% of synthetic years.")
    print("=" * 92)


if __name__ == "__main__":
    main()
