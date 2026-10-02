# Measurement-to-Factor Semantic-Grounding Gate (v1)

A self-contained executable evaluation probe demonstrating deterministic factor inference from multi-channel sensory observations, without cognitive pretense or inference beyond what the evidence supports.

## Design Principle

The probe implements a narrow, verification-ready pipeline:

```
Raw observations (with timestamps, reference frames, confidence)
    ↓
Multi-channel factor inference
    ↓
Confidence & uncertainty quantification
    ↓
Semantic classification
    ↓
Refusal when evidence is insufficient
```

**Core rule:** Never infer contact, attachment, or object identity from a single sensory channel.

## What This Probe Establishes

1. **Multi-channel convergence is required for contact claims.**
   - Visual observation of occlusion (episode B1) does not establish contact.
   - Pressure + position + visual must agree within measurement tolerance.
   - A single sensor reading is below the bar for binding semantic claims.

2. **Single sensory channels cannot determine identity through occlusion.**
   - Identical pose + appearance after a 4-second occlusion (episode C2) is insufficient for identity assignment.
   - Observational continuity or alternative evidence (e.g., tracked trajectory before occlusion) is required.
   - Refusal is the correct output when evidence is insufficient.

3. **Indistinguishable instances cannot be resolved by appearance alone.**
   - Two objects with identical visual signature at different spatial locations (episode C3) cannot be collapsed into a single identity.
   - Appearance match is a necessary but not sufficient condition for identity.

4. **Transient contact is distinguishable from persistent attachment.**
   - An object resting on a surface initially (pressure sensor active) then rising (pressure drops, position increases) is not attached (episode B2).
   - Temporal analysis of multi-sensor observations can separate transient from persistent states.

5. **Deterministic, narrow rules work without claiming cognition.**
   - All classifications are built from explicitly recorded factors.
   - Confidence scores reflect convergence across independent channels, not model uncertainty.
   - No probabilistic reasoning, natural language processing, or learned weights.

## What This Probe Does NOT Establish

- **Real-time object tracking or prediction** — it processes static episode snapshots, not continuous streams.
- **Causal reasoning about object dynamics** — forces, accelerations, and interactions are not modeled.
- **Visual recognition or semantic understanding** — color histograms and pose are treated as opaque measurements.
- **Robustness to sensor noise, drift, or miscalibration** — observations are assumed truthful at reported confidence levels.
- **Generalization to new domains** — the rules are tuned for the specimen cases; other scenarios may require different factors or thresholds.
- **Cognitive plausibility** — this is not a model of human perception; it is a narrow semantic contract.

## Episodes

### Positive Case (A1): Multi-Channel Support

**Episode:** `positive_support_case_A1`

Object A rests on object B. Evidence:
- Pressure sensor: 9.7–9.8 N stable across 3 seconds (high confidence)
- Position tracker: Z-coordinate at surface height (±5mm tolerance)
- Camera overhead: No visual gap
- Accelerometer: Zero Z-acceleration (resting)

**Expected classification:** `support` (confidence 0.98)

**What it shows:** Multi-channel convergence produces high-confidence semantic binding.

---

### Adversarial Case (B1): Visual Occlusion, No Contact

**Episode:** `adversarial_obstruction_B1`

Visual appearance suggests occlusion; other channels deny contact.

Evidence:
- Camera overhead: Object A appears "on" object B (confidence 0.85, perspective artifact)
- Pressure sensor: 0 N (no contact force)
- Position tracker: Z = 0.15m, object B height = 0.1m (5cm gap)
- 3D stereo camera: Confirms 5cm gap (confidence 0.89)

**Expected classification:** `visual_occlusion_not_support` (confidence 0.97)

**What it shows:** Single-channel evidence (visual) is insufficient and can be overridden by converging multi-channel refutation.

---

### Adversarial Case (B2): Transient Contact, Not Attachment

**Episode:** `adversarial_attachment_B2`

Initial contact followed by independent motion; tests whether agents mistake transient co-location for attachment.

Evidence:
- T=100ms: Pressure sensor 9.8 N, visual contact present
- T=2500ms: Pressure sensor drops to 0 N
- T=3000ms: Position tracker shows A risen to 0.25m (15cm above B)
- T=2500ms: Velocity tracker shows A moving upward at 0.05 m/s

**Expected classification:** `transient_contact_not_attachment` (confidence 0.96)

**What it shows:** Temporal analysis of independent sensor channels can distinguish persistent attachment from transient co-location.

---

### Positive Case (C1): Persistent Pose Under Perturbation

**Episode:** `posture_persistence_case_C1`

Object C maintains identical pose and color signature over 10 seconds, including environmental perturbation (wind gust at T=3s).

Evidence:
- Pose estimator: (1.0, 2.0, 0.1) quaternion [0,0,0,1] at T=500ms, 4000ms, 9000ms (identical)
- Color histogram: Identical signature at T=1000ms and T=5000ms
- Position: Unchanged through environmental event

