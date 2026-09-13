"""Executable loss-aware projection checks for the analytic consumer profile."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from linguistic_core.consumer_projection_v1 import (
    execute_consumer_projection,
    require_canonical_projection_equivalence,
)

ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "evaluation/m4_role_definitions/analytic_core_profile_contract_v1.json"
BINARY_RECEIPT = ROOT / "evaluation/m4_role_definitions/semantic_binding_binary_projection_v1.json"
TABLE_RECEIPT = ROOT / "evaluation/m4_role_definitions/interpretation_license_table_projection_v1.json"

BINARY_ID = "analytic.projection.semantic-binding-binary-v1"
TABLE_ID = "analytic.projection.interpretation-license-table-v1"


def _role(view, local_name: str):
    return next(item for item in view.selected_roles if item.local_name == local_name)


def _omitted(view, local_name: str):
    return next(item for item in view.loss_receipt.omitted_roles if item.local_name == local_name)


def test_semantic_binding_binary_projection_emits_edge_and_loss_receipt() -> None:
    view = execute_consumer_projection(
        MANIFEST,
        projection_id=BINARY_ID,
        source_assertion_id="assert:analytic.binding.exposure",
    )
    assert view.target_view == "binary_edge"
    assert [item.filler_id for item in view.endpoint_fillers] == [
        "column:exposure_score",
        "world-variable:exposure",
    ]
    assert _role(view, "binding_kind").fillers[0].filler_id == "binding-kind:measures"
    assert _omitted(view, "observation_model").fillers[0].filler_kind == "relation_assertion"
    assert _omitted(view, "observation_model").fillers[0].filler_id == "assert:analytic.observation.exposure"
    assert _omitted(view, "scope").fillers[0].filler_id == "scope:posts-2026q2"
    assert _omitted(view, "uncertainty").fillers[0].filler_id == "uncertainty:measurement-u1"
    assert _omitted(view, "provenance").fillers[0].filler_id == "provenance:semantic-review-v1"
    assert view.loss_receipt.loss_classification == "lossy"
    assert view.loss_receipt.canonical_equivalence is False


def test_interpretation_license_table_projection_keeps_summary_and_names_lost_basis() -> None:
    view = execute_consumer_projection(
        MANIFEST,
        projection_id=TABLE_ID,
        source_assertion_id="assert:analytic.license.effect-claim",
    )
    assert view.target_view == "table_row"
    assert view.endpoint_fillers == ()
    assert _role(view, "method_result").fillers[0].filler_id == "repr:fitted-causal-model-1"
    assert _role(view, "scope").fillers[0].filler_id == "scope:posts-2026q2"
    assert _role(view, "licenses_claim_type").fillers[0].filler_id == "claim-type:causal-effect"
    assert _omitted(view, "semantic_binding").fillers[0].filler_id == "assert:analytic.binding.exposure"
    assert _omitted(view, "world_model").fillers[0].filler_id == "assert:analytic.world.diffusion"
    assert _omitted(view, "observation_model").fillers[0].filler_id == "assert:analytic.observation.exposure"
    assert {item.filler_id for item in _omitted(view, "assumption").fillers} == {
        "assumption:no-unmeasured-confounding",
        "assumption:positivity",
    }
    assert len(_omitted(view, "provenance").fillers) == 2
    assert view.loss_receipt.canonical_equivalence is False


def test_lossy_views_refuse_canonical_round_trip_equivalence() -> None:
    for projection_id, assertion_id in (
        (BINARY_ID, "assert:analytic.binding.exposure"),
        (TABLE_ID, "assert:analytic.license.effect-claim"),
    ):
        view = execute_consumer_projection(
            MANIFEST,
            projection_id=projection_id,
            source_assertion_id=assertion_id,
        )
        with pytest.raises(ValueError, match="LOSSY_PROJECTION_CANNOT_ROUND_TRIP_EQUIVALENTLY"):
            require_canonical_projection_equivalence(view)


def test_projection_refuses_wrong_relation_assertion() -> None:
    with pytest.raises(ValueError, match="PROJECTION_SOURCE_RELATION_MISMATCH"):
        execute_consumer_projection(
            MANIFEST,
            projection_id=BINARY_ID,
            source_assertion_id="assert:analytic.license.effect-claim",
        )


def test_projection_refuses_unknown_projection_id() -> None:
    with pytest.raises(ValueError, match="PROFILE_PROJECTION_UNKNOWN"):
        execute_consumer_projection(
            MANIFEST,
            projection_id="analytic.projection:missing",
            source_assertion_id="assert:analytic.binding.exposure",
        )


def test_runner_emits_binary_projection_with_loss_receipt() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_consumer_projection_v1.py",
            "--projection-id",
            BINARY_ID,
            "--assertion-id",
            "assert:analytic.binding.exposure",
            "--json",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "consumer-projection-execution.v1"
    assert payload["target_view"] == "binary_edge"
    assert payload["loss_receipt"]["loss_classification"] == "lossy"
    assert payload["loss_receipt"]["canonical_equivalence"] is False


def test_retained_projection_receipts_match_fresh_execution() -> None:
    cases = (
        (BINARY_ID, "assert:analytic.binding.exposure", BINARY_RECEIPT),
        (TABLE_ID, "assert:analytic.license.effect-claim", TABLE_RECEIPT),
    )
    for projection_id, assertion_id, receipt_path in cases:
        fresh = execute_consumer_projection(
            MANIFEST,
            projection_id=projection_id,
            source_assertion_id=assertion_id,
        ).model_dump(mode="json")
        retained = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert retained == fresh
