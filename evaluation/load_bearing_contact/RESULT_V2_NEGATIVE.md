# Yareta foot-ground contact v2 — negative result

## Status

**Completed negative result.**

The preregistered v2 protocol executed successfully, but it does **not** provide
evidence for a robust pressure-to-foot-ground-contact grounding factor.

The protocol in `experiment_plan_v2.json` was not changed after data
inspection.

## Source and acquisition

Yareta / University of Geneva:

- *Human gait and other movements - markers / inertial sensors / pressure
  insoles / force plates*
- DOI: `10.26037/yareta:xkxgaw6ewjdhfntdhtj7upepxy`
- CC BY 4.0

The public archive is a standard ZIP served through a range-capable public
download endpoint.

The exact preregistered selection was acquired by byte range rather than by
downloading the full archive:

- archive size: **2,760,098,341 bytes**
- archive entries: **775**
- selected paired trials: **126**
- selected files: **252**
- selected uncompressed bytes: **321,936,880**
- selected compressed payload: **169,830,263 bytes**
- every selected file passed ZIP CRC and Yareta SHA-256 verification
- selection SHA-256:
  `0cdcc0ca7774648cfd189a9f00c39c49edd6ba036dd39346766e7447fffbe594`

## Reference independence

Inference uses only the 16 pressure channels for the evaluated foot.

Primary reference labels come from the source-authored C3D `EVENT` records:

- `Foot Strike`
- `Foot Off`
- `Left` / `Right` context

The associated paper states that these walking events were derived from
optoelectronic marker trajectories and visually checked/corrected; force
plates and the insole event detector were not used to construct them.

This preserves the evidence/reference independence that the PhysioNet v1
experiment lacked.

## Alignment audit

All **126/126** selected CSV/C3D trial pairs passed structural alignment:

- synchronized CSV rows = C3D point frames
- point rate = **100 Hz**
- source `EVENT` group present
- only expected Foot Strike / Foot Off labels
- only Left / Right event contexts
- exactly 16 pressure channels per foot

Three trials use a nonzero C3D `first_frame`:

- `P06_S01_FastGait_02`: 59 frames / 0.59 s
- `P06_S01_Gait_01`: 31 frames / 0.31 s
- `P07_S01_Gait_04`: 45 frames / 0.45 s

Their event times map unambiguously to synchronized CSV samples using the C3D
frame origin:

```text
adjusted_event_time = EVENT_time - first_frame / frame_rate
```

No heuristic time shift was introduced.

## Preregistered reference construction

v2 used:

- 200 ms non-overlapping windows
- a 150 ms exclusion margin around every event boundary
- stance = Foot Strike -> following Foot Off
- swing = Foot Off -> following Foot Strike
- a window is scored only if the entire window lies outside the exclusion
  margins

This rule turned out to be very conservative.

Calibration reference windows:

- contact: **492**
- no-contact: **3**
- reference-ambiguous / excluded by boundary rule: **2,337**

Held-out reference windows:

- contact: **271**
- no-contact: **9**
- reference-ambiguous / excluded by boundary rule: **1,186**

The extreme no-contact scarcity was not corrected after inspection.

## Calibration

Calibration participants:

`P02, P04, P05, P07, P08, P10`

The frozen threshold grid selected center:

`0.45`

Calibration balanced accuracy with refusals counted incorrect:

`0.7530487805`

Calibration coverage:

`0.9515151515`

Only **3** no-contact calibration windows contributed to that selection, so the
calibration objective was poorly supported on the negative class.

## Held-out result

Held-out participants:

`P03, P06, P09`

Primary metrics:

- scored reference windows: **280**
- coverage: **91.79%**
- balanced accuracy, refusals counted incorrect: **50.47%**
- overall accuracy, refusals counted incorrect: **45.71%**
- accuracy on covered windows: **49.81%**
- false contact predictions: **4**
- false no-contact predictions: **125**
- refusals: **23**

Predictions:

- contact: **127**
- no-contact: **130**
- refusal: **23**

Reference labels:

- contact: **271**
- no-contact: **9**

The dominant error is therefore not false contact. It is incorrectly calling
many optoelectronically referenced contact windows **no contact**.

## Robustness

### Sensor-order permutation

Reversing the order of all 16 pressure channels produced:

- prediction changes: **0 / 280**
- maximum feature drift: **0.0**

This expected invariance passed.

### Single-sensor dropout

Each of the 16 pressure sensors was separately zeroed on held-out data without
retuning.

Across the 16 dropout runs:

- balanced accuracy ranged from approximately **0.390 to 0.507**
- coverage ranged from approximately **0.896 to 0.932**
- false no-contact predictions remained high (**123-138**)

No dropout condition rescues the baseline result.

## Interpretation

v2 fails its substantive grounding gate.

The current evidence does not justify the claim that the preregistered
pressure feature and calibration procedure robustly recover independent
foot-ground contact evidence across held-out participants.

Two facts are especially important:

1. The reference is now genuinely independent of the pressure inference
   channel, so this is a meaningful failure rather than a tautology.
2. The preregistered 150 ms margin plus 200 ms window created a severe
   reference-class imbalance, leaving only three calibration no-contact
   windows.

The result does not by itself establish whether the dominant limitation is the
reference-window design, the normalized summed-pressure feature, participant
variation, or a combination.

## Stop rule

No v2 threshold, margin, window size, normalization rule, participant split, or
objective is changed after seeing this result.

Any material redesign requires:

- a separately versioned experiment plan; and
- **fresh evaluation data** not already used as v2 held-out evidence.

The v2 held-out participants must not be silently reused as confirmatory test
data for a post-hoc v3 rule.