**Expected classification:** `persistent_identity_stable_pose` (confidence 0.95)

**What it shows:** Pose and appearance consistency across environmental perturbations supports identity persistence.

---

### Adversarial Case (C2): Occlusion Gap > 3s, Identity Unknown

**Episode:** `adversarial_occlusion_replacement_C2`

Object disappears from view for 4 seconds, then reappears with identical pose and appearance.

Evidence:
- T=500ms: Object at (1.0, 2.0, 0.1), color=unique_id_2
- T=3000ms: Object leaves field of view (permanent occlusion)
- T=7000ms: Object reappears at (1.0, 2.0, 0.1), color=unique_id_2
- **Unobserved:** 4-second gap with no sensor coverage

**Expected classification:** `identity_unknown_insufficient_evidence` (confidence 0.99)

**What it shows:** Occlusion gaps preclude confident identity assignment, even with matching pose and appearance at re-entry. The object could have been replaced; only continuous observation or independent trajectory evidence resolves this.

---

### Adversarial Case (C3): Indistinguishable Instances

**Episode:** `adversarial_indistinguishable_duplicate_C3`

Two objects with identical appearance and pose template but at different spatial locations appear simultaneously.

Evidence:
- Left object: Position (0.5, 2.0, 0.1), color=unique_id_XYZ
- Right object: Position (1.5, 2.0, 0.1), color=unique_id_XYZ
- Both objects present at the same time
- Appearance is identical (same histogram)
- Pose template is identical (only location differs)

**Expected classification:** `multiple_indistinguishable_instances_identity_unresolvable` (confidence 0.98)

**What it shows:** Appearance match alone cannot resolve multiple co-occurring instances. Spatial grounding is unambiguous (different locations), but semantic identity cannot be assigned. The correct output is refusal, not guessing.

---

## Running the Probe

### As a standalone script

```bash
python probe_measurement_to_factor_v1.py
```

Output: Summary of all 6 episodes with classification results.

### As pytest tests

```bash
pytest test_measurement_to_factor_v1.py -v
```

Individual test cases for each episode, plus tests for factor inference correctness.

### In the repository test suite

```bash
pytest tests/ -k measurement_to_factor -v
```

(Requires the test file to be copied to `tests/evaluation/test_measurement_to_factor_v1.py` or linked.)

## Fixture Format

Episodes are stored in `specimen_fixtures_v1.json` with the following structure:

```json
{
  "episode_id": "unique_identifier",
  "episode_type": "support|obstruction|attachment|posture_persistence|posture_identity_adversarial",
  "reference_frame": "lab_coordinate_system_v1",
  "time_window": {
    "start_ms": 0,
    "end_ms": 5000,
    "stability_duration_ms": 3000
  },
  "observations": [
    {
      "obs_id": "unique_identifier",
      "channel": "pressure_sensor|camera_overhead|position_tracker|...",
      "timestamp_ms": 100,
      "value": 9.8,
      "unit": "N",
      "confidence": 0.95
    }
  ],
  "expected_classification": "support",
  "classification_confidence": 0.98,
  "expected_factors": { ... }
}
```

Channels supported:
- `pressure_sensor` — Direct contact force (Newtons)
- `camera_overhead` — Visual observation from above
- `camera_3d_stereo` — 3D depth measurement
- `camera_color` — Appearance / color histogram
- `position_tracker` — Cartesian coordinates with reference frame
- `pose_estimator` — Position + orientation (quaternion)
- `accelerometer` — Linear acceleration
- `motion_tracker` — Velocity
- `air_currents` — Environmental events (not used in classification, for context)
- `camera_visibility` — Visibility events (occlusion, field-of-view)

## Confidence Representation

Confidence scores reflect **evidence convergence**, not model uncertainty:

- **0.95–0.99:** Multi-channel agreement within measurement tolerance
- **0.90–0.94:** Primary channels agree; secondary channels consistent
- **0.85–0.89:** Single strong channel; weaker evidence from others
- **0.50–0.84:** Mixed evidence; insufficient for high-confidence binding
- **Refusal (N/A):** Evidence is contradictory or below threshold for any semantic claim

## Limitations

1. **Fixed reference frames** — The probe assumes static, calibrated reference systems. Dynamic or relative frames require additional logic.
2. **No prediction** — Episode analysis is retrospective; future state is not modeled.
3. **No learning** — Thresholds and rules are manually tuned; they do not adapt to new data.
4. **Narrow scope** — Six specimen cases cover contact, identity, and persistence but not occlusion reasoning, force dynamics, or causal inference.
5. **Deterministic only** — Useful for verification and as a semantic contract specification, not for general perception.

## Author

Claude Haiku 4.5 on behalf of Brian Mills. Probe design and specimen cases reviewed against semantic-grounding design principles in linguistic-core.

## References

- **Design:** `docs/design/SEMANTIC_PREDICATE_VOCABULARY.md` (cross-project semantic contract context)
- **Licensing:** Probe is part of linguistic-core; see `LICENSE`
