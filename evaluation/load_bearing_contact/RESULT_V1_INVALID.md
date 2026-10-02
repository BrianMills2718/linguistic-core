# PhysioNet v1 reference-independence audit

## Result

The preregistered PhysioNet v1 design is **invalid as an external validation experiment**.

All 18 selected `GaCo*_01.txt` recordings were downloaded and verified against
the published PhysioNet SHA-256 manifest. Across **218,142 rows**, the per-foot
"total force" channels are numerically equal to the sums of the eight individual
per-foot force sensors to floating-point roundoff.

Observed maximum absolute differences:

- left foot: `2.2737367544323206e-13 N`
- right foot: `2.2737367544323206e-13 N`

Rows with absolute difference greater than `1e-9 N`:

- left: **0**
- right: **0**

The preregistered inference rule defined per-sample force as the sum of those
eight individual sensors. Therefore the proposed "withheld total-force
reference" is not an independent measurement target for that rule. Applying
the same 20/100 N classification bands to both sides would test an algebraic
identity rather than sensor-to-semantic generalization.

## What was not done

- The v1 thresholds were not changed.
- Held-out outcomes were not used to tune anything.
- Perfect or near-perfect classification metrics are **not** reported as a
  grounding result.
- The v1 plan is not rewritten after inspection.

## What this establishes

The failure is useful process evidence:

> Reference-channel independence must be audited before semantic scoring.

The acquisition/hashing path worked, but this dataset/configuration cannot
supply the independent reference that the second grounding-family experiment
requires.

The replacement protocol is preregistered in
`experiment_plan_v2.json`, using pressure-insole signals as inference input and
independently derived optoelectronic gait events as the primary contact
reference.
