"""Construction checks for the candidate predicate-local role-definition contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from linguistic_core.role_definition_v1 import (
    ConsumerRoleProfileV1,
    LocalRoleTransformV1,
    PredicateRoleSchemaV1,
    RoleDefinitionV1,
    build_probe_report,
    load_probe_input,
    resolve_local_transform,
    validate_consumer_profile,
)

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "evaluation/m4_role_definitions/role_definition_probe_v1.json"


def _probe():
    return load_probe_input(FIXTURE)


def _schema(predicate_id: str) -> PredicateRoleSchemaV1:
    return next(
        schema for schema in _probe().predicate_schemas if schema.predicate_id == predicate_id
    )


def test_probe_preserves_local_identity_and_existing_m4_global_pairs() -> None:
    value = _probe()
    report = build_probe_report(value)
    assert report.predicate_schema_count == 3
    assert report.role_definition_count == 9
    assert report.acquisition_transform_count == 3
    assert report.world_substrate_mapping_count == 3
    assert "predicate_local_role_identity" in report.checks

    buy = _schema("lc:buy_purchase")
    acquire = _schema("lc:acquire_get_obtain")
    observed = tuple(
        resolve_local_transform(buy, acquire, transform)
        for transform in value.acquisition_transforms
    )
    assert observed == (
        ("lc.role.buyer", "lc.role.recipient"),
        ("lc.role.goods", "lc.role.theme"),
        ("lc.role.seller", "lc.role.source"),
    )


def test_world_substrate_give_profile_resolves_current_binding_exactly() -> None:
    value = _probe()
    give = _schema("lc:give_transfer")
    assert validate_consumer_profile(give, value.world_substrate_give) == (
        ("giver", "lc.role.donor"),
        ("transferred_object", "lc.role.theme"),
        ("recipient", "lc.role.recipient"),
    )


def test_local_role_identity_is_not_global_role_identity() -> None:
    acquire_theme = _schema("lc:acquire_get_obtain").role_by_id(
        "lc.roledef.acquire_get_obtain.theme"
    )
    give_object = _schema("lc:give_transfer").role_by_id(
        "lc.roledef.give_transfer.transferred_object"
    )
    assert acquire_theme is not None
    assert give_object is not None
    assert acquire_theme.role_definition_id != give_object.role_definition_id
    assert acquire_theme.local_name != give_object.local_name
    assert acquire_theme.grounded_role_id == give_object.grounded_role_id == "lc.role.theme"


def test_duplicate_local_names_fail_closed() -> None:
    role_a = RoleDefinitionV1(
        role_definition_id="lc.roledef.example.first",
        predicate_id="lc:example",
        local_name="participant",
        grounded_role_id="lc.role.agent",
        presentation_ordinal=0,
    )
    role_b = RoleDefinitionV1(
        role_definition_id="lc.roledef.example.second",
        predicate_id="lc:example",
        local_name="participant",
        grounded_role_id="lc.role.theme",
        presentation_ordinal=1,
    )
    with pytest.raises(ValidationError, match="ROLE_DEFINITION_LOCAL_NAME_DUPLICATE"):
        PredicateRoleSchemaV1(predicate_id="lc:example", roles=(role_a, role_b))


def test_invalid_cardinality_fails_closed() -> None:
    with pytest.raises(ValidationError, match="ROLE_DEFINITION_CARDINALITY_INVALID"):
        RoleDefinitionV1(
            role_definition_id="lc.roledef.example.participant",
            predicate_id="lc:example",
            local_name="participant",
            grounded_role_id="lc.role.agent",
            min_count=2,
            max_count=1,
            presentation_ordinal=0,
        )


def test_transform_cannot_silently_reference_role_owned_by_another_predicate() -> None:
    buy = _schema("lc:buy_purchase")
    acquire = _schema("lc:acquire_get_obtain")
    wrong = LocalRoleTransformV1(
        source_role_definition_id="lc.roledef.give_transfer.giver",
        target_role_definition_id="lc.roledef.acquire_get_obtain.recipient",
    )
    with pytest.raises(ValueError, match="LOCAL_ROLE_TRANSFORM_SOURCE_MISSING"):
        resolve_local_transform(buy, acquire, wrong)


def test_consumer_profile_rejects_mechanic_semantics_as_extra_fields() -> None:
    payload = _probe().world_substrate_give.model_dump()
    payload["mechanic_id"] = "mechanism.ownership.give"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ConsumerRoleProfileV1.model_validate(payload)


def test_consumer_profile_rejects_wrong_grounding() -> None:
    profile = _probe().world_substrate_give
    payload = profile.model_dump()
    payload["mappings"][1]["grounded_role_id"] = "lc.role.recipient"
    wrong = ConsumerRoleProfileV1.model_validate(payload)
    with pytest.raises(ValueError, match="CONSUMER_GROUNDED_ROLE_MISMATCH"):
        validate_consumer_profile(_schema("lc:give_transfer"), wrong)


def test_runner_json_mode_exposes_candidate_probe_report() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_role_definition_probe_v1.py", "--json"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "role-definition-probe-report.v1"
    assert payload["role_definition_count"] == 9
    assert payload["world_substrate_mapping_count"] == 3
