from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "evaluation" / "uci_posture_grounding" / "evaluate.py"
SPEC = importlib.util.spec_from_file_location("uci_posture_grounding_evaluate", MODULE_PATH)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)

ARCHIVE = ROOT / "evaluation" / "uci_posture_grounding" / ".cache" / "uci341.zip"


def test_official_subject_split_is_disjoint_and_complete():
    assert probe.TRAIN_SUBJECTS.isdisjoint(probe.TEST_SUBJECTS)
    assert probe.TRAIN_SUBJECTS == {
        1, 3, 5, 6, 7, 8, 11, 14, 15, 16, 17, 19, 21, 22, 23, 25, 26, 27, 28, 29, 30
    }
    assert probe.TEST_SUBJECTS == {2, 4, 9, 10, 12, 13, 18, 20, 24}


def test_percentile_interpolates_deterministically():
    assert probe.percentile([0.0, 10.0], 0.25) == pytest.approx(2.5)
    assert probe.percentile([0.0, 10.0], 0.90) == pytest.approx(9.0)


def test_rotation_preserves_invariant_features():
    accel = ((1.0, 0.2, -0.1), (0.9, 0.1, 0.4), (1.1, -0.3, 0.2))
    gyro = ((0.1, 0.2, 0.3), (-0.2, 0.1, 0.4), (0.3, -0.1, 0.2))
    original = probe.invariant_features(accel, gyro)

    for rotation_name in probe.ROTATIONS:
        rotated = probe.invariant_features(
            probe.rotate_window(accel, rotation_name),
            probe.rotate_window(gyro, rotation_name),
        )
        assert rotated.accel_magnitude_std == pytest.approx(
            original.accel_magnitude_std, abs=1e-15
        )
        assert rotated.gyro_magnitude_rms == pytest.approx(
            original.gyro_magnitude_rms, abs=1e-15
        )


def test_axis_gate_changes_when_coordinate_frame_rotates():
    accel = ((0.0, 0.0, 1.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0))
    gyro = ((0.0, 0.0, 0.0),) * 3
    thresholds = probe.Thresholds(
        static_accel_upper=0.01,
        static_gyro_upper=0.01,
        motion_accel_lower=0.10,
        motion_gyro_lower=0.10,
    )

    original_axis = probe.axis_features(accel, gyro)
    rotated_accel = probe.rotate_window(accel, "x90")
    rotated_gyro = probe.rotate_window(gyro, "x90")

    assert probe.predict_axis_baseline(original_axis, thresholds) == probe.PRED_STABLE
    assert (
        probe.predict_axis_baseline(
            probe.axis_features(rotated_accel, rotated_gyro), thresholds
        )
        == probe.PRED_UNCERTAIN
    )
    assert probe.predict_invariant(
        probe.invariant_features(accel, gyro), thresholds
    ) == probe.predict_invariant(
        probe.invariant_features(rotated_accel, rotated_gyro), thresholds
    )


def test_overlap_between_stable_and_motion_rules_refuses():
    thresholds = probe.Thresholds(
        static_accel_upper=0.10,
        static_gyro_upper=0.10,
        motion_accel_lower=0.05,
        motion_gyro_lower=0.05,
    )
    features = probe.InvariantFeatures(
        accel_magnitude_std=0.075,
        gyro_magnitude_rms=0.075,
    )
    assert probe.predict_invariant(features, thresholds) == probe.PRED_UNCERTAIN


@pytest.mark.skipif(not ARCHIVE.exists(), reason="pinned UCI archive not available locally")
def test_pinned_archive_external_evaluation_contract():
    report = probe.run_evaluation(ARCHIVE)

    assert report["dataset"]["archive_sha256"] == probe.ARCHIVE_SHA256
    assert report["split"]["overlap"] == []
    assert report["segment_counts"]["train"]["total"] == 849
    assert report["segment_counts"]["test"]["total"] == 365

    invariant = report["models"]["rotation_invariant"]["metrics"]
    assert invariant["total"] == 365
    assert invariant["subset_predictions"]["static"]["total"] == 108
    assert invariant["subset_predictions"]["dynamic"]["total"] == 149
    assert invariant["subset_predictions"]["transition"]["total"] == 108

    rotation = report["rotation_robustness"]
    assert rotation["comparisons"] == 1095
    assert rotation["invariant_prediction_stability"] == 1.0
    assert rotation["max_abs_invariant_accel_feature_drift"] < 1e-12
    assert rotation["max_abs_invariant_gyro_feature_drift"] < 1e-12

    # The old +Z assumption is demonstrably inappropriate for this recording frame.
    assert rotation["baseline_z_alignment_gate_true_original_count"] < 10
