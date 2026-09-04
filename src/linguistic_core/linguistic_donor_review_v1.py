"""Two-independent-pass automated review for linguistic_core donor mappings.

Slice B (`docs/plans/goals/2026-09-03-linguistic-core-completeness-resume.md`):
resume verification of the crosswalk's donor mapping claims (PropBank/
FrameNet/SUMO provenance behind `linguistic_core` predicates) through a new
`tentatively_verified` state, reached only through a genuine two-independent-
model-pass review with no self-review -- mirroring this repo's existing
"no proposer verifies its own output" pattern
(`append_reviewed_sumo_role_records_v1`).

This module never proposes a mapping; the mappings under review were already
produced elsewhere (an earlier, unreviewed automated pass recorded on the
donor predicate row). It only runs two independent judgment calls per row and
reconciles them deterministically in code:

- both passes ``supports`` -> ``tentatively_verified``
- either pass ``abstain``, or the two passes disagree -> ``unresolved``
- both passes ``contradicts`` -> ``rejected``

Row selection prioritizes crosswalk rows tied to `Merge.kif`-sourced SUMO
content (ties to the parallel Slice A work), via the donor database's
``role_slots.type_constraint -> types.source`` join -- the only join this
schema offers from a predicate to its originating SUMO module.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from linguistic_core.linguistic_crosswalk_v1 import (
    IndependentReviewOutcome,
    LinguisticCrosswalkV1,
)

_PROMPT_REF = "onto_canon6_plan0147_linguistic_donor_mapping_independent_review@1"
ReviewVerdict = Literal["supports", "contradicts", "abstain"]


class LinguisticDonorReviewError(ValueError):
    """Raised when a donor-mapping review row or reconciliation cannot proceed."""


class DonorMappingRowEvidenceV1(BaseModel):
    """Exact evidence for one FrameNet donor-mapping candidate row under review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1, description="Original crosswalk record under review.")
    canonical_id: str = Field(min_length=1)
    canonical_kind: str = Field(min_length=1)
    predicate_name: str = Field(min_length=1)
    predicate_description: str = Field(min_length=1)
    frame_id: str = Field(min_length=1)
    frame_name: str = Field(min_length=1)
    frame_description: str = Field(min_length=1)
    merge_kif_tied: bool = Field(
        description="Whether >=1 of the predicate's role_slots is typed by a Merge.kif SUMO type."
    )


class DonorMappingReviewPassV1(BaseModel):
    """One independent reviewer pass over one row, native-schema response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: ReviewVerdict = Field(description="This pass's independent judgment.")
    rationale: str = Field(min_length=1, max_length=1000, description="Concise grounded reason.")


class DonorMappingReviewCheckpointV1(BaseModel):
    """One persisted two-pass result for one row -- the checkpoint unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-donor-review-checkpoint-v1"] = (
        "linguistic-donor-review-checkpoint-v1"
    )
    record_id: str
    canonical_id: str
    canonical_kind: str
    model_a: str
    model_b: str
    pass_a: DonorMappingReviewPassV1
    pass_b: DonorMappingReviewPassV1
    outcome: IndependentReviewOutcome
    cost_usd_a: float | None = Field(default=None, ge=0)
    cost_usd_b: float | None = Field(default=None, ge=0)


def reconcile_two_pass_review_v1(
    pass_a: DonorMappingReviewPassV1, pass_b: DonorMappingReviewPassV1
) -> IndependentReviewOutcome:
    """Deterministically reconcile two independent verdicts into one crosswalk outcome.

    agree-supports -> tentatively_verified; either abstains or they disagree ->
    unresolved; agree-contradicts -> rejected. No other combination exists
    because both verdicts are drawn from the same 3-way enum.
    """

    if pass_a.verdict == "supports" and pass_b.verdict == "supports":
        return "tentatively_verified"
    if pass_a.verdict == "contradicts" and pass_b.verdict == "contradicts":
        return "rejected"
    return "unresolved"


def select_merge_kif_framenet_candidate_rows_v1(
    crosswalk: LinguisticCrosswalkV1,
    *,
    donor_database: Path,
    limit: int | None = None,
) -> tuple[DonorMappingRowEvidenceV1, ...]:
    """Select `candidate`-state FrameNet donor rows, prioritizing Merge.kif ties.

    Only rows still in `candidate`/`unresolved` state and not already reviewed
    (no existing review record referencing them) are eligible. Sorted with
    Merge.kif-tied rows first, then by record_id, for a deterministic pilot
    population; `limit` truncates after that ordering.
    """

    database = donor_database.resolve()
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro&immutable=1", uri=True)
    try:
        merge_types = {
            row[0]
            for row in connection.execute("SELECT id FROM types WHERE source = 'sumo:Merge.kif'")
        }
        if not merge_types:
            raise LinguisticDonorReviewError("donor database has no Merge.kif-sourced types")
        placeholders = ",".join("?" * len(merge_types))
        merge_predicates = {
            row[0]
            for row in connection.execute(
                f"SELECT DISTINCT event_sense_id FROM role_slots "
                f"WHERE type_constraint IN ({placeholders})",
                tuple(merge_types),
            )
        }
        already_reviewed = {
            item.source_id
            for item in crosswalk.records
            if item.source_key == "linguistic_donor_independent_review_v1"
        }
        candidates: list[DonorMappingRowEvidenceV1] = []
        for item in crosswalk.records:
            if item.source_key != "framenet_candidate" or item.state != "candidate":
                continue
            if item.record_id in already_reviewed:
                continue
            predicate_name = item.canonical_id.removeprefix("lc:")
            predicate_row = connection.execute(
                "SELECT description FROM predicates WHERE name = ?", (predicate_name,)
            ).fetchone()
            frame_row = connection.execute(
                "SELECT name, description FROM frames WHERE id = ?", (item.source_id,)
            ).fetchone()
            if predicate_row is None or not predicate_row[0]:
                raise LinguisticDonorReviewError(
                    f"donor predicate lacks a description: {predicate_name}"
                )
            if frame_row is None or not frame_row[1]:
                raise LinguisticDonorReviewError(
                    f"donor FrameNet frame lacks a description: {item.source_id}"
                )
            candidates.append(
                DonorMappingRowEvidenceV1(
                    record_id=item.record_id,
                    canonical_id=item.canonical_id,
                    canonical_kind=item.canonical_kind,
                    predicate_name=predicate_name,
                    predicate_description=predicate_row[0],
                    frame_id=item.source_id,
                    frame_name=frame_row[0],
                    frame_description=frame_row[1],
                    merge_kif_tied=predicate_name in merge_predicates,
                )
            )
    finally:
        connection.close()
    ordered = tuple(
        sorted(candidates, key=lambda item: (not item.merge_kif_tied, item.record_id))
    )
    return ordered if limit is None else ordered[:limit]


