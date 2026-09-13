"""Consumer-owned relation schemas expressed in the Linguistic Core grammar."""

from __future__ import annotations

from pathlib import Path

import json
import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from linguistic_core.role_definition_v1 import (
    RelationRoleDefinitionV1,
    RelationSchemaV1,
    build_consumer_relation_schema_probe_report,
    load_consumer_relation_schema_probe,
)

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "evaluation/m4_role_definitions/world_substrate_relation_schema_v1.json"


def _value():
    return load_consumer_relation_schema_probe(FIXTURE)


def test_world_substrate_semantic_binding_uses_consumer_namespace() -> None:
    value = _value()
    schema = value.relation_schema
    assert value.consumer_id == "world-substrate"
    assert schema.relation_schema_id == "ws:semantic_binding"
    assert schema.owner_namespace == "ws"
    assert len(schema.roles) == 7
    assert all(role.role_definition_id.startswith("ws.roledef.semantic_binding.") for role in schema.roles)
    assert all(role.grounded_role_id is None for role in schema.roles)


def test_semantic_binding_role_shape_matches_current_contract() -> None:
    schema = _value().relation_schema
    expected = {
        "sense": ("lc:PredicateSense", 1, 1),
        "participant_profile": ("ws:ParticipantRoleProfile", 1, 1),
        "specialization": ("ws:SemanticSpecialization", 0, 1),
        "causal_class": ("ws:CausalClass", 1, 1),
        "causal_bearer": ("ws:CausalBearer", 0, 1),
        "mechanic": ("ws:Mechanic", 0, 1),
        "interpretation_limit": ("ws:InterpretationLimit", 0, None),
    }
    observed = {
        role.local_name: (role.expected_filler_type, role.min_count, role.max_count)
        for role in schema.roles
    }
    assert observed == expected
    assert "consumer-owned consequence authority" in schema.role_by_name("mechanic").constraints[0]


def test_probe_report_keeps_consumer_schema_outside_lc_namespace() -> None:
    report = build_consumer_relation_schema_probe_report(_value())
    assert report.relation_schema_id == "ws:semantic_binding"
    assert report.owner_namespace == "ws"
    assert report.role_definition_count == 7
    assert report.grounded_role_count == 0
    assert report.ungrounded_role_count == 7
    assert report.repeatable_role_count == 1
    assert "consumer_schema_does_not_become_lc_vocabulary" in report.checks


def test_consumer_relation_cannot_smuggle_lc_ownership() -> None:
    role = RelationRoleDefinitionV1(
        role_definition_id="lc.roledef.semantic_binding.sense",
        relation_schema_id="ws:semantic_binding",
        local_name="sense",
        expected_filler_type="lc:PredicateSense",
        presentation_ordinal=0,
    )
    with pytest.raises(ValidationError, match="RELATION_ROLE_DEFINITION_NAMESPACE_MISMATCH"):
        RelationSchemaV1(
            relation_schema_id="ws:semantic_binding",
            owner_namespace="ws",
            roles=(role,),
        )


def test_relation_schema_owner_must_match_relation_namespace() -> None:
    role = RelationRoleDefinitionV1(
        role_definition_id="ws.roledef.semantic_binding.sense",
        relation_schema_id="ws:semantic_binding",
        local_name="sense",
        expected_filler_type="lc:PredicateSense",
        presentation_ordinal=0,
    )
    with pytest.raises(ValidationError, match="RELATION_SCHEMA_OWNER_NAMESPACE_MISMATCH"):
        RelationSchemaV1(
            relation_schema_id="ws:semantic_binding",
            owner_namespace="lc",
            roles=(role,),
        )


def test_runner_exposes_consumer_relation_probe_report() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_consumer_relation_schema_probe_v1.py", "--json"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "consumer-relation-schema-probe-report.v1"
    assert payload["relation_schema_id"] == "ws:semantic_binding"
    assert payload["role_definition_count"] == 7
