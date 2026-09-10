"""
Stage 3: adversarial rooms, self-play crowding, and room size.

These are the cases a random room draw under-samples. Each one is a room built
specifically to be hostile to a regime-conditioned contrarian, or to a strategy
whose single vote matters.
"""

import sys

from harness import RULE, SEEDS, evaluate, fmt, random_pick, save
from opponents import AlternatorK, BiasedRandom, NoisyRegimeContrarian, ThresholdHerder
from strategies import AlwaysLong, FloorOnly, candidate

HEAD = (f"{'room':<26}{'mean':>12} {'95% CI':>25} {'median':>11} {'p05':>11} "
        f"{'p95':>11} {'worst':>12} {'P(loss)':>8} {'days':>6}")


def room_all_clones(rng, n=20):
    """Every opponent runs the candidate's own logic. Worst case for crowding."""
    return [NoisyRegimeContrarian(window=60, noise=0.05) for _ in range(n)]


def room_half_clones(rng, n=20):
    out = [NoisyRegimeContrarian(window=int(rng.integers(30, 90)), noise=0.1)
           for _ in range(n // 2)]
    out += [random_pick(rng) for _ in range(n - n // 2)]
    return out


def room_herd_long(rng, n=20):
    """A room that reads the 8/13 asymmetry and piles long at a low threshold."""
    return [ThresholdHerder(w=int(rng.integers(5, 15)), thresh=0.55) for _ in range(n)]


def room_coin_flip(rng, n=20):
    """No edge exists. Any apparent signal is noise, so trading should stop."""
    return [BiasedRandom(p_long=0.5, p_flat=0.0) for _ in range(n)]


def room_cyclic(rng, n=20):
    return [AlternatorK(k=int(rng.integers(2, 5)), offset=i) for i in range(n)]


def room_tiny(rng):
    """Five opponents: our single vote decides the day most of the time."""
    return [random_pick(rng) for _ in range(5)]


def room_mostly_abstain(rng, n=20):
    """Most teams skip the instrument they cannot backtest."""
    from opponents import LateEntrant
    return [LateEntrant(start=400) for _ in range(n - 3)] + [random_pick(rng) for _ in range(3)]


ADVERSARIAL = [
    ("all clones (n=20)", room_all_clones),
    ("half clones (n=20)", room_half_clones),
    ("herds long (n=20)", room_herd_long),
    ("pure coin flip (n=20)", room_coin_flip),
    ("cyclic (n=20)", room_cyclic),
    ("tiny room (n=5)", room_tiny),
    ("mostly abstains (n=20)", room_mostly_abstain),
]

which = sys.argv[1] if len(sys.argv) > 1 else "adv"
out = {}

if which == "adv":
    print("=" * 132)
    print("STAGE 3a  ADVERSARIAL ROOMS  (120 seeds each)")
    print("=" * 132)
    print(HEAD)
    print(RULE)
    for label, builder in ADVERSARIAL:
        row = evaluate(lambda: candidate(), 120, SEEDS["adversarial"], room_builder=builder)
        out["candidate/" + label] = row
        print(fmt(label, row))
    print(RULE)
    print("  same rooms, baselines for comparison")
    print(RULE)
    for label, builder in ADVERSARIAL:
        row = evaluate(lambda: AlwaysLong(), 120, SEEDS["adversarial"], room_builder=builder)
        out["always-long/" + label] = row
        print(fmt("  always-long: " + label, row))
    for label, builder in ADVERSARIAL:
        row = evaluate(lambda: FloorOnly(), 120, SEEDS["adversarial"], room_builder=builder)
        out["floor-only/" + label] = row
        print(fmt("  floor-only:  " + label, row))
    save("adversarial", out)

elif which == "selfplay":
    print("=" * 132)
    print("STAGE 3b  SELF-PLAY: exact copies of the candidate added to a 20-team room")
    print("=" * 132)
    print(HEAD)
    print(RULE)
    for c in [0, 1, 2, 3, 5, 8, 12, 19]:
        def builder(rng, c=c):
            others = [random_pick(rng) for _ in range(max(0, 20 - c))]
            return others + [candidate() for _ in range(c)]
        row = evaluate(lambda: candidate(), 120, SEEDS["selfplay"], room_builder=builder)
        out[str(c)] = row
        print(fmt(f"{c} clones", row))
    save("selfplay", out)

elif which == "size":
    print("=" * 132)
    print("STAGE 3c  ROOM SIZE SWEEP  (held-out mix, fixed opponent count)")
    print("=" * 132)
    print(HEAD)
    print(RULE)
    for n in [3, 5, 10, 20, 40, 80]:
        row = evaluate(lambda: candidate(), 120, SEEDS["roomsize"],
                       room_kwargs={"min_size": n, "max_size": n})
        out[str(n)] = row
        print(fmt(f"{n} opponents", row))
    save("roomsize", out)