def _optional_cost(result: object) -> float | None:
    """Return a finite non-negative observed cost without guessing units."""

    cost = getattr(result, "cost", None)
    if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
        return float(cost)
    return None


def run_two_pass_review_row_v1(
    row: DonorMappingRowEvidenceV1,
    *,
    models: tuple[str, str],
    trace_id_prefix: str,
    max_budget_per_call: float,
    prompt_path: Path,
) -> DonorMappingReviewCheckpointV1:
    """Make two real independent llm_client calls for one row and reconcile them.

    The two passes use two different models so neither reviews the mapping's
    own proposer (a separate offline process, `row_mapping_method_ref` on the
    donor predicate row) nor each other.
    """

    if models[0] == models[1]:
        raise LinguisticDonorReviewError("the two review passes must use different models")
    from llm_client import StructuredOutputPolicy, call_llm_structured, render_prompt

    predicate_json = json.dumps(
        {"lemma": row.predicate_name, "description": row.predicate_description},
        sort_keys=True,
    )
    frame_json = json.dumps(
        {"name": row.frame_name, "description": row.frame_description}, sort_keys=True
    )
    messages = render_prompt(prompt_path, predicate_json=predicate_json, frame_json=frame_json)
    passes: list[DonorMappingReviewPassV1] = []
    costs: list[float | None] = []
    for index, model in enumerate(models):
        # No retry/fallback overrides here -- per the plan's `external_call_budget`
        # ("retry_repair_fallback: none invented yet -- use whatever this
        # repo's llm_client default retry/timeout behavior already is"),
        # this deliberately uses llm_client's own default retry policy rather
        # than the SUMO proposal code's zero-retry-authority override (which
        # exists there for bit-exact trace reproducibility, not applicable
        # here). fallback_models stays empty so each pass's model identity is
        # exactly the one requested, preserving the two-different-models
        # independence guarantee; cache stays off so each pass is a fresh call.
        verdict, result = call_llm_structured(
            model,
            messages,
            DonorMappingReviewPassV1,
            fallback_models=[],
            cache=None,
            reasoning_effort="none",
            structured_output_policy=StructuredOutputPolicy(mode="require_native_json_schema"),
            task="judging",
            trace_id=f"{trace_id_prefix}:{row.record_id}:pass{index}",
            max_budget=max_budget_per_call,
            model_justification=(
                "Independent review pass over an existing FrameNet donor-mapping "
                "candidate row for the linguistic_core crosswalk (Plan "
                "0147/Slice B); this call never proposed the mapping."
            ),
            prompt_ref=_PROMPT_REF,
        )
        passes.append(verdict)
        costs.append(_optional_cost(result))
    outcome = reconcile_two_pass_review_v1(passes[0], passes[1])
    return DonorMappingReviewCheckpointV1(
        record_id=row.record_id,
        canonical_id=row.canonical_id,
        canonical_kind=row.canonical_kind,
        model_a=models[0],
        model_b=models[1],
        pass_a=passes[0],
        pass_b=passes[1],
        outcome=outcome,
        cost_usd_a=costs[0],
        cost_usd_b=costs[1],
    )


def load_checkpointed_review_results_v1(
    checkpoint_path: Path,
) -> tuple[DonorMappingReviewCheckpointV1, ...]:
    """Replay every already-completed row from a checkpoint JSONL file."""

    if not checkpoint_path.exists():
        return ()
    results = []
    with checkpoint_path.open(encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                results.append(DonorMappingReviewCheckpointV1.model_validate_json(line))
    return tuple(results)


def append_checkpoint_row_v1(
    checkpoint_path: Path, result: DonorMappingReviewCheckpointV1
) -> None:
    """Persist one row's result immediately, so a mid-batch failure loses nothing."""

    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open("a", encoding="utf-8") as stream:
        stream.write(result.model_dump_json() + "\n")
        stream.flush()


def reviewed_donor_mappings_from_checkpoints_v1(
    results: tuple[DonorMappingReviewCheckpointV1, ...],
) -> tuple[tuple[str, str, str, IndependentReviewOutcome], ...]:
    """Project checkpoint rows into the tuple shape the crosswalk append function takes."""

    return tuple(
        (item.record_id, item.canonical_id, item.canonical_kind, item.outcome)
        for item in results
    )
