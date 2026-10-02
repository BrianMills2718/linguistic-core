# UCI posture grounding probe

This directory is an **evaluation-only** probe for the lowest seam in the
semantic-grounding work:

```text
raw inertial measurements
    -> low-level motion/stability factors
    -> uncertainty
    -> narrow semantic evidence class
```

It is not an activity-recognition model and does not define the meanings of
`sit`, `support`, `object`, or any other Linguistic Core predicate.

## Dataset and provenance

The probe uses UCI dataset 341, **Smartphone-Based Recognition of Human
Activities and Postural Transitions**, DOI `10.24432/C54G7M`.

The pinned archive used for the recorded result is:

```text
SHA-256
4ac4ae064227c07045a99551876b54d204837e995e298b6488559e209b3deb09
```

The bundled dataset README is treated as authoritative for file semantics:

- raw files are under `RawData/`;
- accelerometer rows are triaxial values in g;
- gyroscope rows are triaxial values in rad/s;
- rows are recorded at 50 Hz;
- `RawData/labels.txt` columns 4 and 5 are **sample indices**, not seconds;
- activities 4-6 are static postures;
- activities 1-3 are dynamic activities;
- activities 7-12 are postural transitions.

The evaluator uses the dataset's published subject partition, rather than
inventing a new split:

- train/calibration: 1, 3, 5, 6, 7, 8, 11, 14, 15, 16, 17, 19, 21, 22, 23,
  25, 26, 27, 28, 29, 30
- held-out test: 2, 4, 9, 10, 12, 13, 18, 20, 24

For each labeled segment, the evaluator takes one deterministic central window
of at most 128 synchronized samples. Activity labels are used only to calibrate
thresholds on training subjects and to score held-out predictions. The
prediction functions do not receive an activity ID or posture hint.

## Licensing caution

There is a source-level licensing discrepancy.

- The current UCI catalog page states that dataset 341 is licensed **CC BY
  4.0**:
  https://archive.ics.uci.edu/dataset/341/smartphone%2Bbased%2Brecognition%2Bof%2Bhuman%2Bactivities%2Band%2Bpostural%2Btransitions
- The `README.txt` bundled inside the pinned archive states that any commercial
  use is prohibited.

This probe does not try to resolve that conflict. To stay conservative, the
repository commits no archive bytes and no extracted raw sensor rows. The
committed report contains only aggregate metrics and bounded source
provenance (experiment, subject, activity, and sample ranges).

Place the official archive at:

```text
evaluation/uci_posture_grounding/.cache/uci341.zip
```

The local cache is intentionally gitignored.

## What is inferred

The output vocabulary is intentionally small:

- `stable_posture_evidence`
- `motion_or_transition_evidence`
- `REFUSAL:uncertain`

For scoring only, static activities 4-6 map to the stable reference class.
Dynamic activities 1-3 and transitions 7-12 map to the non-static reference
class. Dynamic and transition results are also reported separately.

The rotation-invariant path uses two deliberately simple factors:

1. standard deviation of acceleration-vector magnitude; and
2. RMS angular-speed-vector magnitude.

Thresholds are derived only from official training subjects using fixed,
predeclared quantiles:

- 90th percentile of static training examples as upper stability thresholds;
- 25th percentile of non-static training examples as lower motion thresholds.

If both rules fire, or neither rule fires, the evaluator refuses with
`REFUSAL:uncertain`.

## Axis-dependent diagnostic baseline

The baseline uses the same motion factors but retains the earlier assumption
that a candidate stable window should have mean Z acceleration near +1 g.

The real data show that assumption is inappropriate here:

- only 2/365 held-out windows satisfy the +Z gate;
- only 1/108 held-out static windows is accepted as stable by the baseline;
- baseline coverage is 248/365 = 67.9%.

This is a reference-frame failure, not evidence that the underlying posture is
unstable.

## Rotation-invariant result

On the official held-out subjects, the invariant path produced:

- total windows: 365
- coverage: 338/365 = 92.6%
- covered accuracy on the **collapsed stable vs non-static target**: 338/338
- static: 91 stable, 17 uncertain, 0 motion (108 total)
- dynamic: 149 motion, 0 uncertain, 0 stable (149 total)
- transition: 98 motion, 10 uncertain, 0 stable (108 total)

There were no false stable/non-static classifications among covered windows.
That should not be read as general activity-recognition accuracy: the target is
coarse, thresholds are intentionally conservative, and 27 windows are refused.

See `evaluation_report.json` for exact thresholds, confusion matrices, and
bounded failure provenance.

## Minimal invariance check

The evaluator applies deterministic 90-degree proper rotations around X, Y,
and Z to held-out synchronized accelerometer and gyroscope samples without
recalibration.

The vector-magnitude factors change only at floating-point roundoff
(`<= 2.3e-16` in the pinned run), and invariant predictions are unchanged in
all 1,095 rotated comparisons.

This is the useful part of the Bronstein/geometric-learning connection for the
current project: **state and test which transformations should preserve a
grounding factor**. No GNN, equivariant neural architecture, or new semantic
layer is introduced.

## Reproduce

With the pinned archive in `.cache/uci341.zip`:

```bash
python3 evaluation/uci_posture_grounding/evaluate.py
pytest -q tests/evaluation/test_uci_posture_grounding.py
```

The evaluator rewrites `evaluation_report.json` deterministically.
