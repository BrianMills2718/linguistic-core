"""Focused M2 finite-inventory and coverage-matrix tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from linguistic_core.first_release_inventory_v1 import (
    CONSTRUCTION_AXES,
    DOMAIN_AXES,
    FirstReleaseInventoryV1,
    InventoryError,
    expand_coverage_matrix,
    load_and_validate_inventory,
    render_inventory_markdown,
)

ROOT = Path(__file__).parents[2]
INVENTORY_PATH = ROOT / "config/first_release_inventory_v1.yaml"


def test_canonical_inventory_is_finite_pinned_and_matrix_complete() -> None:
    inventory, report = load_and_validate_inventory(ROOT, INVENTORY_PATH)

    assert report.publication_status == "not_authorized"
    assert report.selected_donor_count == 3
    assert {item.source_key for item in inventory.selected_donors} == {
        "propbank_frames_34",
        "framenet_17",
        "sumo_root_kif",
    }
    assert len(report.coverage_cells) == len(CONSTRUCTION_AXES) * len(DOMAIN_AXES) == 80
    assert (
        len({(item.construction, item.domain) for item in report.coverage_cells}) == 80
    )
    assert report.coverage_counts["explicit_gap"] == 8
    assert report.not_yet_retained_field_count == 1
    assert [
        item.components[0].count.selected for item in inventory.selected_donors
    ] == [
        7566,
        1221,
        46,
    ]
    assert "Publication status: **not_authorized**" in render_inventory_markdown(
        inventory, report
    )


def test_every_selected_component_has_field_and_rights_dispositions() -> None:
    inventory, _report = load_and_validate_inventory(ROOT, INVENTORY_PATH)
    for donor in inventory.selected_donors:
        assert donor.rights.evidence
        assert donor.rights.release_condition
        for component in donor.components:
            assert component.fields
            assert all(field.reason for field in component.fields)

    frame_fields = {
        field.field: (field.disposition, field.implementation_state)
        for donor in inventory.selected_donors
        if donor.family == "framenet"
        for component in donor.components
        for field in component.fields
    }
    assert frame_fields["frame.semantic_types"] == ("exclude", "not_applicable")
    assert frame_fields["frame_elements.semantic_types"] == ("include", "retained")


def test_source_identity_drift_fails_visibly(tmp_path: Path) -> None:
    payload = yaml.safe_load(INVENTORY_PATH.read_text(encoding="utf-8"))
    payload["selected_donors"][0]["identity"] = (
        "git:commit=" + "0" * 40 + ";tree=" + "0" * 40
    )
    changed = tmp_path / "inventory.yaml"
    changed.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    with pytest.raises(InventoryError, match="INVENTORY_SOURCE_IDENTITY_MISMATCH"):
        load_and_validate_inventory(ROOT, changed)


def test_evidence_hash_drift_fails_visibly(tmp_path: Path) -> None:
    copied = tmp_path / "repo"
    copied.mkdir()
    shutil.copytree(ROOT / "config", copied / "config")
    shutil.copytree(ROOT / "docs", copied / "docs")
    inventory_path = copied / "config/first_release_inventory_v1.yaml"
    source_manifest = copied / "config/linguistic_sources_v1.yaml"
    source_manifest.write_text(
        source_manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(InventoryError, match="INVENTORY_EVIDENCE_DRIFT"):
        load_and_validate_inventory(copied, inventory_path)


def test_structured_component_count_drift_fails_visibly(tmp_path: Path) -> None:
    payload = yaml.safe_load(INVENTORY_PATH.read_text(encoding="utf-8"))
    payload["selected_donors"][2]["components"][0]["count"]["selected"] = 47
    changed = tmp_path / "inventory.yaml"
    changed.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    with pytest.raises(InventoryError, match="INVENTORY_COMPONENT_COUNT_MISMATCH"):
        load_and_validate_inventory(ROOT, changed)


def test_missing_axis_and_unselected_source_are_rejected() -> None:
    payload = yaml.safe_load(INVENTORY_PATH.read_text(encoding="utf-8"))
    payload["coverage_rules"].pop()
    with pytest.raises(ValueError, match="every construction exactly once"):
        FirstReleaseInventoryV1.model_validate(payload)

    payload = yaml.safe_load(INVENTORY_PATH.read_text(encoding="utf-8"))
    payload["coverage_rules"][0]["default"]["source_keys"].append("nombank")
    inventory = FirstReleaseInventoryV1.model_validate(payload)
    with pytest.raises(InventoryError, match="COVERAGE_REFERENCES_UNSELECTED_SOURCE"):
        expand_coverage_matrix(inventory)


def test_retained_outputs_match_canonical_execution() -> None:
    inventory, report = load_and_validate_inventory(ROOT, INVENTORY_PATH)
    retained = json.loads(
        (ROOT / "evaluation/first_release_inventory/coverage_matrix_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert retained["inventory_revision"] == inventory.revision
    assert retained["cells"] == [
        item.model_dump(mode="json") for item in report.coverage_cells
    ]
