"""Regression checks for the comprehensive Plan 0147 crosswalk artifact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from onto_canon6.packs.linguistic_crosswalk_v1 import LinguisticCrosswalkV1
from onto_canon6.packs.semantic_provenance import SemanticMappingRecord


def _payload() -> dict[str, object]:
    """Load the exhaustive committed record rather than a reduced fixture."""

    path = Path(__file__).parents[2] / "docs/runs/artifacts/plan0147_linguistic_crosswalk_v1.json"
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def test_crosswalk_preserves_full_population_and_reviewed_sumo_outcomes() -> None:
    """Keep every mapping and the reviewed 8/26 SUMO result non-promotional."""

    crosswalk = LinguisticCrosswalkV1.model_validate(_payload())
    assert crosswalk.input_mapping_count == 46150
    assert crosswalk.reviewed_record_count == 34
    assert (
        crosswalk.input_mapping_count + crosswalk.reviewed_record_count
        == len(crosswalk.records)
        == 46184
    )
    mapping_path = (
        Path(__file__).parents[2] / "ontology_packs/linguistic_core/0.3.0/semantic_mappings.jsonl"
    )
    donor_mappings = tuple(
        SemanticMappingRecord.model_validate_json(line)
        for line in mapping_path.read_text(encoding="utf-8").splitlines()
    )
    assert crosswalk.input_mapping_count == len(donor_mappings)
    assert (crosswalk.candidate_count, crosswalk.rejected_count, crosswalk.unresolved_count) == (
        2263,
        8,
        43913,
    )
    assert crosswalk.verified_count == 0
    reviewed = [item for item in crosswalk.records if item.source_key == "sumo_governed_review_v1"]
    assert len(reviewed) == 34
    assert sum(item.state == "rejected" for item in reviewed) == 8


def test_crosswalk_rejects_promotion_and_count_preserving_corruption() -> None:
    """Reject a forged verified state and stale digest even if row count remains fixed."""

    payload = _payload()
    records = cast(list[dict[str, object]], payload["records"])
    records[0]["state"] = "verified"
    with pytest.raises(ValidationError):
        LinguisticCrosswalkV1.model_validate(payload)
