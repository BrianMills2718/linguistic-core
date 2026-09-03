"""Pure (no-LLM) checks for the Slice B two-pass donor-mapping review mechanics."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from onto_canon6.packs.linguistic_crosswalk_v1 import (
    LinguisticCrosswalkV1,
    append_independent_reviewed_donor_records_v1,
)
from onto_canon6.packs.linguistic_donor_review_v1 import (
    DonorMappingReviewCheckpointV1,
    DonorMappingReviewPassV1,
    LinguisticDonorReviewError,
    append_checkpoint_row_v1,
    load_checkpointed_review_results_v1,
    reconcile_two_pass_review_v1,
    reviewed_donor_mappings_from_checkpoints_v1,
    select_merge_kif_framenet_candidate_rows_v1,
)

_DB_PATH = Path(__file__).parents[2] / "data/sumo_plus.db"


def _crosswalk() -> LinguisticCrosswalkV1:
    path = Path(__file__).parents[2] / "docs/runs/artifacts/plan0147_linguistic_crosswalk_v1.json.gz"
    return LinguisticCrosswalkV1.model_validate_json(gzip.open(path, "rb").read())


def _pass(verdict: str) -> DonorMappingReviewPassV1:
    return DonorMappingReviewPassV1(verdict=verdict, rationale="test rationale")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("verdict_a", "verdict_b", "expected"),
    [
        ("supports", "supports", "tentatively_verified"),
        ("contradicts", "contradicts", "rejected"),
        ("supports", "contradicts", "unresolved"),
        ("contradicts", "supports", "unresolved"),
        ("abstain", "supports", "unresolved"),
        ("supports", "abstain", "unresolved"),
        ("abstain", "abstain", "unresolved"),
        ("abstain", "contradicts", "unresolved"),
    ],
)
def test_reconcile_two_pass_review(verdict_a: str, verdict_b: str, expected: str) -> None:
    """Every combination of the 3-way verdict enum reconciles to the documented outcome."""

    outcome = reconcile_two_pass_review_v1(_pass(verdict_a), _pass(verdict_b))
    assert outcome == expected


def test_select_merge_kif_rows_prioritizes_merge_kif_and_excludes_reviewed() -> None:
    """Row selection is real (hits the actual donor DB), deterministic, and Merge.kif-first."""

    crosswalk = _crosswalk()
    rows = select_merge_kif_framenet_candidate_rows_v1(
        crosswalk, donor_database=_DB_PATH, limit=10
    )
    assert len(rows) == 10
    assert all(row.merge_kif_tied for row in rows)
    assert [row.record_id for row in rows] == sorted(row.record_id for row in rows)
    # every selected row is a real, still-unreviewed candidate row
    by_id = {item.record_id: item for item in crosswalk.records}
    for row in rows:
        original = by_id[row.record_id]
        assert original.source_key == "framenet_candidate"
        assert original.state == "candidate"

    # already-reviewed rows are excluded from a subsequent selection
    reviewed = append_independent_reviewed_donor_records_v1(
        crosswalk,
        reviewed_donor_mappings=tuple(
            (row.record_id, row.canonical_id, row.canonical_kind, "tentatively_verified")
            for row in rows[:3]
        ),
    )
    rows_after = select_merge_kif_framenet_candidate_rows_v1(
        reviewed, donor_database=_DB_PATH, limit=10
    )
    assert {row.record_id for row in rows[:3]}.isdisjoint({row.record_id for row in rows_after})


def test_select_merge_kif_rows_deterministic_repeat_call() -> None:
    """Selection is a pure read against immutable inputs -- repeat calls agree exactly."""

    crosswalk = _crosswalk()
    first = select_merge_kif_framenet_candidate_rows_v1(crosswalk, donor_database=_DB_PATH, limit=25)
    second = select_merge_kif_framenet_candidate_rows_v1(crosswalk, donor_database=_DB_PATH, limit=25)
    assert first == second


def test_checkpoint_round_trip_and_projection(tmp_path: Path) -> None:
    """Checkpoints persist per-row, survive reload, and project into the append shape."""

    checkpoint_path = tmp_path / "review_checkpoint.jsonl"
    result = DonorMappingReviewCheckpointV1(
        record_id="lcx1_deadbeefdeadbeefdeadbeef",
        canonical_id="lc:example_predicate",
        canonical_kind="predicate_type",
        model_a="openrouter/deepseek/deepseek-v4-flash",
        model_b="openrouter/minimax/minimax-m3",
        pass_a=_pass("supports"),
        pass_b=_pass("supports"),
        outcome="tentatively_verified",
        cost_usd_a=0.0012,
        cost_usd_b=0.0011,
    )
    assert not checkpoint_path.exists()
    append_checkpoint_row_v1(checkpoint_path, result)
    assert load_checkpointed_review_results_v1(checkpoint_path) == (result,)
    # a second row appends rather than overwrites
    result_2 = result.model_copy(update={"record_id": "lcx1_cafebabecafebabecafebabe"})
    append_checkpoint_row_v1(checkpoint_path, result_2)
    replayed = load_checkpointed_review_results_v1(checkpoint_path)
    assert replayed == (result, result_2)
    mapped = reviewed_donor_mappings_from_checkpoints_v1(replayed)
    assert mapped == (
        ("lcx1_deadbeefdeadbeefdeadbeef", "lc:example_predicate", "predicate_type", "tentatively_verified"),
        ("lcx1_cafebabecafebabecafebabe", "lc:example_predicate", "predicate_type", "tentatively_verified"),
    )
    # each line is valid standalone JSON (checkpoint format is inspectable line-by-line)
    for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
        json.loads(line)


def test_load_checkpoint_missing_file_returns_empty(tmp_path: Path) -> None:
    """No checkpoint file yet means no completed rows -- not an error."""

    assert load_checkpointed_review_results_v1(tmp_path / "absent.jsonl") == ()


def test_select_raises_loud_when_donor_database_has_no_merge_kif_types(tmp_path: Path) -> None:
    """Fail loud rather than silently reviewing an arbitrary/non-prioritized sample."""

    empty_db = tmp_path / "empty.db"
    import sqlite3

    connection = sqlite3.connect(empty_db)
    connection.execute(
        "CREATE TABLE types (id TEXT PRIMARY KEY, description TEXT, source TEXT NOT NULL, "
        "is_process INTEGER DEFAULT 0, domain_module TEXT)"
    )
    connection.execute(
        "CREATE TABLE role_slots (event_sense_id TEXT, named_label TEXT, arg_position TEXT, "
        "abstract_role TEXT, type_constraint TEXT, required INTEGER, source TEXT)"
    )
    connection.commit()
    connection.close()
    with pytest.raises(LinguisticDonorReviewError, match="no Merge.kif-sourced types"):
        select_merge_kif_framenet_candidate_rows_v1(_crosswalk(), donor_database=empty_db)
