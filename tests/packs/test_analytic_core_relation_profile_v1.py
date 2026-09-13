"""Full type-level Evidence → Action analytic relation profile."""

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
FIXTURE = ROOT / "evaluation/m4_role_definitions/analytic_core_relation_profile_v1.json"

EXPECTED_SCHEMAS = {
    "analytic:representation_projection",
    "analytic:representation_transformation",
    "analytic:semantic_binding",
    "analytic:observation_model_profile",
    "analytic:world_model_profile",
    "analytic:analytic_methodology_profile",
    "analytic:inference_relation",
    "analytic:interpretation_license",
    "analytic:decision_method_application",
    "analytic:action_realization",
    "analytic:feedback_update",
}


def _bundle() -> RelationAssertionBundleV1:
    return load_relation_assertion_bundle(FIXTURE)


def _assertion(aid: str):
    return next(item for item in _bundle().assertions if item.assertion_id == aid)


def _fillers(assertion, role_suffix: str, *, kind: str | None = None) -> list[str]:
    result = []
    for item in assertion.bindings:
        if item.role_definition_id.endswith("." + role_suffix):
            if kind is None or item.filler.filler_kind == kind:
                result.append(item.filler.filler_id)
    return result


def test_profile_has_explicit_eleven_relation_schemas() -> None:
    bundle = _bundle()
    assert {item.relation_schema_id for item in bundle.schemas} == EXPECTED_SCHEMAS
    assert all(item.owner_namespace == "analytic" for item in bundle.schemas)
    assert all(not item.relation_schema_id.startswith("lc:") for item in bundle.schemas)
    report = validate_relation_assertion_bundle(bundle)
    assert report.schema_count == 11
    assert report.assertion_count == 12
    assert report.relation_assertion_filler_count == 15
    assert report.top_assertion_id == "assert:analytic.feedback.model-update"


def test_world_and_observation_models_are_first_class_relations() -> None:
    bundle = _bundle()
    ids = {item.assertion_id: item.relation_schema_id for item in bundle.assertions}
    assert ids["assert:analytic.world.diffusion"] == "analytic:world_model_profile"
    assert ids["assert:analytic.observation.exposure"] == "analytic:observation_model_profile"
    binding = _assertion("assert:analytic.binding.exposure")
    assert _fillers(binding, "observation_model", kind="relation_assertion") == [
        "assert:analytic.observation.exposure"
    ]


def test_method_output_becomes_downstream_representation_without_new_identity() -> None:
    inference = _assertion("assert:analytic.inference.effect-model")
    downstream = _assertion("assert:analytic.transform.intervention-simulator")
    license_assertion = _assertion("assert:analytic.license.effect-claim")

    result_id = _fillers(inference, "output", kind="reference")
    downstream_input = _fillers(downstream, "input_representation", kind="reference")
    licensed_result = _fillers(license_assertion, "method_result", kind="reference")

    assert result_id == ["repr:fitted-causal-model-1"]
    assert downstream_input == result_id
    assert licensed_result == result_id


def test_interpretation_license_composes_inference_semantics_and_models() -> None:
    license_assertion = _assertion("assert:analytic.license.effect-claim")
    assert _fillers(license_assertion, "inference", kind="relation_assertion") == [
        "assert:analytic.inference.effect-model"
    ]
    assert _fillers(license_assertion, "semantic_binding", kind="relation_assertion") == [
        "assert:analytic.binding.exposure"
    ]
    assert _fillers(license_assertion, "world_model", kind="relation_assertion") == [
        "assert:analytic.world.diffusion"
    ]
    assert _fillers(license_assertion, "observation_model", kind="relation_assertion") == [
        "assert:analytic.observation.exposure"
    ]
    assert len(_fillers(license_assertion, "provenance", kind="reference")) == 2
    assert _fillers(license_assertion, "licenses_claim_type", kind="reference") == [
        "claim-type:causal-effect"
    ]


def test_decision_action_feedback_are_nested_not_inferred_from_order() -> None:
    decision = _assertion("assert:analytic.decision.intervention-choice")
    action = _assertion("assert:analytic.action.reduce-exposure")
    feedback = _assertion("assert:analytic.feedback.model-update")
    assert _fillers(decision, "licensed_basis", kind="relation_assertion") == [
        "assert:analytic.license.effect-claim"
    ]
    assert _fillers(action, "decision_application", kind="relation_assertion") == [
        "assert:analytic.decision.intervention-choice"
    ]
    assert _fillers(feedback, "action_realization", kind="relation_assertion") == [
        "assert:analytic.action.reduce-exposure"
    ]


def test_top_feedback_composition_reaches_every_schema_type() -> None:
    bundle = _bundle()
    by_id = {item.assertion_id: item for item in bundle.assertions}
    seen: set[str] = set()
    stack = [bundle.top_assertion_id]
    while stack:
        aid = stack.pop()
        if aid in seen:
            continue
        seen.add(aid)
        assertion = by_id[aid]
        for binding in assertion.bindings:
            if binding.filler.filler_kind == "relation_assertion":
                stack.append(binding.filler.filler_id)
    reached_schema_ids = {by_id[aid].relation_schema_id for aid in seen}
    assert reached_schema_ids == EXPECTED_SCHEMAS
    assert "assert:analytic.transform.intervention-simulator" not in seen


def _mutated_bundle(mutator) -> RelationAssertionBundleV1:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mutator(payload)
    return RelationAssertionBundleV1.model_validate_json(json.dumps(payload))


def test_license_provenance_remains_required_in_full_profile() -> None:
    def mutate(payload):
        license_assertion = next(
            item for item in payload["assertions"]
            if item["assertion_id"] == "assert:analytic.license.effect-claim"
        )
        license_assertion["bindings"] = [
            item for item in license_assertion["bindings"]
            if not item["role_definition_id"].endswith(".provenance")
        ]

    with pytest.raises(ValueError, match="RELATION_ASSERTION_ROLE_MIN_COUNT"):
        validate_relation_assertion_bundle(_mutated_bundle(mutate))


def test_nested_license_cannot_be_replaced_by_plain_decision_reference() -> None:
    def mutate(payload):
        decision = next(
            item for item in payload["assertions"]
            if item["assertion_id"] == "assert:analytic.decision.intervention-choice"
        )
        basis = next(
            item for item in decision["bindings"]
            if item["role_definition_id"].endswith(".licensed_basis")
        )
        basis["filler"]["filler_kind"] = "reference"

    with pytest.raises(ValueError, match="RELATION_ASSERTION_FILLER_REQUIRED"):
        validate_relation_assertion_bundle(_mutated_bundle(mutate))


def test_generic_runner_accepts_full_analytic_profile() -> None:
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
    assert payload["schema_count"] == 11
    assert payload["assertion_count"] == 12
    assert payload["relation_assertion_filler_count"] == 15
    assert payload["top_assertion_id"] == "assert:analytic.feedback.model-update"
