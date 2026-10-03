from __future__ import annotations

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EVAL_PATH = (
    ROOT / "evaluation" / "load_bearing_contact" / "evaluate_yareta_contact_v2.py"
)
ACQUIRE_PATH = (
    ROOT / "evaluation" / "load_bearing_contact" / "acquire_yareta_v2_ranges.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


evaluation = load_module("yareta_contact_v2_eval", EVAL_PATH)
acquisition = load_module("yareta_contact_v2_acquire", ACQUIRE_PATH)


def test_predict_respects_refusal_band():
    assert evaluation.predict(0.70, 0.50, 0.05) == evaluation.CONTACT
    assert evaluation.predict(0.30, 0.50, 0.05) == evaluation.NO_CONTACT
    assert evaluation.predict(0.50, 0.50, 0.05) == evaluation.REFUSAL


def test_reference_window_requires_full_margin_clearance():
    events = [
        {"time": 0.0, "label": "Foot Strike", "side": "Left"},
        {"time": 0.7, "label": "Foot Off", "side": "Left"},
        {"time": 1.2, "label": "Foot Strike", "side": "Left"},
    ]
    assert (
        evaluation.reference_for_window(20, 40, 100.0, events, "Left", 0.15)
        == evaluation.CONTACT
    )
    assert (
        evaluation.reference_for_window(85, 105, 100.0, events, "Left", 0.15)
        == evaluation.NO_CONTACT
    )
    # Starts only 100 ms after foot strike: must remain reference-ambiguous.
    assert (
        evaluation.reference_for_window(10, 30, 100.0, events, "Left", 0.15)
        is None
    )


def test_pressure_columns_require_exact_1_to_16():
    header = ["x"] + [f"leftPressure{i}_N_cm___" for i in range(1, 17)] + ["y"]
    indices = evaluation.pressure_column_indices(header, "Left")
    assert indices == list(range(1, 17))

    bad = ["x"] + [f"leftPressure{i}_N_cm___" for i in range(1, 16)]
    with pytest.raises(ValueError, match="expected 1..16"):
        evaluation.pressure_column_indices(bad, "Left")


def test_select_center_uses_lower_center_after_equal_metric_tie():
    plan = {
        "calibration": {
            "refusal_half_width": 0.05,
            "candidate_center_thresholds": [0.30, 0.50],
        }
    }
    windows = [
        {"feature": 0.90, "reference": evaluation.CONTACT},
        {"feature": 0.80, "reference": evaluation.CONTACT},
        {"feature": 0.10, "reference": evaluation.NO_CONTACT},
        {"feature": 0.20, "reference": evaluation.NO_CONTACT},
    ]
    center, rows = evaluation.select_center(windows, plan)
    assert center == 0.30
    assert all(row["balanced_accuracy"] == 1.0 for row in rows)


def test_zip_eocd_and_central_directory_parsers():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("researchdata/P02_S01/SYNC_DATA/example.csv", b"abc" * 100)
    data = buffer.getvalue()
    eocd = acquisition.parse_eocd(data, 0)
    assert eocd["total_entries"] == 1
    central = data[
        eocd["central_offset"] : eocd["central_offset"] + eocd["central_size"]
    ]
    entries = acquisition.parse_central_directory(central)
    assert list(entries) == ["researchdata/P02_S01/SYNC_DATA/example.csv"]
    entry = next(iter(entries.values()))
    assert entry["method"] == 8
    assert entry["uncompressed_size"] == 300


def test_select_manifest_entries_requires_frozen_selection_hash():
    rows = [
        {
            "full_name": "/P02_S01/SYNC_DATA/a.csv",
            "size": 3,
            "sha256": "x" * 64,
        }
    ]
    manifest = {
        "files": rows,
        "selection_sha256": acquisition.canonical_selection_hash(rows),
    }
    entries = {
        "researchdata/P02_S01/SYNC_DATA/a.csv": {
            "method": 8,
            "uncompressed_size": 3,
            "compressed_size": 3,
            "local_header_offset": 0,
            "crc32": 0,
            "flags": 0,
        }
    }
    selected = acquisition.select_manifest_entries(manifest, entries)
    assert len(selected) == 1

    manifest["selection_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="selection hash mismatch"):
        acquisition.select_manifest_entries(manifest, entries)


def test_normalization_is_unlabeled_and_bounded():
    normalized, p5, p95 = evaluation.normalize_signal([float(i) for i in range(101)])
    assert p5 == pytest.approx(5.0)
    assert p95 == pytest.approx(95.0)
    assert min(normalized) == 0.0
    assert max(normalized) == 1.0


def test_balanced_accuracy_counts_refusal_as_incorrect():
    windows = [
        {"feature": 0.9, "reference": evaluation.CONTACT},
        {"feature": 0.5, "reference": evaluation.CONTACT},
        {"feature": 0.1, "reference": evaluation.NO_CONTACT},
        {"feature": 0.5, "reference": evaluation.NO_CONTACT},
    ]
    metrics = evaluation.shallow_metrics(windows, center=0.5, refusal_half_width=0.05)
    assert metrics["balanced_accuracy"] == pytest.approx(0.5)
    assert metrics["coverage"] == pytest.approx(0.5)
    assert metrics["refusals"] == 2
