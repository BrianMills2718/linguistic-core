"""Executable tests for measurement-to-factor semantic-grounding gate."""

from __future__ import annotations

import pytest

from probe_measurement_to_factor_v1 import (
    ClassificationResult,
    MeasurementToFactorGate,
    SemanticClassification,
)


@pytest.fixture
def gate() -> MeasurementToFactorGate:
    """Load specimen fixtures and initialize gate."""
    return MeasurementToFactorGate()


def test_gate_loads_fixtures(gate: MeasurementToFactorGate) -> None:
    """Verify fixtures load correctly."""
    assert gate.fixtures is not None
    assert "episodes" in gate.fixtures
    assert len(gate.episodes) == 6


def test_positive_support_case_A1(gate: MeasurementToFactorGate) -> None:
    """Test multi-channel convergence for positive support case."""
    episode = next(e for e in gate.episodes if e["episode_id"] == "positive_support_case_A1")
    result = gate.classify_episode(episode)

    assert result.inferred_classification == SemanticClassification.SUPPORT
    assert result.inferred_confidence > 0.95
    assert result.match is True
    assert "contact_state" in result.factors


def test_adversarial_obstruction_B1(gate: MeasurementToFactorGate) -> None:
    """Test that visual occlusion alone is insufficient; multi-channel required."""
    episode = next(e for e in gate.episodes if e["episode_id"] == "adversarial_obstruction_B1")
    result = gate.classify_episode(episode)

    assert result.inferred_classification == SemanticClassification.VISUAL_OCCLUSION_NOT_SUPPORT
    assert result.inferred_confidence > 0.95
    assert result.match is True


def test_adversarial_attachment_B2(gate: MeasurementToFactorGate) -> None:
    """Test that transient contact is distinguished from persistent attachment."""
    episode = next(e for e in gate.episodes if e["episode_id"] == "adversarial_attachment_B2")
    result = gate.classify_episode(episode)

    assert result.inferred_classification == SemanticClassification.TRANSIENT_CONTACT_NOT_ATTACHMENT
    assert result.inferred_confidence > 0.95
    assert result.match is True


def test_posture_persistence_case_C1(gate: MeasurementToFactorGate) -> None:
    """Test stable pose persistence across environmental perturbations."""
    episode = next(e for e in gate.episodes if e["episode_id"] == "posture_persistence_case_C1")
    result = gate.classify_episode(episode)

    assert result.inferred_classification == SemanticClassification.PERSISTENT_IDENTITY_STABLE_POSE
    assert result.inferred_confidence > 0.90
    assert result.match is True


def test_adversarial_occlusion_replacement_C2(gate: MeasurementToFactorGate) -> None:
    """Test that identity across occlusion gaps > 3s requires observational continuity."""
    episode = next(e for e in gate.episodes if e["episode_id"] == "adversarial_occlusion_replacement_C2")
    result = gate.classify_episode(episode)

    assert result.inferred_classification == SemanticClassification.IDENTITY_UNKNOWN_INSUFFICIENT_EVIDENCE
    assert result.inferred_confidence > 0.95
    assert result.match is True
    assert "max_gap_ms" in str(result.factors.get("temporal_continuity", {}).value)


def test_adversarial_indistinguishable_duplicate_C3(gate: MeasurementToFactorGate) -> None:
    """Test that indistinguishable instances cannot be resolved by appearance alone."""
    episode = next(e for e in gate.episodes if e["episode_id"] == "adversarial_indistinguishable_duplicate_C3")
    result = gate.classify_episode(episode)

    assert result.inferred_classification == SemanticClassification.MULTIPLE_INDISTINGUISHABLE_INSTANCES
    assert result.inferred_confidence > 0.95
    assert result.match is True


def test_contact_factor_inference_with_pressure(gate: MeasurementToFactorGate) -> None:
    """Test that pressure sensor input is correctly interpreted."""
    episode = next(e for e in gate.episodes if e["episode_id"] == "positive_support_case_A1")
    contact_factor, factors = gate.infer_contact_factors(episode)

    assert contact_factor.name == "contact_state"
    assert contact_factor.confidence > 0.90
    assert len([f for f in factors if f.name == "pressure_measurement"]) > 0


def test_identity_factor_inference_temporal_continuity(gate: MeasurementToFactorGate) -> None:
    """Test that temporal gaps are detected in identity inference."""
    episode = next(e for e in gate.episodes if e["episode_id"] == "adversarial_occlusion_replacement_C2")
    factors = gate.infer_identity_factors(episode)

    temporal_factors = [f for f in factors if "temporal_continuity" in f.name]
    assert len(temporal_factors) > 0
    temporal_factor = temporal_factors[0]
    assert temporal_factor.value.get("max_gap_ms") == 4000


def test_identity_factor_inference_multi_instance(gate: MeasurementToFactorGate) -> None:
    """Test that multiple instances are correctly detected."""
    episode = next(e for e in gate.episodes if e["episode_id"] == "adversarial_indistinguishable_duplicate_C3")
    factors = gate.infer_identity_factors(episode)

    multi_instance_factors = [f for f in factors if "multi_instance" in f.name]
    assert len(multi_instance_factors) > 0
    assert multi_instance_factors[0].value.get("instance_count") == 2


def test_full_evaluation_all_episodes_pass(gate: MeasurementToFactorGate) -> None:
    """Test that full evaluation passes all episodes."""
    evaluation = gate.run_evaluation()

    assert evaluation["passed"] == evaluation["total"]
    assert evaluation["failed"] == 0
    assert evaluation["total"] == 6


def test_evaluation_result_structure(gate: MeasurementToFactorGate) -> None:
    """Test that evaluation results have correct structure."""
    evaluation = gate.run_evaluation()

    assert isinstance(evaluation["results"], list)
    for result in evaluation["results"]:
        assert isinstance(result, ClassificationResult)
        assert hasattr(result, "episode_id")
        assert hasattr(result, "inferred_classification")
        assert hasattr(result, "inferred_confidence")
        assert hasattr(result, "match")
