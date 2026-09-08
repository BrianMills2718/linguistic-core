# Frame-layer accuracy

Durable re-derivation of the measurement behind failure modes VF-01 and VF-10.

## Why this exists

The original 2026-09-07 measurement lived only in a session scratch directory
and was lost, so the taxonomy carried figures nobody could re-check — the exact
failure VF-13 describes. This re-runs it and keeps the artifacts in the
repository.

## Reproduce

```
python evaluation/frame_layer/judge_frame_sample.py --n 100   # ~$0.015
python evaluation/frame_layer/analyze.py
```

Sample is seeded (`SEED = 20260907`) and re-drawable. `--dry-run` draws without
spending. Judging classifies by the nine-relation mapping vocabulary rather than
correct/wrong, because a frame *broader* than the sense is imprecise rather than
an error; only `incompatibleWith` is unambiguous failure.

## Result, 2026-09-07 (n=100, $0.0144)

| | this run | original run (lost) |
|---|---|---|
| `exactMatch` | **5%** | 14% |
| usable (not incompatible) | **48%** | 39–45% |
| `incompatibleWith` | **52%** | 55–61% |
| ρ, confidence vs not-incompatible | **+0.017** | +0.11 |

Full distribution: `incompatibleWith` 52, `broaderThan` 22, `closeMatch` 15,
`narrowerThan` 6, `exactMatch` 5.

**What replicates:** the layer is roughly half incompatible, and the assigner's
confidence is uncorrelated with correctness. Both runs agree on those, which are
the two claims the design depends on.

**What does not:** `exactMatch` at 5% against 14%. The two runs used different
judge settings and cannot be reconciled because the first run's artifacts are
gone. Treat `exactMatch` as unstable between judges and the incompatible rate as
the reliable figure.

**Confidence is not merely uninformative, it is flat.** Incompatible rate by the
assigner's own confidence band: 58% below 0.70, 65% at 0.70–0.79, 38% at
0.80–0.89, 53% at 0.90–0.99, and 53% at exactly 1.00. No threshold helps. Mean
confidence by judged relation runs 0.774 for `incompatibleWith` against 0.900 for
`exactMatch` — a real gap, but on n=5.

## Caveat

A model judging another model's output. The original run mitigated this with ten
blind hand-checks and an adversarial defence pass; this re-derivation did not
repeat those, so it establishes reproducibility of the headline rate rather than
independent ground truth.
