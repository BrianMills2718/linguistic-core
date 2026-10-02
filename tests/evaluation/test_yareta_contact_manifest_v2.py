from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "evaluation" / "load_bearing_contact" / "discover_yareta_v2.py"
PLAN_PATH = ROOT / "evaluation" / "load_bearing_contact" / "experiment_plan_v2.json"

SPEC = importlib.util.spec_from_file_location("discover_yareta_v2", MODULE_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


@pytest.fixture
def plan():
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _row(participant: str, trial_type: str, number: str, ext: str, i: int):
    area = "SYNC_DATA" if ext == "csv" else "RAW_DATA"
    name = f"{participant}_S01_{trial_type}_{number}.{ext}"
    return {
        "resId": f"id-{i}",
        "metadata": {
            "file": {
                "fullName": f"/{participant}_S01/{area}/{name}",
                "name": name,
                "size": 100 + i,
            },
            "checksums": {"SHA-256": f"{i:064x}"},
        },
    }


def test_participant_split_is_disjoint_and_excludes_p01(plan):
    selected = mod.selected_participants(plan)
    assert "P01" not in selected
    assert selected == {"P02", "P03", "P04", "P05", "P06", "P07", "P08", "P09", "P10"}
    assert set(plan["participant_split"]["calibration"]).isdisjoint(
        plan["participant_split"]["evaluation"]
    )


def test_selection_accepts_only_preregistered_walking_pairs(plan):
    rows = [
        _row("P02", "Gait", "01", "csv", 1),
        _row("P02", "Gait", "01", "c3d", 2),
        _row("P03", "SlowGait", "02", "csv", 3),
        _row("P03", "SlowGait", "02", "c3d", 4),
        _row("P09", "FastGait", "01", "csv", 5),
        _row("P09", "FastGait", "01", "c3d", 6),
        _row("P01", "Gait", "01", "csv", 7),
        {
            "resId": "id-8",
            "metadata": {
                "file": {
                    "fullName": "/P02_S01/SYNC_DATA/P02_S01_TUG_01.csv",
                    "name": "P02_S01_TUG_01.csv",
                    "size": 100,
                },
                "checksums": {"SHA-256": "8" * 64},
            },
        },
    ]
    selected = mod.select_manifest_rows(rows, plan)
    assert [row["name"] for row in selected] == [
        "P02_S01_Gait_01.c3d",
        "P02_S01_Gait_01.csv",
        "P03_S01_SlowGait_02.c3d",
        "P03_S01_SlowGait_02.csv",
        "P09_S01_FastGait_01.c3d",
        "P09_S01_FastGait_01.csv",
    ]


def test_pair_validation_rejects_missing_counterpart(plan):
    rows = [
        {
            "id": "x",
            "name": "P02_S01_Gait_01.csv",
            "full_name": "/P02_S01/SYNC_DATA/P02_S01_Gait_01.csv",
            "size": 10,
            "sha256": "a" * 64,
            "participant": "P02",
            "trial_type": "Gait",
            "trial_number": "01",
            "extension": "csv",
            "stem": "P02_S01_Gait_01",
        }
    ]
    with pytest.raises(ValueError, match="unpaired"):
        mod.validate_pairs(rows, plan)


def test_selection_hash_is_order_sensitive_to_manifest_content_but_deterministic():
    rows = [
        {"name": "a", "id": "1", "sha256": "x"},
        {"name": "b", "id": "2", "sha256": "y"},
    ]
    assert mod.canonical_selection_hash(rows) == mod.canonical_selection_hash(rows)
    assert mod.canonical_selection_hash(rows) != mod.canonical_selection_hash(list(reversed(rows)))
