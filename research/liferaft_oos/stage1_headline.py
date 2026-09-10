"""Stage 1: headline out-of-sample table on randomly generated held-out rooms."""

from harness import HEAD, RULE, SEEDS, evaluate, fmt, save
from strategies import (AlwaysFlat, AlwaysLong, AlwaysShort, FloorOnly,
                        RegimeContrarian, candidate)

N = 300
SEED = SEEDS["headline"]

LINEUP = [
    ("always-flat", lambda: AlwaysFlat()),
    ("always-long", lambda: AlwaysLong()),
    ("always-short", lambda: AlwaysShort()),
    ("floor-option only", lambda: FloorOnly()),
    ("pooled k=0", lambda: RegimeContrarian(k=0.0, warmup=40, probe=6, pooled=True)),
    ("pooled k=2", lambda: RegimeContrarian(k=2.0, warmup=40, probe=6, pooled=True)),
    ("regime k=0 (raw)", lambda: candidate(k=0.0)),
    ("regime k=2 (CANDIDATE)", lambda: candidate()),
    ("  ...minus floor rule", lambda: candidate(use_floor=False)),
    ("  ...minus probe days", lambda: candidate(probe=0)),
    ("  ...minus warmup", lambda: candidate(warmup=0)),
]

print("=" * 132)
print(f"STAGE 1  OUT-OF-SAMPLE: {N} randomly generated held-out rooms, 365 days each")
print("=" * 132)
print(HEAD)
print(RULE)

out = {}
for label, mk in LINEUP:
    row = evaluate(mk, N, SEED)
    out[label] = row
    print(fmt(label, row))

save("headline", out)
