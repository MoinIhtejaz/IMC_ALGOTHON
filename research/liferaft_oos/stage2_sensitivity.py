"""
Stage 2: parameter sensitivity.

The question is not "which k is best" (picking that on these rooms would be the
very overfitting we are testing for). The question is whether the frozen k=2 sits
on a plateau or on a spike. A plateau means the result survives the parameter
being roughly right. A spike means the reported number is an artefact.
"""

import sys

from harness import RULE, SEEDS, evaluate, fmt, save
from strategies import candidate

N = 250
SEED = SEEDS["sensitivity"]

HEAD = (f"{'setting':<26}{'mean':>12} {'95% CI':>25} {'median':>11} {'p05':>11} "
        f"{'p95':>11} {'worst':>12} {'P(loss)':>8} {'days':>6}")

which = sys.argv[1] if len(sys.argv) > 1 else "k"
out = {}

if which == "k":
    print("=" * 132)
    print("STAGE 2a  CONFIDENCE DISCOUNT k  (frozen value is 2.0)")
    print("=" * 132)
    print(HEAD)
    print(RULE)
    for k in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0]:
        row = evaluate(lambda k=k: candidate(k=k), N, SEED)
        out[str(k)] = row
        print(fmt(f"k = {k}", row))
    save("sens_k", out)

elif which == "warmup":
    print("=" * 132)
    print("STAGE 2b  WARMUP LENGTH  (frozen value is 40)")
    print("=" * 132)
    print(HEAD)
    print(RULE)
    for w in [0, 10, 20, 40, 60, 90, 140]:
        row = evaluate(lambda w=w: candidate(warmup=w), N, SEED)
        out[str(w)] = row
        print(fmt(f"warmup = {w}", row))
    save("sens_warmup", out)

elif which == "probe":
    print("=" * 132)
    print("STAGE 2c  PROBE CADENCE  (frozen value is every 6th day)")
    print("=" * 132)
    print(HEAD)
    print(RULE)
    for p in [0, 3, 4, 6, 8, 12, 20]:
        row = evaluate(lambda p=p: candidate(probe=p), N, SEED)
        out[str(p)] = row
        print(fmt("probe = none" if p == 0 else f"probe = every {p}", row))
    save("sens_probe", out)

elif which == "minn":
    print("=" * 132)
    print("STAGE 2d  MINIMUM SAMPLE PER BUCKET  (frozen value is 5)")
    print("=" * 132)
    print(HEAD)
    print(RULE)
    for m in [2, 3, 5, 8, 15, 30]:
        row = evaluate(lambda m=m: candidate(min_n=m), N, SEED)
        out[str(m)] = row
        print(fmt(f"min_n = {m}", row))
    save("sens_minn", out)
