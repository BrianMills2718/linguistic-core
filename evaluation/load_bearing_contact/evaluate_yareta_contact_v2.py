#!/usr/bin/env python3
"""Evaluate preregistered Yareta foot-ground contact experiment v2.

Inference uses only the 16 pressure channels for the evaluated foot. Primary
reference labels come from source-authored C3D Foot Strike / Foot Off events.

The protocol is governed by experiment_plan_v2.json. This evaluator does not
modify its split, windowing, synchronization margin, threshold grid, refusal
width, or calibration objective.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

CONTACT = "foot_ground_contact_evidence"
NO_CONTACT = "no_foot_ground_contact_evidence"
REFUSAL = "REFUSAL:near_event_or_uncertain"
PRESSURE_PATTERNS = {
    "Left": re.compile(r"^leftPressure(\d+)_N_cm___$"),
    "Right": re.compile(r"^rightPressure(\d+)_N_cm___$"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def normalize_signal(values: list[float]) -> tuple[list[float], float, float]:
    p5 = percentile(values, 0.05)
    p95 = percentile(values, 0.95)
    if not math.isfinite(p5) or not math.isfinite(p95) or p95 <= p5:
        raise ValueError(f"invalid pressure normalization p5={p5} p95={p95}")
    normalized = [
        min(1.0, max(0.0, (value - p5) / (p95 - p5))) for value in values
    ]
    return normalized, p5, p95


def predict(feature: float, center: float, refusal_half_width: float) -> str:
    if feature >= center + refusal_half_width:
        return CONTACT
    if feature <= center - refusal_half_width:
        return NO_CONTACT
    return REFUSAL


def pressure_column_indices(header: list[str], side: str) -> list[int]:
    found: list[tuple[int, int]] = []
    pattern = PRESSURE_PATTERNS[side]
    for index, name in enumerate(header):
        match = pattern.match(name)
        if match:
            found.append((int(match.group(1)), index))
    found.sort()
    numbers = [number for number, _ in found]
    if numbers != list(range(1, 17)):
        raise ValueError(f"{side} pressure columns are {numbers}, expected 1..16")
    return [index for _, index in found]


def read_pressure_signal(
    csv_path: Path,
    side: str,
    *,
    drop_sensor_index: int | None = None,
    reverse_sensor_order: bool = False,
) -> tuple[list[float], int]:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        canonical_indices = pressure_column_indices(header, side)
        ordered_indices = (
            list(reversed(canonical_indices))
            if reverse_sensor_order
            else canonical_indices
        )

        values: list[float] = []
        rows = 0
        for row in reader:
            rows += 1
            sample_values: list[float] = []
            for position, column_index in enumerate(ordered_indices):
                canonical_position = (
                    15 - position if reverse_sensor_order else position
                )
                value = float(row[column_index])
                if not math.isfinite(value):
                    raise ValueError(f"non-finite pressure value in {csv_path.name}")
                if (
                    drop_sensor_index is not None
                    and canonical_position == drop_sensor_index
                ):
                    value = 0.0
                sample_values.append(value)
            values.append(sum(sample_values))
    return values, rows


def load_c3d_events(c3d_path: Path) -> dict[str, Any]:
    try:
        import ezc3d  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Yareta integration evaluation requires ezc3d. "
            "Install it in an isolated evaluation environment (e.g. pip install ezc3d)."
        ) from exc

    obj = ezc3d.c3d(str(c3d_path))
    frame_count = int(obj["data"]["points"].shape[2])
    point_header = obj["header"]["points"]
    rate = float(point_header["frame_rate"])
    first_frame = int(point_header["first_frame"])

    event_group = obj["parameters"].get("EVENT")
    if not event_group:
        raise ValueError(f"{c3d_path.name}: missing EVENT group")

    labels = list(event_group["LABELS"]["value"])
    contexts = list(event_group["CONTEXTS"]["value"])
    raw_times = [float(value) for value in event_group["TIMES"]["value"][1]]
    used = int(event_group["USED"]["value"][0])

    if not (len(labels) == len(contexts) == len(raw_times) == used):
        raise ValueError(f"{c3d_path.name}: inconsistent EVENT lengths")
    if set(labels) - {"Foot Strike", "Foot Off"}:
        raise ValueError(
            f"{c3d_path.name}: unexpected EVENT labels {sorted(set(labels))}"
        )
    if set(contexts) - {"Left", "Right"}:
        raise ValueError(
            f"{c3d_path.name}: unexpected EVENT contexts {sorted(set(contexts))}"
        )

    origin_seconds = first_frame / rate
    events = [
        {
            "time": raw_time - origin_seconds,
            "label": label,
            "side": context,
        }
        for raw_time, label, context in zip(raw_times, labels, contexts)
    ]

    for side in ("Left", "Right"):
        sequence = sorted(
            (event["time"], event["label"])
            for event in events
            if event["side"] == side
        )
        if len(sequence) < 2:
            raise ValueError(f"{c3d_path.name}: too few {side} events")
        for first, second in zip(sequence, sequence[1:]):
            if first[1] == second[1]:
                raise ValueError(
                    f"{c3d_path.name}: non-alternating {side} events {first}, {second}"
                )

    return {
        "frame_count": frame_count,
        "rate": rate,
        "first_frame": first_frame,
        "origin_seconds": origin_seconds,
        "events": events,
    }


def reference_for_window(
    start_index: int,
    end_exclusive: int,
    rate: float,
    events: list[dict[str, Any]],
    side: str,
    margin_seconds: float,
) -> str | None:
    start_time = start_index / rate
    end_time = end_exclusive / rate
    sequence = sorted(
        (event["time"], event["label"])
        for event in events
        if event["side"] == side
    )
    for (first_time, first_label), (second_time, second_label) in zip(
        sequence, sequence[1:]
    ):
        if first_label == second_label:
            continue
        if (
            start_time >= first_time + margin_seconds
            and end_time <= second_time - margin_seconds
        ):
            if first_label == "Foot Strike" and second_label == "Foot Off":
                return CONTACT
            if first_label == "Foot Off" and second_label == "Foot Strike":
                return NO_CONTACT
    return None


def trial_foot_windows(
    data_root: Path,
    participant: str,
    stem: str,
    side: str,
    plan: dict[str, Any],
    *,
    drop_sensor_index: int | None = None,
    reverse_sensor_order: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    participant_dir = data_root / f"{participant}_S01"
    csv_path = participant_dir / "SYNC_DATA" / f"{stem}.csv"
    c3d_path = participant_dir / "RAW_DATA" / f"{stem}.c3d"

    pressure, csv_rows = read_pressure_signal(
        csv_path,
        side,
        drop_sensor_index=drop_sensor_index,
        reverse_sensor_order=reverse_sensor_order,
    )
    c3d = load_c3d_events(c3d_path)
    if csv_rows != c3d["frame_count"]:
        raise ValueError(
            f"{stem}: CSV rows {csv_rows} != C3D frames {c3d['frame_count']}"
        )
    if abs(c3d["rate"] - plan["dataset"]["insole_sampling_hz"]) > 1e-9:
        raise ValueError(f"{stem}: unexpected point rate {c3d['rate']}")

    trial_max_time = (csv_rows - 1) / c3d["rate"]
    event_times = [event["time"] for event in c3d["events"]]
    if event_times and (
        min(event_times) < -1e-6 or max(event_times) > trial_max_time + 1e-6
    ):
        raise ValueError(
            f"{stem}: adjusted EVENT times outside synchronized CSV time base"
        )

    normalized, p5, p95 = normalize_signal(pressure)
    window_samples = int(plan["preprocessing"]["window_samples"])
    stride = int(plan["preprocessing"]["stride_samples"])
    margin_seconds = (
        float(plan["reference_construction"]["synchronization_exclusion_margin_ms"])
        / 1000.0
    )

    windows: list[dict[str, Any]] = []
    ambiguous = 0
    for start in range(0, csv_rows - window_samples + 1, stride):
        end = start + window_samples
        reference = reference_for_window(
            start,
            end,
            c3d["rate"],
            c3d["events"],
            side,
            margin_seconds,
        )
        feature = statistics.median(normalized[start:end])
        if reference is None:
            ambiguous += 1
            continue
        windows.append(
            {
                "participant": participant,
                "stem": stem,
                "side": side,
                "start": start,
                "end": end,
                "feature": feature,
                "reference": reference,
            }
        )

    return windows, {
        "participant": participant,
        "stem": stem,
        "side": side,
        "csv_rows": csv_rows,
        "c3d_frames": c3d["frame_count"],
        "rate": c3d["rate"],
        "first_frame": c3d["first_frame"],
        "origin_seconds": c3d["origin_seconds"],
        "normalization_p5": p5,
        "normalization_p95": p95,
        "reference_ambiguous_windows": ambiguous,
        "reference_scored_windows": len(windows),
    }


def selected_stems(
    manifest: dict[str, Any], participants: set[str]
) -> list[tuple[str, str]]:
    stems: set[tuple[str, str]] = set()
    for row in manifest["files"]:
        participant = row["participant"]
        if participant in participants and row["extension"] == "csv":
            stems.add((participant, row["stem"]))
    return sorted(stems)


def verify_local_files(
    data_root: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    missing: list[str] = []
    bad_hashes: list[str] = []
    total_bytes = 0
    for row in manifest["files"]:
        path = data_root / row["full_name"].lstrip("/")
        if not path.exists():
            missing.append(row["full_name"])
            continue
        total_bytes += path.stat().st_size
        if path.stat().st_size != row["size"] or sha256_file(path) != row["sha256"]:
            bad_hashes.append(row["full_name"])
    if missing or bad_hashes:
        raise ValueError(
            f"local Yareta integrity failure missing={missing[:5]} "
            f"bad_hashes={bad_hashes[:5]}"
        )
    return {
        "selected_file_count": len(manifest["files"]),
        "selected_trial_pair_count": manifest["summary"]["selected_trial_pair_count"],
        "selected_uncompressed_bytes": total_bytes,
        "selection_sha256": manifest["selection_sha256"],
        "all_selected_files_sha256_verified": True,
    }


def collect_windows(
    data_root: Path,
    manifest: dict[str, Any],
    plan: dict[str, Any],
    participants: set[str],
    *,
    drop_sensor_index: int | None = None,
    reverse_sensor_order: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    windows: list[dict[str, Any]] = []
    trial_foot_info: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for participant, stem in selected_stems(manifest, participants):
        for side in ("Left", "Right"):
            try:
                current, info = trial_foot_windows(
                    data_root,
                    participant,
                    stem,
                    side,
                    plan,
                    drop_sensor_index=drop_sensor_index,
                    reverse_sensor_order=reverse_sensor_order,
                )
                windows.extend(current)
                trial_foot_info.append(info)
            except Exception as exc:
                exclusions.append(
                    {
                        "participant": participant,
                        "stem": stem,
                        "side": side,
                        "reason": str(exc),
                    }
                )
    return windows, trial_foot_info, exclusions


def shallow_metrics(
    windows: list[dict[str, Any]],
    center: float,
    refusal_half_width: float,
) -> dict[str, Any]:
    references = Counter(window["reference"] for window in windows)
    predictions: Counter[str] = Counter()
    correct = 0
    covered = 0
    false_contact = 0
    false_no_contact = 0

    for window in windows:
        predicted = predict(window["feature"], center, refusal_half_width)
        predictions[predicted] += 1
        covered += predicted != REFUSAL
        correct += predicted == window["reference"]
        false_contact += (
            predicted == CONTACT and window["reference"] == NO_CONTACT
        )
        false_no_contact += (
            predicted == NO_CONTACT and window["reference"] == CONTACT
        )

    contact_total = references[CONTACT]
    no_contact_total = references[NO_CONTACT]
    balanced_accuracy = None
    if contact_total and no_contact_total:
        correct_contact = sum(
            1
            for window in windows
            if window["reference"] == CONTACT
            and predict(window["feature"], center, refusal_half_width) == CONTACT
        )
        correct_no_contact = sum(
            1
            for window in windows
            if window["reference"] == NO_CONTACT
            and predict(window["feature"], center, refusal_half_width) == NO_CONTACT
        )
        balanced_accuracy = 0.5 * (
            correct_contact / contact_total + correct_no_contact / no_contact_total
        )

    return {
        "n": len(windows),
        "reference_counts": dict(references),
        "prediction_counts": dict(predictions),
        "coverage": covered / len(windows) if windows else None,
        "balanced_accuracy": balanced_accuracy,
        "accuracy_all": correct / len(windows) if windows else None,
        "accuracy_covered": correct / covered if covered else None,
        "false_contact": false_contact,
        "false_no_contact": false_no_contact,
        "refusals": predictions[REFUSAL],
    }


def detailed_metrics(
    windows: list[dict[str, Any]],
    center: float,
    refusal_half_width: float,
) -> dict[str, Any]:
    summary = shallow_metrics(windows, center, refusal_half_width)
    failures: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for window in windows:
        grouped[(window["participant"], window["side"])].append(window)
        predicted = predict(window["feature"], center, refusal_half_width)
        if predicted != window["reference"] and len(failures) < 40:
            failures.append(
                {
                    key: window[key]
                    for key in (
                        "participant",
                        "stem",
                        "side",
                        "start",
                        "end",
                        "reference",
                    )
                }
                | {"predicted": predicted}
            )

    per_participant_foot = {
        f"{participant}:{side}": shallow_metrics(
            group, center, refusal_half_width
        )
        for (participant, side), group in sorted(grouped.items())
    }
    return {
        "total_reference_windows": summary.pop("n"),
        **{
            "balanced_accuracy_refusals_incorrect": summary.pop(
                "balanced_accuracy"
            ),
            "accuracy_all_refusals_incorrect": summary.pop("accuracy_all"),
            "accuracy_on_covered": summary.pop("accuracy_covered"),
        },
        **summary,
        "failures_bounded": failures,
        "per_participant_foot": per_participant_foot,
    }


def select_center(
    windows: list[dict[str, Any]], plan: dict[str, Any]
) -> tuple[float, list[dict[str, Any]]]:
    refusal_half_width = float(plan["calibration"]["refusal_half_width"])
    candidates = [
        float(value)
        for value in plan["calibration"]["candidate_center_thresholds"]
    ]
    if not any(window["reference"] == CONTACT for window in windows):
        raise ValueError("calibration has no contact reference windows")
    if not any(window["reference"] == NO_CONTACT for window in windows):
        raise ValueError("calibration has no no-contact reference windows")

    rows: list[dict[str, Any]] = []
    for center in candidates:
        metrics = shallow_metrics(windows, center, refusal_half_width)
        rows.append({"center": center, **metrics})

    valid = [row for row in rows if row["balanced_accuracy"] is not None]
    selected = max(
        valid,
        key=lambda row: (
            row["balanced_accuracy"],
            row["coverage"],
            -row["center"],
        ),
    )
    return float(selected["center"]), rows


def alignment_audit(
    trial_foot_info: Iterable[dict[str, Any]],
    exclusions: list[dict[str, Any]],
) -> dict[str, Any]:
    infos = list(trial_foot_info)
    nonzero = {
        info["stem"]: {
            "first_frame": info["first_frame"],
            "origin_seconds": info["origin_seconds"],
        }
        for info in infos
        if info["first_frame"]
    }
    return {
        "trial_foot_records": len(infos),
        "exclusions": exclusions,
        "nonzero_first_frame_trials": [
            {"stem": stem, **values} for stem, values in sorted(nonzero.items())
        ],
        "event_time_mapping": (
            "adjusted_event_time = C3D EVENT time - first_frame / frame_rate; "
            "CSV row zero corresponds to stored C3D first_frame"
        ),
        "reference_ambiguous_windows": sum(
            info["reference_ambiguous_windows"] for info in infos
        ),
        "reference_scored_windows": sum(
            info["reference_scored_windows"] for info in infos
        ),
    }


def run_evaluation(
    plan_path: Path,
    manifest_path: Path,
    data_root: Path,
) -> dict[str, Any]:
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    integrity = verify_local_files(data_root, manifest)

    calibration_participants = set(plan["participant_split"]["calibration"])
    evaluation_participants = set(plan["participant_split"]["evaluation"])
    if calibration_participants & evaluation_participants:
        raise ValueError("calibration/evaluation participant split overlaps")

    calibration_windows, calibration_info, calibration_exclusions = collect_windows(
        data_root, manifest, plan, calibration_participants
    )
    evaluation_windows, evaluation_info, evaluation_exclusions = collect_windows(
        data_root, manifest, plan, evaluation_participants
    )

    center, calibration_grid = select_center(calibration_windows, plan)
    refusal_half_width = float(plan["calibration"]["refusal_half_width"])
    held_out = detailed_metrics(
        evaluation_windows, center, refusal_half_width
    )

    permuted_windows, _permuted_info, permuted_exclusions = collect_windows(
        data_root,
        manifest,
        plan,
        evaluation_participants,
        reverse_sensor_order=True,
    )
    baseline_by_key = {
        (
            window["participant"],
            window["stem"],
            window["side"],
            window["start"],
            window["end"],
        ): window
        for window in evaluation_windows
    }
    permuted_by_key = {
        (
            window["participant"],
            window["stem"],
            window["side"],
            window["start"],
            window["end"],
        ): window
        for window in permuted_windows
    }
    common_keys = sorted(set(baseline_by_key) & set(permuted_by_key))
    permutation_changes = 0
    maximum_feature_drift = 0.0
    for key in common_keys:
        baseline = baseline_by_key[key]
        permuted = permuted_by_key[key]
        maximum_feature_drift = max(
            maximum_feature_drift,
            abs(baseline["feature"] - permuted["feature"]),
        )
        permutation_changes += (
            predict(baseline["feature"], center, refusal_half_width)
            != predict(permuted["feature"], center, refusal_half_width)
        )

    dropout: list[dict[str, Any]] = []
    for sensor_index in range(16):
        dropout_windows, _dropout_info, dropout_exclusions = collect_windows(
            data_root,
            manifest,
            plan,
            evaluation_participants,
            drop_sensor_index=sensor_index,
        )
        dropout.append(
            {
                "sensor_index_1based": sensor_index + 1,
                "metrics": detailed_metrics(
                    dropout_windows, center, refusal_half_width
                ),
                "excluded_trial_feet": len(dropout_exclusions),
            }
        )

    calibration_counts = Counter(
        window["reference"] for window in calibration_windows
    )
    held_out_counts = Counter(
        window["reference"] for window in evaluation_windows
    )

    return {
        "schema": "linguistic-core.yareta-foot-ground-contact-evaluation.v2",
        "result_status": "completed_negative_result",
        "primary_claim_supported": False,
        "source_integrity": {
            **integrity,
            "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        },
        "alignment": {
            "calibration": alignment_audit(
                calibration_info, calibration_exclusions
            ),
            "evaluation": alignment_audit(
                evaluation_info, evaluation_exclusions
            ),
        },
        "reference": {
            "margin_seconds": (
                plan["reference_construction"][
                    "synchronization_exclusion_margin_ms"
                ]
                / 1000.0
            ),
            "window_samples": plan["preprocessing"]["window_samples"],
            "calibration_reference_counts": dict(calibration_counts),
            "evaluation_reference_counts": dict(held_out_counts),
        },
        "calibration": {
            "candidate_results": calibration_grid,
            "selected_center": center,
            "selected_metrics": shallow_metrics(
                calibration_windows, center, refusal_half_width
            ),
        },
        "held_out": held_out,
        "robustness": {
            "sensor_order_permutation": {
                "common_windows": len(common_keys),
                "prediction_changes": permutation_changes,
                "max_abs_feature_drift": maximum_feature_drift,
                "exclusions": permuted_exclusions,
            },
            "single_sensor_dropout": dropout,
        },
        "interpretation": {
            "calibration_reference_imbalance": (
                f"{calibration_counts[CONTACT]} contact vs "
                f"{calibration_counts[NO_CONTACT]} no-contact scored windows"
            ),
            "held_out_reference_imbalance": (
                f"{held_out_counts[CONTACT]} contact vs "
                f"{held_out_counts[NO_CONTACT]} no-contact scored windows"
            ),
            "conclusion": (
                "The preregistered v2 protocol does not provide evidence for "
                "a robust pressure-to-foot-ground-contact grounding factor. "
                "The conservative reference construction produced very few "
                "no-contact calibration windows, and the frozen selected "
                "threshold generalized poorly to held-out participants."
            ),
            "no_post_hoc_retuning": True,
            "protocol_change_policy": (
                "Any material change requires a separately versioned plan and "
                "fresh evaluation data; v2 is retained unchanged."
            ),
        },
        "limits": [
            "Pressure-insoles are inference inputs; optoelectronic C3D gait events are the primary reference.",
            "Windows within the preregistered event-boundary margin are excluded from reference scoring.",
            "Threshold selection uses calibration participants only.",
            "This evaluates foot-ground contact evidence, not the full support relation.",
        ],
    }


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan", type=Path, default=here / "experiment_plan_v2.json"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=here / "acquisition_manifest_v2.json",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=here / ".cache" / "yareta_v2_selected",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=here / "evaluation_report_v2.json",
    )
    args = parser.parse_args()

    report = run_evaluation(args.plan, args.manifest, args.data_root)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    held_out = report["held_out"]
    print(f"selected_center={report['calibration']['selected_center']}")
    print(
        f"held_out_reference={report['reference']['evaluation_reference_counts']}"
    )
    print(
        "held_out "
        f"coverage={held_out['coverage']:.6f} "
        f"balanced_accuracy={held_out['balanced_accuracy_refusals_incorrect']:.6f} "
        f"accuracy_covered={held_out['accuracy_on_covered']:.6f} "
        f"false_contact={held_out['false_contact']} "
        f"false_no_contact={held_out['false_no_contact']} "
        f"refusals={held_out['refusals']}"
    )
    permutation = report["robustness"]["sensor_order_permutation"]
    print(
        "permutation "
        f"changes={permutation['prediction_changes']} "
        f"max_feature_drift={permutation['max_abs_feature_drift']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
