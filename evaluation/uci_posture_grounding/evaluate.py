#!/usr/bin/env python3
"""External-data probe for a narrow measurement -> semantic-factor seam.

UCI activity labels are used only after factor inference, for calibration on the
official training subjects and evaluation on the official held-out subjects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Sequence

ARCHIVE_SHA256 = "4ac4ae064227c07045a99551876b54d204837e995e298b6488559e209b3deb09"
DOI = "10.24432/C54G7M"
SAMPLE_RATE_HZ = 50
WINDOW_SAMPLES = 128

TRAIN_SUBJECTS = frozenset({1, 3, 5, 6, 7, 8, 11, 14, 15, 16, 17, 19, 21, 22, 23, 25, 26, 27, 28, 29, 30})
TEST_SUBJECTS = frozenset({2, 4, 9, 10, 12, 13, 18, 20, 24})

ACTIVITY_NAMES = {
    1: "WALKING",
    2: "WALKING_UPSTAIRS",
    3: "WALKING_DOWNSTAIRS",
    4: "SITTING",
    5: "STANDING",
    6: "LAYING",
    7: "STAND_TO_SIT",
    8: "SIT_TO_STAND",
    9: "SIT_TO_LIE",
    10: "LIE_TO_SIT",
    11: "STAND_TO_LIE",
    12: "LIE_TO_STAND",
}
STATIC_IDS = frozenset({4, 5, 6})
DYNAMIC_IDS = frozenset({1, 2, 3})
TRANSITION_IDS = frozenset({7, 8, 9, 10, 11, 12})

PRED_STABLE = "stable_posture_evidence"
PRED_MOTION = "motion_or_transition_evidence"
PRED_UNCERTAIN = "REFUSAL:uncertain"

ROTATIONS = {
    "x90": lambda v: (v[0], -v[2], v[1]),
    "y90": lambda v: (v[2], v[1], -v[0]),
    "z90": lambda v: (-v[1], v[0], v[2]),
}


@dataclass(frozen=True)
class SegmentWindow:
    experiment: int
    user: int
    activity_id: int
    label_start: int
    label_end: int
    window_start: int
    window_end_exclusive: int
    accel: tuple[tuple[float, float, float], ...]
    gyro: tuple[tuple[float, float, float], ...]

    @property
    def reference(self) -> str:
        return PRED_STABLE if self.activity_id in STATIC_IDS else PRED_MOTION

    @property
    def reference_subset(self) -> str:
        if self.activity_id in STATIC_IDS:
            return "static"
        if self.activity_id in DYNAMIC_IDS:
            return "dynamic"
        if self.activity_id in TRANSITION_IDS:
            return "transition"
        return "unknown"


@dataclass(frozen=True)
class InvariantFeatures:
    accel_magnitude_std: float
    gyro_magnitude_rms: float


@dataclass(frozen=True)
class AxisFeatures:
    accel_mean_z: float
    invariant: InvariantFeatures


@dataclass(frozen=True)
class Thresholds:
    static_accel_upper: float
    static_gyro_upper: float
    motion_accel_lower: float
    motion_gyro_lower: float


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def vector_magnitude(v: tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def rms(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("rms requires values")
    return math.sqrt(mean([x * x for x in values]))


def invariant_features(
    accel: Sequence[tuple[float, float, float]],
    gyro: Sequence[tuple[float, float, float]],
) -> InvariantFeatures:
    if len(accel) < 2 or len(gyro) < 2:
        raise ValueError("at least two synchronized samples are required")
    if len(accel) != len(gyro):
        raise ValueError("accelerometer and gyroscope windows must be synchronized")
    accel_mag = [vector_magnitude(v) for v in accel]
    gyro_mag = [vector_magnitude(v) for v in gyro]
    return InvariantFeatures(
        accel_magnitude_std=pstdev(accel_mag),
        gyro_magnitude_rms=rms(gyro_mag),
    )


def axis_features(
    accel: Sequence[tuple[float, float, float]],
    gyro: Sequence[tuple[float, float, float]],
) -> AxisFeatures:
    inv = invariant_features(accel, gyro)
    return AxisFeatures(accel_mean_z=mean([v[2] for v in accel]), invariant=inv)


def rotate_window(
    samples: Sequence[tuple[float, float, float]], rotation_name: str
) -> tuple[tuple[float, float, float], ...]:
    fn = ROTATIONS[rotation_name]
    return tuple(fn(v) for v in samples)


def calibrate(train_windows: Sequence[SegmentWindow]) -> Thresholds:
    """Calibrate fixed quantile rules using official training subjects only."""
    static_features: list[InvariantFeatures] = []
    motion_features: list[InvariantFeatures] = []
    for w in train_windows:
        f = invariant_features(w.accel, w.gyro)
        if w.activity_id in STATIC_IDS:
            static_features.append(f)
        elif w.activity_id in DYNAMIC_IDS or w.activity_id in TRANSITION_IDS:
            motion_features.append(f)
    if not static_features or not motion_features:
        raise ValueError("calibration requires both static and non-static examples")
    return Thresholds(
        static_accel_upper=percentile([f.accel_magnitude_std for f in static_features], 0.90),
        static_gyro_upper=percentile([f.gyro_magnitude_rms for f in static_features], 0.90),
        motion_accel_lower=percentile([f.accel_magnitude_std for f in motion_features], 0.25),
        motion_gyro_lower=percentile([f.gyro_magnitude_rms for f in motion_features], 0.25),
    )


def predict_invariant(features: InvariantFeatures, thresholds: Thresholds) -> str:
    stable = (
        features.accel_magnitude_std <= thresholds.static_accel_upper
        and features.gyro_magnitude_rms <= thresholds.static_gyro_upper
    )
    motion = (
        features.accel_magnitude_std >= thresholds.motion_accel_lower
        or features.gyro_magnitude_rms >= thresholds.motion_gyro_lower
    )
    if stable and not motion:
        return PRED_STABLE
    if motion and not stable:
        return PRED_MOTION
    return PRED_UNCERTAIN


def predict_axis_baseline(features: AxisFeatures, thresholds: Thresholds) -> str:
    """Diagnostic baseline retaining the old +Z gravity assumption."""
    pred = predict_invariant(features.invariant, thresholds)
    if pred == PRED_STABLE and abs(features.accel_mean_z - 1.0) > 0.05:
        return PRED_UNCERTAIN
    return pred


def _read_xyz(zf: zipfile.ZipFile, member: str) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    for raw in zf.read(member).decode("utf-8").splitlines():
        parts = raw.split()
        if len(parts) >= 3:
            out.append((float(parts[0]), float(parts[1]), float(parts[2])))
    return out


def _parse_labels(zf: zipfile.ZipFile) -> dict[tuple[int, int], list[tuple[int, int, int]]]:
    grouped: dict[tuple[int, int], list[tuple[int, int, int]]] = defaultdict(list)
    for raw in zf.read("RawData/labels.txt").decode("utf-8").splitlines():
        exp_s, user_s, act_s, start_s, end_s = raw.split()[:5]
        exp, user, act, start, end = map(int, (exp_s, user_s, act_s, start_s, end_s))
        if act in ACTIVITY_NAMES:
            grouped[(exp, user)].append((act, start, end))
    return grouped


def load_windows(archive_path: Path) -> list[SegmentWindow]:
    digest = sha256_file(archive_path)
    if digest != ARCHIVE_SHA256:
        raise ValueError(f"archive SHA256 mismatch: expected {ARCHIVE_SHA256}, got {digest}")
    windows: list[SegmentWindow] = []
    with zipfile.ZipFile(archive_path) as zf:
        grouped = _parse_labels(zf)
        for (exp, user), labels in sorted(grouped.items()):
            if user not in TRAIN_SUBJECTS and user not in TEST_SUBJECTS:
                continue
            acc_member = f"RawData/acc_exp{exp:02d}_user{user:02d}.txt"
            gyro_member = f"RawData/gyro_exp{exp:02d}_user{user:02d}.txt"
            accel_all = _read_xyz(zf, acc_member)
            gyro_all = _read_xyz(zf, gyro_member)
            limit = min(len(accel_all), len(gyro_all))
            for activity_id, start, end in labels:
                start = max(0, start)
                end = min(end, limit - 1)
                if end <= start:
                    continue
                segment_len = end - start + 1
                n = min(WINDOW_SAMPLES, segment_len)
                window_start = start + (segment_len - n) // 2
                window_end = window_start + n
                accel = tuple(accel_all[window_start:window_end])
                gyro = tuple(gyro_all[window_start:window_end])
                if len(accel) < 2 or len(accel) != len(gyro):
                    continue
                windows.append(
                    SegmentWindow(
                        experiment=exp,
                        user=user,
                        activity_id=activity_id,
                        label_start=start,
                        label_end=end,
                        window_start=window_start,
                        window_end_exclusive=window_end,
                        accel=accel,
                        gyro=gyro,
                    )
                )
    return windows


def _empty_confusion() -> dict[str, dict[str, int]]:
    return {
        PRED_STABLE: {PRED_STABLE: 0, PRED_MOTION: 0, PRED_UNCERTAIN: 0},
        PRED_MOTION: {PRED_STABLE: 0, PRED_MOTION: 0, PRED_UNCERTAIN: 0},
    }


def score_predictions(
    windows: Sequence[SegmentWindow], predictions: Sequence[str]
) -> dict:
    confusion = _empty_confusion()
    subset = {"static": Counter(), "dynamic": Counter(), "transition": Counter()}
    failures: list[dict] = []
    correct = 0
    covered = 0
    for w, pred in zip(windows, predictions):
        ref = w.reference
        confusion[ref][pred] += 1
        subset[w.reference_subset][pred] += 1
        if pred != PRED_UNCERTAIN:
            covered += 1
        if pred == ref:
            correct += 1
        if pred != ref and len(failures) < 30:
            failures.append(
                {
                    "experiment": w.experiment,
                    "user": w.user,
                    "activity_id": w.activity_id,
                    "activity": ACTIVITY_NAMES[w.activity_id],
                    "label_start": w.label_start,
                    "label_end": w.label_end,
                    "window_start": w.window_start,
                    "window_end_exclusive": w.window_end_exclusive,
                    "reference": ref,
                    "predicted": pred,
                }
            )
    total = len(windows)
    correct_covered = sum(confusion[ref][ref] for ref in (PRED_STABLE, PRED_MOTION))
    return {
        "total": total,
        "covered": covered,
        "coverage": covered / total if total else None,
        "correct_total": correct,
        "accuracy_overall_with_refusals_as_not_correct": correct / total if total else None,
        "accuracy_on_covered": correct_covered / covered if covered else None,
        "confusion": confusion,
        "subset_predictions": {
            name: {
                "total": sum(counter.values()),
                PRED_STABLE: counter[PRED_STABLE],
                PRED_MOTION: counter[PRED_MOTION],
                PRED_UNCERTAIN: counter[PRED_UNCERTAIN],
            }
            for name, counter in subset.items()
        },
        "failures_bounded": failures,
    }


def _count_segments(windows: Sequence[SegmentWindow]) -> dict:
    by_subset = Counter(w.reference_subset for w in windows)
    by_activity = Counter(ACTIVITY_NAMES[w.activity_id] for w in windows)
    return {
        "total": len(windows),
        "by_subset": dict(sorted(by_subset.items())),
        "by_activity": dict(sorted(by_activity.items())),
    }


def rotation_robustness(
    windows: Sequence[SegmentWindow], thresholds: Thresholds
) -> dict:
    baseline_same = 0
    invariant_same = 0
    gate_same = 0
    gate_true_original = 0
    comparisons = 0
    max_acc_feature_drift = 0.0
    max_gyro_feature_drift = 0.0
    for w in windows:
        inv0 = invariant_features(w.accel, w.gyro)
        axis0 = axis_features(w.accel, w.gyro)
        inv_pred0 = predict_invariant(inv0, thresholds)
        base_pred0 = predict_axis_baseline(axis0, thresholds)
        gate0 = abs(axis0.accel_mean_z - 1.0) <= 0.05
        gate_true_original += int(gate0)
        for rotation_name in ROTATIONS:
            racc = rotate_window(w.accel, rotation_name)
            rgyro = rotate_window(w.gyro, rotation_name)
            inv_r = invariant_features(racc, rgyro)
            axis_r = axis_features(racc, rgyro)
            comparisons += 1
            invariant_same += int(predict_invariant(inv_r, thresholds) == inv_pred0)
            baseline_same += int(predict_axis_baseline(axis_r, thresholds) == base_pred0)
            gate_same += int((abs(axis_r.accel_mean_z - 1.0) <= 0.05) == gate0)
            max_acc_feature_drift = max(
                max_acc_feature_drift,
                abs(inv_r.accel_magnitude_std - inv0.accel_magnitude_std),
            )
            max_gyro_feature_drift = max(
                max_gyro_feature_drift,
                abs(inv_r.gyro_magnitude_rms - inv0.gyro_magnitude_rms),
            )
    return {
        "rotations": list(ROTATIONS),
        "comparisons": comparisons,
        "baseline_prediction_stability": baseline_same / comparisons if comparisons else None,
        "invariant_prediction_stability": invariant_same / comparisons if comparisons else None,
        "baseline_z_alignment_gate_stability": gate_same / comparisons if comparisons else None,
        "baseline_z_alignment_gate_true_original_count": gate_true_original,
        "baseline_z_alignment_gate_true_original_fraction": gate_true_original / len(windows) if windows else None,
        "max_abs_invariant_accel_feature_drift": max_acc_feature_drift,
        "max_abs_invariant_gyro_feature_drift": max_gyro_feature_drift,
    }


def run_evaluation(archive_path: Path) -> dict:
    windows = load_windows(archive_path)
    train = [w for w in windows if w.user in TRAIN_SUBJECTS]
    test = [w for w in windows if w.user in TEST_SUBJECTS]
    if set(w.user for w in train) & set(w.user for w in test):
        raise AssertionError("train/test subjects overlap")
    thresholds = calibrate(train)
    invariant_predictions = [
        predict_invariant(invariant_features(w.accel, w.gyro), thresholds) for w in test
    ]
    baseline_predictions = [
        predict_axis_baseline(axis_features(w.accel, w.gyro), thresholds) for w in test
    ]
    return {
        "schema": "linguistic-core.uci-posture-grounding-evaluation.v1",
        "dataset": {
            "name": "Smartphone-Based Recognition of Human Activities and Postural Transitions",
            "uci_id": 341,
            "doi": DOI,
            "archive_sha256": ARCHIVE_SHA256,
            "sampling_rate_hz": SAMPLE_RATE_HZ,
            "window_samples": WINDOW_SAMPLES,
            "window_policy": "one deterministic central window per labeled segment, up to 128 synchronized samples",
            "label_role": "calibration/evaluation reference only; never passed into prediction",
        },
        "licensing": {
            "current_uci_catalog": "CC BY 4.0",
            "bundled_archive_readme": "states that any commercial use is prohibited",
            "redistribution_policy_for_this_probe": "no raw sensor rows or archive bytes are committed while the source statements conflict",
        },
        "split": {
            "source": "official UCI Train/Test subject partition",
            "train_subjects": sorted(TRAIN_SUBJECTS),
            "test_subjects": sorted(TEST_SUBJECTS),
            "overlap": sorted(TRAIN_SUBJECTS & TEST_SUBJECTS),
        },
        "segment_counts": {"train": _count_segments(train), "test": _count_segments(test)},
        "calibration": {
            "source": "official train subjects only",
            "fixed_quantiles": {"static_upper": 0.90, "motion_lower": 0.25},
            "thresholds": {
                "static_accel_magnitude_std_upper": thresholds.static_accel_upper,
                "static_gyro_magnitude_rms_upper": thresholds.static_gyro_upper,
                "motion_accel_magnitude_std_lower": thresholds.motion_accel_lower,
                "motion_gyro_magnitude_rms_lower": thresholds.motion_gyro_lower,
            },
        },
        "models": {
            "axis_dependent_baseline": {
                "description": "invariant motion factors plus diagnostic mean-Z ~= +1g gate for candidate stable predictions",
                "metrics": score_predictions(test, baseline_predictions),
            },
            "rotation_invariant": {
                "description": "acceleration-magnitude variability and angular-speed magnitude RMS only",
                "metrics": score_predictions(test, invariant_predictions),
            },
        },
        "rotation_robustness": rotation_robustness(test, thresholds),
        "interpretation_limits": [
            "This is a narrow operational probe of stable-vs-nonstatic evidence, not a universal definition of posture or transition.",
            "Activity annotations are reference labels, not world truth and not inference inputs.",
            "Dynamic activities and postural transitions are collapsed to the same non-static prediction target; subset metrics are reported separately.",
            "No threshold was fit or changed using official test subjects or rotated test observations.",
            "Raw sensor rows are not included in the report.",
        ],
    }


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=here / ".cache" / "uci341.zip")
    parser.add_argument("--output", type=Path, default=here / "evaluation_report.json")
    args = parser.parse_args()
    if not args.archive.exists():
        raise SystemExit(
            f"archive not found: {args.archive}\n"
            "Download the official UCI 341 archive into .cache/uci341.zip; see README.md."
        )
    report = run_evaluation(args.archive)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    inv = report["models"]["rotation_invariant"]["metrics"]
    base = report["models"]["axis_dependent_baseline"]["metrics"]
    rot = report["rotation_robustness"]
    print(f"wrote {args.output}")
    print(f"baseline: coverage={base['coverage']:.3f} covered_accuracy={base['accuracy_on_covered']}")
    print(f"invariant: coverage={inv['coverage']:.3f} covered_accuracy={inv['accuracy_on_covered']}")
    print(
        f"rotation stability: baseline={rot['baseline_prediction_stability']:.3f} "
        f"invariant={rot['invariant_prediction_stability']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
