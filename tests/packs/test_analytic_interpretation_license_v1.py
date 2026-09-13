"""Analytic consumer schema probe for InterpretationLicense."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from linguistic_core.relation_assertion_v1 import (
    RelationAssertionBundleV1,
    load_relation_assertion_bundle,
    validate_relation_assertion_bundle,
)

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "evaluation/m4_role_definitions/analytic_interpretation_license_v1.json"


def _bundle() -> RelationAssertionBundleV1:
    return load_relation_assertion_bundle(FIXTURE)


def _payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _validated(payload: dict[str, object]) -> RelationAssertionBundleV1:
    return RelationAssertionBundleV1.model_validate_json(json.dumps(payload))


def test_interpretation_license_composes_nested_semantic_binding() -> None:
    bundle = _bundle()
    report = validate_relation_assertion_bundle(bundle)
    assert report.schema_count == 2
    assert report.assertion_count == 2
    assert report.relation_assertion_filler_count == 1
    assert report.top_assertion_id == "assert:analytic.interpretation-license.effect-1"
    license_assertion = next(item for item in bundle.assertions if item.assertion_id == report.top_assertion_id)
    nested = next(item for item in license_assertion.bindings if item.role_definition_id.endswith(".semantic_binding"))
    assert nested.filler.filler_kind == "relation_assertion"
    assert nested.filler.filler_id == "assert:analytic.semantic-binding.exposure"

def test_interpretation_license_role_shape_matches_analytic_contract() -> None:
    schema = next(item for item in _bundle().schemas if item.relation_schema_id == "analytic:interpretation_license")
    expected = {
        "method_result": ("analytic:MethodResult", 1, 1),
        "semantic_binding": ("analytic:semantic_binding", 1, None),
        "world_model": ("analytic:WorldModel", 0, 1),
        "observation_model": ("analytic:ObservationModel", 0, None),
        "assumption": ("analytic:Assumption", 0, None),
        "design_condition": ("analytic:DesignCondition", 0, None),
        "provenance": ("analytic:Provenance", 1, None),
        "scope": ("analytic:Scope", 0, 1),
        "licenses_claim_type": ("analytic:ClaimType", 1, None),
    }
    observed = {
        role.local_name: (role.expected_filler_type, role.min_count, role.max_count)
        for role in schema.roles
    }
    assert observed == expected
    assert schema.owner_namespace == "analytic"
    assert all(role.role_definition_id.startswith("analytic.roledef.interpretation_license.") for role in schema.roles)


def test_license_requires_provenance() -> None:
    payload = _payload()
    payload["assertions"][1]["bindings"] = [
        item
        for item in payload["assertions"][1]["bindings"]
        if not item["role_definition_id"].endswith(".provenance")
    ]
    with pytest.raises(ValueError, match="RELATION_ASSERTION_ROLE_MIN_COUNT"):
        validate_relation_assertion_bundle(_validated(payload))


def test_single_world_model_cardinality_is_enforced() -> None:
    payload = _payload()
    world_model = next(
        item for item in payload["assertions"][1]["bindings"]
        if item["role_definition_id"].endswith(".world_model")
    )
    payload["assertions"][1]["bindings"].append(world_model)
    with pytest.raises(ValueError, match="RELATION_ASSERTION_ROLE_MAX_COUNT"):
        validate_relation_assertion_bundle(_validated(payload))

def test_semantic_binding_cannot_be_flattened_to_plain_reference() -> None:
    payload = _payload()
    nested = next(
        item for item in payload["assertions"][1]["bindings"]
        if item["role_definition_id"].endswith(".semantic_binding")
    )
    nested["filler"]["filler_kind"] = "reference"
    with pytest.raises(ValueError, match="RELATION_ASSERTION_FILLER_REQUIRED"):
        validate_relation_assertion_bundle(_validated(payload))


def test_generic_objectification_runner_accepts_analytic_fixture() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_relation_assertion_probe_v1.py",
            "--input",
            str(FIXTURE),
            "--json",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "relation-assertion-probe-report.v1"
    assert payload["assertion_count"] == 2
    assert payload["relation_assertion_filler_count"] == 1
