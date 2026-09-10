"""Resumable shard runner. Each invocation does a slice of the work and saves
it, so long Monte Carlos survive being run in short chunks."""

import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SHARDS = os.path.join(HERE, "shards")
os.makedirs(SHARDS, exist_ok=True)


def shard_path(tag, i):
    return os.path.join(SHARDS, f"{tag}_{i:04d}.npz")


def run(tag, k, count):
    out = shard_path(tag, k)
    if os.path.exists(out):
        return "skip"

    if tag.startswith("A"):
        import scenario_liferaft as S
        data = S.load_round1()
        master = np.random.default_rng(20260809 + 1000 * k)
        tot, pri, lrp, td = [], [], [], []
        clones = int(tag.split("_c")[1]) if "_c" in tag else 0
        for _ in range(count):
            rng = np.random.default_rng(master.integers(0, 2**63 - 1))
            room = S.random_room(rng)
            if clones:
                room = room + [S.CloneOfUs() for _ in range(clones)]
            p, l, d = S.run_year(data, room, rng)
            tot.append(p + l); pri.append(p); lrp.append(l)
            td.append(d["lr_days_traded"])
        np.savez(out, total=tot, price=pri, liferaft=lrp, traded=td)

    else:
        import scenario_prices as S
        d = S.load_round1()
        f = S.fit(d)
        master = np.random.default_rng(7770809 + 1000 * k)
        tot, dds, per = [], [], []
        keys = ["UQ Dollar", "Fintech Token", "Boat Party Ticket", "MenuDash",
                "Bread", "Sausage", "Sausage Sizzle", "Thrifted Jeans"]
        for _ in range(count):
            rng = np.random.default_rng(master.integers(0, 2**63 - 1))
            t, pp, br, dd = S.score(S.synth_year(f, rng))
            assert br == 0
            tot.append(t); dds.append(dd); per.append([pp[x] for x in keys])
        np.savez(out, total=tot, dd=dds, per=np.array(per), keys=keys)

    return "done"


def collect(tag):
    # The suffix must be purely the shard number. Matching on the prefix alone
    # made collect("A") swallow the clone-crowded shards A_c1_*, A_c2_* ... and
    # silently mixed 204 adversarial rooms into the 400 clean ones.
    def is_mine(f):
        if not (f.startswith(tag + "_") and f.endswith(".npz")):
            return False
        return f[len(tag) + 1:-4].isdigit()

    files = sorted(f for f in os.listdir(SHARDS) if is_mine(f))
    if not files:
        return None
    parts = [np.load(os.path.join(SHARDS, f), allow_pickle=True) for f in files]
    out = {}
    for key in parts[0].files:
        if key == "keys":
            out[key] = parts[0][key]
        else:
            out[key] = np.concatenate([p[key] for p in parts])
    return out


if __name__ == "__main__":
    tag, k0, k1, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    for k in range(k0, k1):
        print(f"  shard {tag}:{k} -> {run(tag, k, count)}", flush=True)
