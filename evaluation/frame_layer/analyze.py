"""Report frame-layer accuracy and confidence calibration from judged.jsonl."""
from __future__ import annotations
import collections, json, statistics
from pathlib import Path

rows = [json.loads(l) for l in (Path(__file__).parent / "judged.jsonl").read_text().splitlines() if l.strip()]
n = len(rows)
rel = collections.Counter(r["relation"] for r in rows)
inc = rel["incompatibleWith"]
exact = rel["exactMatch"]

def spearman(xs, ys):
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[s[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")

conf = [r["assigner_confidence"] for r in rows]
usable = [0 if r["relation"] == "incompatibleWith" else 1 for r in rows]
exactv = [1 if r["relation"] == "exactMatch" else 0 for r in rows]

print(f"n={n}  cost=${sum(r.get('cost_usd') or 0 for r in rows):.4f}")
print(f"exactMatch      {exact:3d} = {100*exact/n:.1f}%")
print(f"usable (not incompatible) {n-inc:3d} = {100*(n-inc)/n:.1f}%")
print(f"incompatibleWith {inc:3d} = {100*inc/n:.1f}%")
print("\nrelation distribution:", dict(rel.most_common()))
print(f"\nSpearman rho, assigner confidence vs not-incompatible: {spearman(conf, usable):+.3f}")
print(f"Spearman rho, assigner confidence vs exactMatch:        {spearman(conf, exactv):+.3f}")
print("\nmean assigner confidence by judged relation:")
by = collections.defaultdict(list)
for r in rows:
    by[r["relation"]].append(r["assigner_confidence"])
for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
    print(f"  {k:<22} n={len(v):3d}  mean conf={statistics.mean(v):.3f}")
print("\nby confidence band:")
bands = [(0, .69), (.7, .79), (.8, .89), (.9, .99), (1.0, 1.0)]
for lo, hi in bands:
    g = [r for r in rows if lo <= r["assigner_confidence"] <= hi]
    if g:
        i = sum(1 for r in g if r["relation"] == "incompatibleWith")
        print(f"  {lo:.2f}-{hi:.2f}  n={len(g):3d}  incompatible={100*i/len(g):.0f}%")
