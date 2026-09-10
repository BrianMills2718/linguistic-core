"""Focused M4 acquisition mapping integration checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from linguistic_core.contracts import PackRef
from linguistic_core.m4_acquisition_mapping_v1 import (
    build_report,
    load_jsonl,
    load_m3_evidence,
    render_report,
)
from linguistic_core.semantic_construction_v1 import load_cases, load_exact_pack_closure

ROOT = Path(__file__).parents[2]
SELECTION = ROOT / "evaluation/m4_acquisition_mapping/acquisition_mapping_cases_v1.json"
CASES = ROOT / "evaluation/semantic_construction/acquisition_cases_v1.json"
DONOR = ROOT / "ontology_packs/linguistic_core/0.3.0/semantic_mappings.jsonl"


def _report(*, donor_rows=None, manifest_case_ids=None):
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    cases = tuple(
        case for case in load_cases(CASES) if case.case_id in set(selection["case_ids"])
    )
    closure = load_exact_pack_closure(
        ROOT / "ontology_packs", PackRef(pack_id="linguistic_core", pack_version="0.3.3")
    )
    return build_report(
        closure=closure,
        cases=cases,
        case_manifest=str(SELECTION.relative_to(ROOT)),
        donor_mapping_asset=str(DONOR.relative_to(ROOT)),
        predicate_relation_asset="ontology_packs/linguistic_core/0.3.3/predicate_relations.jsonl",
        role_correspondence_asset="ontology_packs/linguistic_core/0.3.3/role_correspondences.jsonl",
        donor_rows=tuple(load_jsonl(DONOR) if donor_rows is None else donor_rows),
        manifest_case_ids=manifest_case_ids,
    )


def test_acquisition_mapping_binds_donor_roles_and_direction() -> None:
    report = _report()
    assert report.failed == 0
    assert report.passed == 3
    assert report.candidate_count == 1
    mapping = report.directional_mappings[0]
    assert mapping.source_predicate_id == "lc:buy_purchase"
    assert mapping.target_predicate_id == "lc:acquire_get_obtain"
    assert mapping.conditions == ("commercial_transaction",)
    assert mapping.lost_distinctions == ("commercial_consideration",)
    assert len(mapping.role_transforms) == 3
    assert all(item.source_donor.source_key == "propbank_nltk" for item in mapping.role_transforms)
    assert mapping.source_evidence.roleset_id == "buy.01"
    assert mapping.source_evidence.arguments[2] == ("ARG2", "7", "8", "from Dresser")
    assert mapping.ambiguity_disposition == "resolved_by_exact_source_alignment"
    assert mapping.role_transforms[0].donor_assertion == "source_native_propbank_role"


def test_reverse_and_role_swap_remain_explicit_rejections() -> None:
    report = _report()
    cases = {item.case_id: item for item in report.cases}
    assert cases["acquisition_to_purchase_rejected"].observed_status == "rejected"
    assert cases["acquisition_to_purchase_rejected"].reason.startswith(
        "MAPPING_DIRECTION_UNSUPPORTED"
    )
    assert cases["buyer_seller_swap_rejected"].reason.startswith("ROLE_FILLER_MISMATCH")
    assert "Reverse direction" in render_report(report)


def test_missing_donor_role_evidence_fails_closed() -> None:
    rows = [
        row
        for row in load_jsonl(DONOR)
        if row.get("canonical_id") != "lc:buy_purchase:lc.role.seller"
    ]
    with pytest.raises(ValueError, match="M4_DONOR_ROLE_EVIDENCE_MISSING"):
        _report(donor_rows=rows)


def test_forged_donor_provenance_fails_closed() -> None:
    rows = list(load_jsonl(DONOR))
    for row in rows:
        if row.get("canonical_id") == "lc:buy_purchase:lc.role.buyer" and row.get("source_key") == "propbank_nltk":
            row["source_id"] = "buy-01:ARG9"
            break
    with pytest.raises(ValueError, match="M4_DONOR_PROVENANCE_INVALID"):
        _report(donor_rows=rows)


def test_m3_provenance_drift_fails_closed(tmp_path: Path) -> None:
    payload = json.loads((ROOT / "evaluation/propbank_examples/propbank_examples_reconciliation_v1.json").read_text())
    payload["source_tree_sha"] = "0" * 40
    path = tmp_path / "reconciliation.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="M4_M3_EVIDENCE_PROVENANCE_DRIFT"):
        load_m3_evidence(path)


def test_manifest_extra_or_missing_ids_fails_closed() -> None:
    ids = ("purchase_to_acquisition_allowed", "acquisition_to_purchase_rejected", "buyer_seller_swap_rejected")
    with pytest.raises(ValueError, match="M4_SELECTION_MANIFEST_MISMATCH"):
        _report(manifest_case_ids=ids + ("extra",))
    with pytest.raises(ValueError, match="M4_SELECTION_MANIFEST_MISMATCH"):
        _report(manifest_case_ids=ids[:2])


def test_runner_json_mode_exposes_the_typed_candidate_report() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_m4_acquisition_mapping_v1.py", "--json"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "m4-acquisition-mapping-report.v1"
    assert payload["passed"] == 3
    assert payload["failed"] == 0
    assert payload["directional_mappings"][0]["review_status"] == "candidate"
