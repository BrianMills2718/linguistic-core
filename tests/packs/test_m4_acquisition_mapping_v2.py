"""Focused M4 v2 acquisition mapping checks with predicate-local role identities."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from linguistic_core.contracts import PackRef
from linguistic_core.m4_acquisition_mapping_v1 import build_report as build_report_v1, load_jsonl, load_m3_evidence
from linguistic_core.m4_acquisition_mapping_v2 import LocalRoleResolutionError, build_report, render_report
from linguistic_core.role_definition_v1 import RoleDefinitionProbeInputV1, load_probe_input
from linguistic_core.semantic_construction_v1 import load_cases, load_exact_pack_closure

ROOT = Path(__file__).parents[2]
SELECTION = ROOT / "evaluation/m4_acquisition_mapping/acquisition_mapping_cases_v1.json"
CASES = ROOT / "evaluation/semantic_construction/acquisition_cases_v1.json"
DONOR = ROOT / "ontology_packs/linguistic_core/0.3.0/semantic_mappings.jsonl"
ROLE_DEFINITIONS = ROOT / "evaluation/m4_role_definitions/role_definition_probe_v1.json"
RECONCILIATION = ROOT / "evaluation/propbank_examples/propbank_examples_reconciliation_v1.json"


def _common():
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    ids = tuple(selection["case_ids"])
    cases = tuple(case for case in load_cases(CASES) if case.case_id in set(ids))
    closure = load_exact_pack_closure(ROOT / "ontology_packs", PackRef(pack_id="linguistic_core", pack_version="0.3.3"))
    return ids, cases, closure


def _v1():
    ids, cases, closure = _common()
    return build_report_v1(
        closure=closure,
        cases=cases,
        case_manifest=str(SELECTION.relative_to(ROOT)),
        donor_mapping_asset=str(DONOR.relative_to(ROOT)),
        predicate_relation_asset="ontology_packs/linguistic_core/0.3.3/predicate_relations.jsonl",
        role_correspondence_asset="ontology_packs/linguistic_core/0.3.3/role_correspondences.jsonl",
        donor_rows=load_jsonl(DONOR),
        m3_evidence=load_m3_evidence(RECONCILIATION),
        m3_reconciliation_asset=str(RECONCILIATION.relative_to(ROOT)),
        manifest_case_ids=ids,
    )


def _v2(role_input: RoleDefinitionProbeInputV1 | None = None):
    ids, cases, closure = _common()
    return build_report(
        closure=closure,
        cases=cases,
        case_manifest=str(SELECTION.relative_to(ROOT)),
        donor_mapping_asset=str(DONOR.relative_to(ROOT)),
        predicate_relation_asset="ontology_packs/linguistic_core/0.3.3/predicate_relations.jsonl",
        role_correspondence_asset="ontology_packs/linguistic_core/0.3.3/role_correspondences.jsonl",
        donor_rows=load_jsonl(DONOR),
        m3_evidence=load_m3_evidence(RECONCILIATION),
        m3_reconciliation_asset=str(RECONCILIATION.relative_to(ROOT)),
        manifest_case_ids=ids,
        role_definition_asset=str(ROLE_DEFINITIONS.relative_to(ROOT)),
        role_definition_input=role_input or load_probe_input(ROLE_DEFINITIONS),
        role_definition_asset_sha256=hashlib.sha256(ROLE_DEFINITIONS.read_bytes()).hexdigest(),
    )


def _mutated(mutator) -> RoleDefinitionProbeInputV1:
    payload = json.loads(ROLE_DEFINITIONS.read_text(encoding="utf-8"))
    mutator(payload)
    return RoleDefinitionProbeInputV1.model_validate_json(json.dumps(payload))


def test_v2_preserves_the_complete_v1_receipt() -> None:
    assert _v2().base_report.model_dump(mode="json") == _v1().model_dump(mode="json")


def test_local_ids_enrich_without_changing_global_role_pairs_or_donor_evidence() -> None:
    mapping = _v2().localized_mappings[0]
    observed = tuple(
        (item.source_role_definition_id, item.target_role_definition_id, item.global_transform.source_role_id, item.global_transform.target_role_id)
        for item in mapping.localized_role_transforms
    )
    assert observed == (
        ("lc.roledef.buy_purchase.buyer", "lc.roledef.acquire_get_obtain.recipient", "lc.role.buyer", "lc.role.recipient"),
        ("lc.roledef.buy_purchase.goods", "lc.roledef.acquire_get_obtain.theme", "lc.role.goods", "lc.role.theme"),
        ("lc.roledef.buy_purchase.seller", "lc.roledef.acquire_get_obtain.source", "lc.role.seller", "lc.role.source"),
    )
    assert mapping.localized_role_transforms[0].global_transform.source_donor.source_id == "buy-01:ARG0"


def test_missing_or_ambiguous_local_grounding_fails_closed() -> None:
    def missing(payload):
        payload["predicate_schemas"][0]["roles"] = [role for role in payload["predicate_schemas"][0]["roles"] if role["grounded_role_id"] != "lc.role.buyer"]
    with pytest.raises(LocalRoleResolutionError, match="M4_V2_LOCAL_ROLE_MISSING"):
        _v2(_mutated(missing))

    def ambiguous(payload):
        payload["predicate_schemas"][0]["roles"].append({
            "role_definition_id": "lc.roledef.buy_purchase.purchaser",
            "predicate_id": "lc:buy_purchase",
            "local_name": "purchaser",
            "grounded_role_id": "lc.role.buyer",
            "expected_filler_type": None,
            "min_count": 1,
            "max_count": 1,
            "presentation_ordinal": 3,
            "constraints": [],
        })
    with pytest.raises(LocalRoleResolutionError, match="M4_V2_LOCAL_ROLE_AMBIGUOUS"):
        _v2(_mutated(ambiguous))


def test_declared_local_transform_drift_fails_closed() -> None:
    def mutate(payload):
        payload["acquisition_transforms"][0]["target_role_definition_id"] = "lc.roledef.acquire_get_obtain.theme"
    with pytest.raises(LocalRoleResolutionError, match="M4_V2_LOCAL_TRANSFORM_DECLARATION_DRIFT"):
        _v2(_mutated(mutate))


def test_v2_keeps_v1_reverse_and_role_swap_rejections() -> None:
    results = {item.case_id: item for item in _v2().base_report.cases}
    assert results["acquisition_to_purchase_rejected"].reason.startswith("MAPPING_DIRECTION_UNSUPPORTED")
    assert results["buyer_seller_swap_rejected"].reason.startswith("ROLE_FILLER_MISMATCH")


def test_report_and_runner_expose_v2_local_role_identity() -> None:
    report = _v2()
    assert report.role_definition_asset_sha256 == hashlib.sha256(ROLE_DEFINITIONS.read_bytes()).hexdigest()
    text = render_report(report)
    assert "lc.roledef.buy_purchase.buyer" in text
    assert "V1 receipt digest" in text

    result = subprocess.run(
        [sys.executable, "scripts/run_m4_acquisition_mapping_v2.py", "--json"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "m4-acquisition-mapping-report.v2"
    assert payload["base_report"]["schema_version"] == "m4-acquisition-mapping-report.v1"
    assert len(payload["localized_mappings"][0]["localized_role_transforms"]) == 3
