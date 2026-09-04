"""Regression checks for the comprehensive Plan 0147 crosswalk artifact."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from linguistic_core.linguistic_crosswalk_v1 import (
    LinguisticCrosswalkV1,
    append_independent_reviewed_donor_records_v1,
)
from linguistic_core.linguistic_runtime_view_v1 import build_linguistic_runtime_view_receipt_v1
from linguistic_core.semantic_provenance import SemanticMappingRecord


def _payload() -> dict[str, object]:
    """Load the exhaustive committed record rather than a reduced fixture."""

    path = (
        Path(__file__).parents[2] / "docs/runs/artifacts/plan0147_linguistic_crosswalk_v1.json.gz"
    )
    with gzip.open(path, mode="rt", encoding="utf-8") as handle:
        return cast(dict[str, object], json.load(handle))


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
    assert {item.review_status for item in reviewed} == {"independent_review"}
    assert {item.review_status for item in crosswalk.records if item not in reviewed} == {"not_reviewed"}


def test_crosswalk_rejects_promotion_and_count_preserving_corruption() -> None:
    """Reject a forged verified state and stale digest even if row count remains fixed."""

    payload = _payload()
    records = cast(list[dict[str, object]], payload["records"])
    records[0]["state"] = "verified"
    with pytest.raises(ValidationError):
        LinguisticCrosswalkV1.model_validate(payload)


def test_legacy_payload_without_tentatively_verified_count_still_loads() -> None:
    """The additive field must default so the immutable committed artifact still parses."""

    crosswalk = LinguisticCrosswalkV1.model_validate(_payload())
    assert crosswalk.tentatively_verified_count == 0
    assert crosswalk.verified_count == 0


def test_append_independent_review_adds_tentatively_verified_without_mutating_donor_row() -> None:
    """A two-pass review outcome layers a new record on top of, not over, the donor row."""

    crosswalk = LinguisticCrosswalkV1.model_validate(_payload())
    original = next(item for item in crosswalk.records if item.source_key == "framenet_candidate")
    updated = append_independent_reviewed_donor_records_v1(
        crosswalk,
        reviewed_donor_mappings=(
            (original.record_id, original.canonical_id, original.canonical_kind, "tentatively_verified"),
        ),
    )
    # the original donor mapping row is untouched
    replayed_original = next(item for item in updated.records if item.record_id == original.record_id)
    assert replayed_original == original
    assert replayed_original.state == "candidate"
    # exactly one new review record was appended
    assert len(updated.records) == len(crosswalk.records) + 1
    assert updated.tentatively_verified_count == 1
    assert updated.candidate_count == crosswalk.candidate_count
    assert updated.rejected_count == crosswalk.rejected_count
    assert updated.unresolved_count == crosswalk.unresolved_count
    assert updated.verified_count == 0
    review_record = next(item for item in updated.records if item.state == "tentatively_verified")
    assert review_record.canonical_id == original.canonical_id
    assert review_record.source_key == "linguistic_donor_independent_review_v1"
    assert review_record.review_status == "independent_review"
    assert review_record.verification_basis == "automated_two_pass_review"
    assert review_record.producer_method == "independent_review_of_proposal"
    # population-level count reconciliation actually re-validated on load
    LinguisticCrosswalkV1.model_validate(updated.model_dump(mode="json"))


def test_append_independent_review_supports_rejected_and_unresolved_outcomes() -> None:
    """Disagreement/abstention outcomes reconcile too, with `verification_basis="none"`."""

    crosswalk = LinguisticCrosswalkV1.model_validate(_payload())
    rows = [item for item in crosswalk.records if item.source_key == "framenet_candidate"][:2]
    updated = append_independent_reviewed_donor_records_v1(
        crosswalk,
        reviewed_donor_mappings=(
            (rows[0].record_id, rows[0].canonical_id, rows[0].canonical_kind, "rejected"),
            (rows[1].record_id, rows[1].canonical_id, rows[1].canonical_kind, "unresolved"),
        ),
    )
    assert updated.tentatively_verified_count == 0
    assert updated.rejected_count == crosswalk.rejected_count + 1
    assert updated.unresolved_count == crosswalk.unresolved_count + 1
    new_records = [item for item in updated.records if item.source_key == "linguistic_donor_independent_review_v1"]
    assert {item.state for item in new_records} == {"rejected", "unresolved"}
    assert {item.verification_basis for item in new_records} == {"none"}


def test_crosswalk_still_rejects_verified_alongside_tentatively_verified() -> None:
    """`verified_count: Literal[0]` and the unconditional `state=="verified"` ban are untouched."""

    crosswalk = LinguisticCrosswalkV1.model_validate(_payload())
    original = next(item for item in crosswalk.records if item.source_key == "framenet_candidate")
    updated = append_independent_reviewed_donor_records_v1(
        crosswalk,
        reviewed_donor_mappings=(
            (original.record_id, original.canonical_id, original.canonical_kind, "tentatively_verified"),
        ),
    )
    payload = updated.model_dump(mode="json")
    records = cast(list[dict[str, object]], payload["records"])
    # forge the newly appended review record straight to "verified"
    forged = next(item for item in records if item["state"] == "tentatively_verified")
    forged["state"] = "verified"
    forged["verification_basis"] = "none"
    with pytest.raises(ValidationError):
        LinguisticCrosswalkV1.model_validate(payload)
    with pytest.raises(ValidationError):
        LinguisticCrosswalkV1.model_validate({**payload, "verified_count": 1})


def test_runtime_view_stays_inert_with_tentatively_verified_rows_present() -> None:
    """0.4.0's compile-eligibility gate must not react to the new state at all."""

    crosswalk = LinguisticCrosswalkV1.model_validate(_payload())
    original = next(item for item in crosswalk.records if item.source_key == "framenet_candidate")
    updated = append_independent_reviewed_donor_records_v1(
        crosswalk,
        reviewed_donor_mappings=(
            (original.record_id, original.canonical_id, original.canonical_kind, "tentatively_verified"),
        ),
    )
    assert updated.tentatively_verified_count == 1
    receipt = build_linguistic_runtime_view_receipt_v1(updated)
    assert receipt.eligible_record_count == 0
    assert receipt.emitted_predicate_count == 0
    assert receipt.emitted_role_count == 0
    assert receipt.emitted_entity_type_count == 0
    assert receipt.default_activation is False
    assert receipt.input_record_count == len(updated.records)
