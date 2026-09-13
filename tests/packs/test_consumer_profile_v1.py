"""Versioned consumer-profile and loss-aware projection checks."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from linguistic_core.consumer_profile_v1 import (
    ConsumerProfileContractV1,
    load_consumer_profile_contract,
    validate_consumer_profile_contract,
)

ROOT = Path(__file__).parents[2]
PROFILE_DIR = ROOT / "evaluation/m4_role_definitions"
MANIFEST = PROFILE_DIR / "analytic_core_profile_contract_v1.json"
BUNDLE = PROFILE_DIR / "analytic_core_relation_profile_v1.json"


def _manifest_payload() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _validated_manifest(payload: dict[str, object]) -> ConsumerProfileContractV1:
    return ConsumerProfileContractV1.model_validate_json(json.dumps(payload))


def test_analytic_profile_contract_pins_bundle_and_grammar() -> None:
    contract = load_consumer_profile_contract(MANIFEST)
    report = validate_consumer_profile_contract(MANIFEST)
    assert contract.profile_id == "analytic:evidence_to_action"
    assert contract.profile_version == "0.1.0"
    assert contract.owner_namespace == "analytic"
    assert contract.grammar_dependency.relation_schema_version == "relation-schema.v1"
    assert contract.grammar_dependency.relation_assertion_bundle_version == "relation-assertion-bundle.v1"
    assert report.relation_schema_count == 11
    assert report.assertion_count == 12
    assert report.projection_count == 2
    assert report.lossy_projection_count == 2


def test_binary_semantic_binding_projection_declares_qualification_loss() -> None:
    contract = load_consumer_profile_contract(MANIFEST)
    rule = next(item for item in contract.projections if item.target_view == "binary_edge")
    assert rule.source_relation_schema_id == "analytic:semantic_binding"
    assert len(rule.endpoint_role_definition_ids) == 2
    assert rule.endpoint_role_definition_ids == (
        "analytic.roledef.semantic_binding.represented_element",
        "analytic.roledef.semantic_binding.referent",
    )
    assert "analytic.roledef.semantic_binding.binding_kind" in rule.selected_role_definition_ids
    assert set(rule.omitted_role_definition_ids) == {
        "analytic.roledef.semantic_binding.observation_model",
        "analytic.roledef.semantic_binding.scope",
        "analytic.roledef.semantic_binding.uncertainty",
        "analytic.roledef.semantic_binding.provenance",
    }
    assert rule.loss_classification == "lossy"


def test_interpretation_license_table_projection_exposes_only_summary_roles() -> None:
    contract = load_consumer_profile_contract(MANIFEST)
    rule = next(item for item in contract.projections if item.target_view == "table_row")
    assert rule.source_relation_schema_id == "analytic:interpretation_license"
    assert set(rule.selected_role_definition_ids) == {
        "analytic.roledef.interpretation_license.method_result",
        "analytic.roledef.interpretation_license.scope",
        "analytic.roledef.interpretation_license.licenses_claim_type",
    }
    assert "analytic.roledef.interpretation_license.semantic_binding" in rule.omitted_role_definition_ids
    assert "analytic.roledef.interpretation_license.provenance" in rule.omitted_role_definition_ids
    assert rule.loss_classification == "lossy"


def test_source_bundle_digest_drift_fails_closed(tmp_path: Path) -> None:
    manifest = tmp_path / MANIFEST.name
    bundle = tmp_path / BUNDLE.name
    shutil.copy2(MANIFEST, manifest)
    shutil.copy2(BUNDLE, bundle)
    bundle.write_text(bundle.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="CONSUMER_PROFILE_BUNDLE_DIGEST_MISMATCH"):
        validate_consumer_profile_contract(manifest)


def _write_mutated_profile(tmp_path: Path, payload: dict[str, object]) -> Path:
    manifest = tmp_path / MANIFEST.name
    shutil.copy2(BUNDLE, tmp_path / BUNDLE.name)
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest


def test_projection_must_account_for_every_source_role(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload["projections"][0]["omitted_role_definition_ids"].pop()
    manifest = _write_mutated_profile(tmp_path, payload)
    with pytest.raises(ValueError, match="PROFILE_PROJECTION_ROLE_COVERAGE_MISMATCH"):
        validate_consumer_profile_contract(manifest)


def test_nary_binary_projection_cannot_claim_lossless_equivalence(tmp_path: Path) -> None:
    payload = _manifest_payload()
    rule = payload["projections"][0]
    rule["selected_role_definition_ids"] = (
        rule["selected_role_definition_ids"] + rule["omitted_role_definition_ids"]
    )
    rule["omitted_role_definition_ids"] = []
    rule["loss_classification"] = "lossless"
    manifest = _write_mutated_profile(tmp_path, payload)
    with pytest.raises(ValueError, match="PROFILE_NARY_BINARY_PROJECTION_MUST_BE_LOSSY"):
        validate_consumer_profile_contract(manifest)


def test_profile_namespace_is_not_linguistic_core_owned() -> None:
    payload = _manifest_payload()
    payload["owner_namespace"] = "lc"
    with pytest.raises(ValueError, match="CONSUMER_PROFILE_OWNER_NAMESPACE_MISMATCH"):
        _validated_manifest(payload)


def test_manifest_schema_set_must_match_pinned_bundle(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload["relation_schema_ids"].pop()
    manifest = _write_mutated_profile(tmp_path, payload)
    with pytest.raises(ValueError, match="CONSUMER_PROFILE_SCHEMA_SET_MISMATCH"):
        validate_consumer_profile_contract(manifest)


def test_runner_emits_versioned_profile_validation_report() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_consumer_profile_contract_v1.py", "--json"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "consumer-profile-validation-report.v1"
    assert payload["profile_id"] == "analytic:evidence_to_action"
    assert payload["profile_version"] == "0.1.0"
    assert payload["relation_schema_count"] == 11
    assert payload["projection_count"] == 2
