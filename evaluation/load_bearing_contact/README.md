# Load-bearing contact grounding probe

This directory contains the second external-data grounding-family work.

**v1 is retained as a failed preregistration.** After the selected PhysioNet
recordings were acquired, the proposed per-foot total-force reference was found
to be exactly the sum of the eight individual sensor inputs to floating-point
roundoff across every scanned row. See `RESULT_V1_INVALID.md` and
`reference_independence_audit_v1.json`.

The replacement independent-reference protocol is preregistered in
`experiment_plan_v2.json` before its dataset is downloaded.

The target is deliberately **not** the full lexical/ontological relation `support`.
It is one lower-level factor beneath support:

```text
distributed vertical force measurements
    -> sustained load-bearing contact evidence
```

The experiment plan is frozen in `experiment_plan_v1.json` **before any selected
recording rows are downloaded or evaluated**.

## Data source

PhysioNet: **Gait in Parkinson's Disease v1.0.0**

- DOI: `10.13026/C24H3N`
- license: Open Data Commons Attribution License v1.0
- dataset: https://physionet.org/content/gaitpdb/1.0.0/
- format: https://physionet.org/content/gaitpdb/1.0.0/format.txt
- SHA-256 manifest: https://physionet.org/files/gaitpdb/1.0.0/SHA256SUMS.txt

The published format provides, at 100 Hz:

- eight vertical ground-reaction-force sensors beneath the left foot;
- eight beneath the right foot;
- a recorded total-force channel for each foot.

Only the 18 `GaCo*_01.txt` healthy-control normal-walk recordings listed and
hashed in the plan are selected. No disease-classification target is used.

## Evidence separation

For one foot and one 200 ms non-overlapping window:

- **inference input:** the eight individual VGRF sensors;
- **withheld physical reference:** the recorded total-force channel;
- **output:** one of:
  - `load_bearing_contact_evidence`
  - `no_load_bearing_contact_evidence`
  - `REFUSAL:transition_or_uncertain`

The total-force reference channel is never an inference input.

Clinical labels, demographics, and disease severity are out of scope.

## Frozen v1 rules

Before observing outcomes:

- window: 20 samples = 200 ms;
- no-load bound: <= 20 N;
- load-bearing bound: >= 100 N;
- persistence requirement: at least 80% of samples in the window satisfy the
  relevant force bound;
- otherwise refuse.

The inference-side per-sample force is the sum of the eight individual sensor
forces for that foot. The physical reference uses the separately recorded
per-foot total-force channel with the same temporal band rule.

These are **operational bounds, not universal definitions**. They are not to be
changed after seeing results. If they fail, v1 records the failure and any
alternative must be a new version.

## Predeclared split

Held out:

`GaCo04, GaCo08, GaCo12, GaCo16`

Calibration-only:

`GaCo01, GaCo02, GaCo03, GaCo05, GaCo06, GaCo07, GaCo09, GaCo10,
GaCo11, GaCo13, GaCo14, GaCo15, GaCo17, GaCo22`

The v1 numeric thresholds are fixed rather than fitted, but the split is still
retained for any diagnostics and for consistency with the project's
calibration/evaluation discipline.

## Robustness expectations

- sensor-order permutation: invariant;
- left/right logic: symmetric;
- single-sensor dropout: measure degradation, do not retune;
- loading/unloading bands: should preferentially refuse rather than force a
  stable contact/no-contact decision.

## Claim boundary

A successful result licenses only a bounded statement about **sustained
load-bearing contact evidence**.

It does not establish:

- metaphysical contact;
- a complete support relation;
- bearer/load role assignment;
- relative-position semantics;
- counterfactual load response;
- object persistence.

Those remain separate factors to compose later.

## Current state

- `experiment_plan_v1.json`: immutable original preregistration.
- `reference_independence_audit_v1.json`: 18 files / 218,142 rows audited;
  proposed total-force reference is algebraically derived from the inference
  sensors, so v1 is invalid for external validation.
- `RESULT_V1_INVALID.md`: human-readable failure record.
- `experiment_plan_v2.json`: replacement protocol using the University of
  Geneva/Yareta multimodal gait dataset. Pressure-insole channels are the
  inference source; optoelectronic foot-strike/foot-off events are the
  independent primary reference.

No v2 dataset rows or outcomes had been inspected when the v2 protocol was
written.

### v2 acquisition metadata

`discover_yareta_v2.py` now resolves the preregistered participant/trial scope
against Yareta's public archive-data API without reading signal contents. The
retained `acquisition_manifest_v2.json` freezes:

- **126** paired walking trials;
- **252** files: one synchronized CSV plus one raw C3D per trial;
- **321,936,880 bytes** total;
- each Yareta data-file ID, path, size and SHA-256;
- canonical selection SHA-256
  `0cdcc0ca7774648cfd189a9f00c39c49edd6ba036dd39346766e7447fffbe594`.

The manifest covers only `P02` through `P10` from the preregistered split
and only `SlowGait`, `Gait`, and `FastGait` trials. Every selected trial
has both the synchronized CSV and same-stem raw C3D reference file.

At the time of this checkpoint, Yareta's public metadata API and archive
preparation flow work. A diagnostic request to the archive-metadata per-file
path returned HTTP 500 even after a token cookie, but the current DLCM 3.1.9
Access OpenAPI does **not** define per-file binary download under
`/access/metadata/{archive}/data/{file}`. It defines per-file binary download
under prepared DIP resources and documents public anonymous dissemination at
the archive level.

See `yareta_access_diagnostic_v1.json`. The remaining least-invasive check is
one 1 KiB archive-level Range GET against the documented public download
endpoint. The authorized machine went offline before that request could be
issued. No v2 signal rows have therefore been downloaded or scored, and the
preregistered dataset/protocol remain unchanged.
