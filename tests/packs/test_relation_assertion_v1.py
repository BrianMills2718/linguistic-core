"""First-class grouped relation assertions and objectification checks."""

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
FIXTURE = ROOT / "evaluation/m4_role_definitions/world_substrate_objectification_v1.json"


def _bundle() -> RelationAssertionBundleV1:
    return load_relation_assertion_bundle(FIXTURE)


def _payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _validated(payload: dict[str, object]) -> RelationAssertionBundleV1:
    return RelationAssertionBundleV1.model_validate_json(json.dumps(payload))


def test_world_substrate_causal_event_objectifies_semantic_binding() -> None:
    bundle = _bundle()
    report = validate_relation_assertion_bundle(bundle)
    assert report.schema_count == 2
    assert report.assertion_count == 2
    assert report.relation_assertion_filler_count == 1
    assert report.top_assertion_id == "assert:event.give.1"
    event = next(item for item in bundle.assertions if item.assertion_id == report.top_assertion_id)
    nested = next(binding for binding in event.bindings if binding.role_definition_id.endswith(".semantic_binding"))
    assert nested.filler.filler_kind == "relation_assertion"
    assert nested.filler.filler_id == "assert:binding.give.1"

def test_missing_nested_assertion_fails_closed() -> None:
    payload = _payload()
    payload["assertions"][1]["bindings"][1]["filler"]["filler_id"] = "assert:missing"
    bundle = _validated(payload)
    with pytest.raises(ValueError, match="RELATION_ASSERTION_FILLER_MISSING"):
        validate_relation_assertion_bundle(bundle)


def test_self_reference_fails_closed() -> None:
    payload = _payload()
    payload["assertions"][1]["bindings"][1]["filler"]["filler_id"] = "assert:event.give.1"
    bundle = _validated(payload)
    with pytest.raises(ValueError, match="RELATION_ASSERTION_SELF_REFERENCE"):
        validate_relation_assertion_bundle(bundle)


def test_binary_reference_cannot_replace_required_objectification() -> None:
    payload = _payload()
    payload["assertions"][1]["bindings"][1]["filler"] = {
        "filler_kind": "reference",
        "filler_id": "assert:binding.give.1",
    }
    bundle = _validated(payload)
    with pytest.raises(ValueError, match="RELATION_ASSERTION_FILLER_REQUIRED"):
        validate_relation_assertion_bundle(bundle)


def test_required_role_cardinality_is_enforced() -> None:
    payload = _payload()
    payload["assertions"][1]["bindings"] = [
        item
        for item in payload["assertions"][1]["bindings"]
        if not item["role_definition_id"].endswith(".resulting_state")
    ]
    bundle = _validated(payload)
    with pytest.raises(ValueError, match="RELATION_ASSERTION_ROLE_MIN_COUNT"):
        validate_relation_assertion_bundle(bundle)

def test_nested_relation_type_mismatch_fails_closed() -> None:
    payload = _payload()
    payload["assertions"] = list(reversed(payload["assertions"]))
    payload["assertions"][1]["relation_schema_id"] = "ws:causal_event"
    bundle = _validated(payload)
    with pytest.raises(ValueError, match="RELATION_ASSERTION_FILLER_TYPE_MISMATCH"):
        validate_relation_assertion_bundle(bundle)


def test_runner_exposes_objectification_probe_report() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_relation_assertion_probe_v1.py", "--json"],
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