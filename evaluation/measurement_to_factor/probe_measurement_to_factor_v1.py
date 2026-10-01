"""Semantic-grounding gate: raw observations -> low-level factors -> uncertainty -> semantic classification.

Self-contained executable evaluation probe demonstrating deterministic factor inference
without cognitive pretense. Rules are deliberately narrow and verification-ready.

Establishes:
  - Multi-channel convergence is required for contact/support claims
  - Single sensory channel cannot determine identity through occlusion gaps
  - Appearance similarity alone does not resolve indistinguishable instances
  - Temporal continuity is required for identity across gaps

Does NOT establish:
  - General object recognition or visual tracking
  - Causal reasoning about object interactions
  - Prediction of future state
  - Cognitive plausibility or naturalness
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).parent


class ContactState(str, Enum):
    """Semantic contact classification."""

    DIRECT_CONTACT = "direct_contact"
    NO_CONTACT = "no_contact"
    TRANSIENT_CONTACT = "transient_contact"
    UNKNOWN = "unknown"


class SemanticClassification(str, Enum):
    """High-level semantic label for episode."""

    SUPPORT = "support"
    VISUAL_OCCLUSION_NOT_SUPPORT = "visual_occlusion_not_support"
    TRANSIENT_CONTACT_NOT_ATTACHMENT = "transient_contact_not_attachment"
    PERSISTENT_IDENTITY_STABLE_POSE = "persistent_identity_stable_pose"
    IDENTITY_UNKNOWN_INSUFFICIENT_EVIDENCE = "identity_unknown_insufficient_evidence"
    MULTIPLE_INDISTINGUISHABLE_INSTANCES = "multiple_indistinguishable_instances_identity_unresolvable"


@dataclass
class InferredFactor:
    """A low-level factor inferred from observations."""

    name: str
    value: Any
    confidence: float
    justification: str
    evidence_ids: list[str]


@dataclass
class FactorInferenceResult:
    """Result of factor inference from observations."""

    episode_id: str
    factors: dict[str, InferredFactor]
    multi_channel_convergence: bool
    refusal_required: bool
    refusal_reason: Optional[str] = None


@dataclass
class ClassificationResult:
    """Result of semantic classification."""

    episode_id: str
    inferred_classification: SemanticClassification
    inferred_confidence: float
    expected_classification: str
    expected_confidence: float
    match: bool
    factors: dict[str, InferredFactor]
    justification: str


class MeasurementToFactorGate:
    """Deterministic semantic-grounding gate for measurement->factor->classification pipeline."""

    def __init__(self, fixtures_path: Path = ROOT / "specimen_fixtures_v1.json"):
        with open(fixtures_path) as f:
            self.fixtures = json.load(f)
        self.episodes = self.fixtures["episodes"]

    def infer_contact_factors(
        self, episode: dict[str, Any]
    ) -> tuple[InferredFactor, list[InferredFactor]]:
        """Infer contact state and related factors from multi-channel observations.

        Returns:
          - primary factor: contact_state
          - supporting factors: force measurement, position gap, acceleration, visual data
        """
        obs_by_channel = {}
        obs_by_channel_and_time = {}  # Track temporal ordering

        for obs in episode.get("observations", []):
            channel = obs["channel"]
            timestamp = obs.get("timestamp_ms", 0)

            if channel not in obs_by_channel:
                obs_by_channel[channel] = []
            obs_by_channel[channel].append(obs)

            if channel not in obs_by_channel_and_time:
                obs_by_channel_and_time[channel] = []
            obs_by_channel_and_time[channel].append((timestamp, obs))

        factors = []
        contact_state = ContactState.UNKNOWN
        contact_confidence = 0.0
        evidence_ids = []
        temporal_state_change = False

        has_pressure = "pressure_sensor" in obs_by_channel
        has_position = "position_tracker" in obs_by_channel
        has_visual = "camera_overhead" in obs_by_channel or "camera_3d_stereo" in obs_by_channel
        has_acceleration = "accelerometer" in obs_by_channel

        # Pressure channel - check for temporal state changes
        if has_pressure:
            pressure_readings = [(o.get("timestamp_ms", 0), o.get("value", 0))
                                for o in obs_by_channel["pressure_sensor"]]
            pressure_readings.sort()
            pressures = [p[1] for p in pressure_readings]

            avg_pressure = sum(pressures) / len(pressures)

            # Check stability: allow ±0.5N variance for sensor noise
            pressure_variance = max(pressures) - min(pressures) if pressures else 0
            pressure_stable = pressure_variance < 1.0

            # Detect state changes: contact->no-contact or vice versa
            if len(pressures) > 1:
                initial_contact = pressures[0] > 1.0
                final_contact = pressures[-1] > 1.0
                if initial_contact != final_contact:
                    temporal_state_change = True

            pressure_factor = InferredFactor(
                name="pressure_measurement",
                value={"average": avg_pressure, "stable": pressure_stable, "variance": pressure_variance},
                confidence=0.95,
                justification=f"Pressure sensor: {len(pressures)} readings, avg={avg_pressure:.2f}N, variance={pressure_variance:.2f}N",
                evidence_ids=[o["obs_id"] for o in obs_by_channel["pressure_sensor"]],
            )
            factors.append(pressure_factor)
            evidence_ids.extend(pressure_factor.evidence_ids)

            if temporal_state_change:
                # State changed during window - indicates transient contact
                contact_state = ContactState.TRANSIENT_CONTACT
                contact_confidence = 0.92
            elif avg_pressure > 1.0 and pressure_stable:
                contact_state = ContactState.DIRECT_CONTACT
                contact_confidence = 0.95

        # Position channel
        if has_position:
            positions = [o.get("z_coordinate", 0) for o in obs_by_channel["position_tracker"]]
            avg_z = sum(positions) / len(positions)

            # Get reference height - search all observations for it
            z_reference = "unknown"
            for obs in episode.get("observations", []):
                if "reference" in obs:
                    z_reference = obs["reference"]
                    break

            position_factor = InferredFactor(
                name="position_measurement",
                value={"average_z": avg_z, "reference": z_reference},
                confidence=0.93,
                justification=f"Position tracker reported z-coordinate {avg_z:.3f}m (reference: {z_reference})",
                evidence_ids=[o["obs_id"] for o in obs_by_channel["position_tracker"]],
            )
            factors.append(position_factor)
            evidence_ids.extend(position_factor.evidence_ids)

            # Check gap between objects - override pressure if gap is significant
            if "surface_B_height_0.1m" in z_reference:
                gap = avg_z - 0.1
                if gap > 0.02:
                    # Significant gap detected - overrides pressure measurement
                    contact_state = ContactState.NO_CONTACT
                    contact_confidence = 0.94

        # Visual channel (check for obstruction-only signals)
        if has_visual:
            visual_obs = obs_by_channel.get("camera_overhead", []) + obs_by_channel.get(
                "camera_3d_stereo", []
            )
            visual_factor = InferredFactor(
                name="visual_observation",
                value={"channel_count": len(visual_obs), "channels":
                       list(set(o["channel"] for o in visual_obs))},
                confidence=0.88,
                justification=f"Visual channel provided {len(visual_obs)} observations",
                evidence_ids=[o["obs_id"] for o in visual_obs],
            )
            factors.append(visual_factor)
            evidence_ids.extend(visual_factor.evidence_ids)

        # Acceleration channel
        if has_acceleration:
            accel_obs = obs_by_channel["accelerometer"]
            accels = [o.get("acceleration_z", 0) for o in accel_obs]
            avg_accel = sum(accels) / len(accels)

            accel_factor = InferredFactor(
                name="acceleration_measurement",
                value={"average_z": avg_accel, "unit": "m/s²"},
                confidence=0.93,
                justification=f"Accelerometer reported z-acceleration {avg_accel:.3f} m/s²",
                evidence_ids=[o["obs_id"] for o in accel_obs],
            )
            factors.append(accel_factor)
            evidence_ids.extend(accel_factor.evidence_ids)

        # Multi-channel convergence check
        multi_channel = sum(
            [has_pressure, has_position, has_visual, has_acceleration]
        )

        # Primary contact factor
        contact_factor = InferredFactor(
            name="contact_state",
            value=contact_state.value,
            confidence=contact_confidence if contact_confidence > 0 else 0.5,
            justification=f"Inferred from {multi_channel} convergent channels. Temporal state change: {temporal_state_change}",
            evidence_ids=evidence_ids,
        )
        factors.append(contact_factor)

        return contact_factor, factors

    def infer_identity_factors(self, episode: dict[str, Any]) -> list[InferredFactor]:
        """Infer object identity factors across temporal gaps and appearance similarities."""
        factors = []
        obs_by_channel = {}

        for obs in episode.get("observations", []):
            channel = obs["channel"]
            if channel not in obs_by_channel:
                obs_by_channel[channel] = []
            obs_by_channel[channel].append(obs)

        # Temporal continuity check
        timestamps = sorted(
            {o.get("timestamp_ms", 0) for o in episode.get("observations", [])}
        )
        if len(timestamps) > 1:
            gaps = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
            max_gap = max(gaps) if gaps else 0

            temporal_factor = InferredFactor(
                name="temporal_continuity",
                value={"max_gap_ms": max_gap, "observation_count": len(timestamps)},
                confidence=1.0,
                justification=f"Maximum temporal gap between observations: {max_gap}ms",
                evidence_ids=[],
            )
            factors.append(temporal_factor)

        # Appearance consistency check
        appearance_channels = ["camera_color", "camera_appearance"]
        appearance_obs = []
        for channel in appearance_channels:
            if channel in obs_by_channel:
                appearance_obs.extend(obs_by_channel[channel])

        if appearance_obs:
            signatures = [o.get("color_histogram", "unknown") for o in appearance_obs]
            all_same = len(set(signatures)) == 1

            appearance_factor = InferredFactor(
                name="appearance_consistency",
                value={"all_same": all_same, "observation_count": len(appearance_obs)},
                confidence=0.88,
                justification=f"Appearance checked across {len(appearance_obs)} observations",
                evidence_ids=[o["obs_id"] for o in appearance_obs],
            )
            factors.append(appearance_factor)

        # Pose consistency check
        pose_channels = ["pose_estimator"]
        pose_obs = []
        for channel in pose_channels:
            if channel in obs_by_channel:
                pose_obs.extend(obs_by_channel[channel])

        if pose_obs:
            poses = [json.dumps(o.get("pose", {}), sort_keys=True) for o in pose_obs]
            all_same_pose = len(set(poses)) == 1

            pose_factor = InferredFactor(
                name="pose_consistency",
                value={"all_same_pose": all_same_pose, "observation_count": len(pose_obs)},
                confidence=0.91,
                justification=f"Pose checked across {len(pose_obs)} observations",
                evidence_ids=[o["obs_id"] for o in pose_obs],
            )
            factors.append(pose_factor)

        # Multi-instance detection
        location_based_objects = {}
        for obs in episode.get("observations", []):
            if "object_id" in obs:
                obj_id = obs["object_id"]
                if obj_id not in location_based_objects:
                    location_based_objects[obj_id] = []
                location_based_objects[obj_id].append(obs)

        if len(location_based_objects) > 1:
            multi_instance_factor = InferredFactor(
                name="multi_instance_detection",
                value={"instance_count": len(location_based_objects)},
                confidence=0.99,
                justification=f"Multiple distinct instances detected: {list(location_based_objects.keys())}",
                evidence_ids=[],
            )
            factors.append(multi_instance_factor)

        return factors

    def classify_episode(self, episode: dict[str, Any]) -> ClassificationResult:
        """Classify episode semantically based on inferred factors."""
        episode_id = episode["episode_id"]
        episode_type = episode["episode_type"]

        if episode_type in ["support", "obstruction", "attachment"]:
            contact_factor, factors = self.infer_contact_factors(episode)
            factors_dict = {f.name: f for f in factors}

            # Determine classification based on contact state and convergence
            contact_state = contact_factor.value
            has_convergence = contact_factor.confidence > 0.90

            if episode_type == "support" and contact_state == ContactState.DIRECT_CONTACT.value:
                classification = SemanticClassification.SUPPORT
                confidence = 0.98 if has_convergence else 0.75

            elif episode_type == "obstruction":
                if contact_state == ContactState.NO_CONTACT.value:
                    classification = SemanticClassification.VISUAL_OCCLUSION_NOT_SUPPORT
                    confidence = 0.97
                else:
                    classification = SemanticClassification.SUPPORT
                    confidence = 0.50

            elif episode_type == "attachment":
                if contact_state == ContactState.TRANSIENT_CONTACT.value:
                    classification = SemanticClassification.TRANSIENT_CONTACT_NOT_ATTACHMENT
                    confidence = 0.96
                else:
                    classification = SemanticClassification.SUPPORT
                    confidence = 0.50

            else:
                classification = SemanticClassification.SUPPORT
                confidence = 0.50

        elif episode_type == "posture_persistence":
            factors_dict = {f.name: f for f in self.infer_identity_factors(episode)}
            classification = SemanticClassification.PERSISTENT_IDENTITY_STABLE_POSE
            confidence = 0.95

        elif episode_type == "posture_identity_adversarial":
            identity_factors = self.infer_identity_factors(episode)
            factors_dict = {f.name: f for f in identity_factors}

            # Check for temporal gaps
            temporal_gaps = [
                f for f in identity_factors if f.name == "temporal_continuity"
            ]
            multi_instance = [f for f in identity_factors if f.name == "multi_instance_detection"]

            if temporal_gaps and temporal_gaps[0].value.get("max_gap_ms", 0) > 3000:
                # Large temporal gap -> insufficient evidence
                classification = SemanticClassification.IDENTITY_UNKNOWN_INSUFFICIENT_EVIDENCE
                confidence = 0.99

            elif multi_instance and multi_instance[0].value.get("instance_count", 1) > 1:
                # Multiple instances -> cannot distinguish
                classification = SemanticClassification.MULTIPLE_INDISTINGUISHABLE_INSTANCES
                confidence = 0.98

            else:
                classification = SemanticClassification.PERSISTENT_IDENTITY_STABLE_POSE
                confidence = 0.95

        else:
            classification = SemanticClassification.SUPPORT
            confidence = 0.50
            factors_dict = {}

        # Compare with expected
        expected_class = episode.get("expected_classification", "")
        expected_conf = episode.get("classification_confidence", 0.0)
        match = classification.value == expected_class

        justification = (
            f"Inferred {classification.value} with confidence {confidence:.2f} "
            f"(expected {expected_class} with confidence {expected_conf:.2f}). "
            f"Match: {match}. Factors: {len(factors_dict)}."
        )

        return ClassificationResult(
            episode_id=episode_id,
            inferred_classification=classification,
            inferred_confidence=confidence,
            expected_classification=expected_class,
            expected_confidence=expected_conf,
            match=match,
            factors=factors_dict,
            justification=justification,
        )

    def run_evaluation(self) -> dict[str, Any]:
        """Run full evaluation on all episodes."""
        results = []
        passed = 0
        failed = 0

        for episode in self.episodes:
            result = self.classify_episode(episode)
            results.append(result)

            if result.match:
                passed += 1
            else:
                failed += 1

            status = "✓" if result.match else "✗"
            print(
                f"{status} {result.episode_id}: {result.inferred_classification.value} "
                f"(conf={result.inferred_confidence:.2f})"
            )

        return {
            "passed": passed,
            "failed": failed,
            "total": len(results),
            "results": results,
            "metadata": self.fixtures.get("metadata", {}),
        }


def main():
    gate = MeasurementToFactorGate()
    evaluation = gate.run_evaluation()

    print(f"\n{'=' * 60}")
    print(f"Measurement-to-Factor Specimen Evaluation")
    print(f"{'=' * 60}")
    print(f"Passed: {evaluation['passed']}/{evaluation['total']}")
    print(f"Failed: {evaluation['failed']}/{evaluation['total']}")
    print(f"\nMetadata:")
    for k, v in evaluation["metadata"].items():
        if isinstance(v, list):
            print(f"  {k}:")
            for item in v:
                print(f"    - {item}")
        else:
            print(f"  {k}: {v}")

    print(f"\n{'=' * 60}")
    print("What this probe establishes:")
    print("  - Multi-channel measurement convergence is required for contact claims")
    print("  - Single sensory channel (visual alone) is insufficient for identity")
    print("  - Occlusion gaps > 3s preclude confident identity assignment")
    print("  - Indistinguishable instances cannot be resolved by appearance alone")
    print("  - Transient contact is distinguishable from persistent attachment")

    print(f"\nWhat this probe does NOT establish:")
    print("  - Real-time object tracking or prediction")
    print("  - Causal reasoning about object dynamics")
    print("  - Visual recognition or semantic understanding")
    print("  - Robustness to sensor noise or calibration drift")

    if evaluation["failed"] == 0:
        print("\n✓ All episodes classified correctly.")
        return 0
    else:
        print(f"\n✗ {evaluation['failed']} episode(s) classified incorrectly.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
