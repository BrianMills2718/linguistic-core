"""Governed SUMO crosswalk transition tests for Plan 0147 Slice 3."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from onto_canon6.packs.sumo_crosswalk_review_v1 import (
    CompiledSumoSemanticProposalV1,
    SumoCrosswalkSemanticReviewQueueV1,
    SumoSemanticControlResultV1,
    SumoSemanticDispositionProposalV1,
    SumoSemanticProposalBatchV1,
    SumoSemanticProposalRunV1,
    build_sumo_crosswalk_semantic_review_queue_v1,
)
from onto_canon6.packs.sumo_governed_crosswalk_v1 import (
    GovernedSumoCrosswalkV1,
    SumoCrosswalkReviewDecisionV1,
    SumoGovernedCrosswalkError,
    build_sumo_crosswalk_review_batch_v1,
    compile_governed_sumo_crosswalk_v1,
    write_governed_sumo_crosswalk_v1,
    write_sumo_crosswalk_review_batch_v1,
)
from tests.packs.test_sumo_crosswalk_review_v1 import _inputs


def _review_inputs(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    SumoCrosswalkSemanticReviewQueueV1,
    SumoCrosswalkReviewDecisionV1,
]:
    """Build one exact queue, successful proposal trace, and review decision."""

    report, database, source = _inputs(tmp_path)
    queue = build_sumo_crosswalk_semantic_review_queue_v1(
        report, donor_database=database, propbank_source=source
    )
    case = queue.cases[0]
    proposal = SumoSemanticDispositionProposalV1(
        donor_predicate_id=case.donor_predicate_id,
        named_label=case.named_label,
        disposition="reject_role_mapping",
        evidence_field="propbank_argument_description",
        evidence_quote="thing affecting",
        rationale="The broad wording permits a non-autonomous cause.",
        ambiguity_note="No explicit autonomy.",
    )
    batch = SumoSemanticProposalBatchV1(
        proposals=(proposal,),
        control_results=(
            SumoSemanticControlResultV1(
                control_id="positive_autonomous_actor",
                disposition="retain_role_narrow_type",
                evidence_quote="autonomous actor",
            ),
            SumoSemanticControlResultV1(
                control_id="negative_inanimate_cause",
                disposition="reject_role_mapping",
                evidence_quote="storm",
            ),
        ),
    )
    trace = SumoSemanticProposalRunV1(
        lifecycle="proposal_generated",
        run_id="test-run",
        trace_id="test-trace",
        queue_content_sha256=queue.queue_content_sha256,
        prompt_sha256="1" * 64,
        response_schema_sha256="2" * 64,
        llm_client_commit="3" * 40,
        requested_model="openrouter/minimax/minimax-m3",
        resolved_model="openrouter/minimax/minimax-m3",
        execution_model="openrouter/minimax/minimax-m3",
        cache_hit=False,
        cost_usd=0.01,
        eligible_case_ids=(case.case_id,),
        withheld_case_ids=(),
        rendered_messages=({"role": "user", "content": "fixture evidence"},),
        raw_content=batch.model_dump_json(),
        batch=batch,
        compiled_proposals=(
            CompiledSumoSemanticProposalV1(
                case_id=case.case_id,
                disposition=proposal.disposition,
                evidence_field=proposal.evidence_field,
                evidence_quote=proposal.evidence_quote,
                evidence_start=0,
                evidence_end=len(proposal.evidence_quote),
                rationale=proposal.rationale,
                ambiguity_note=proposal.ambiguity_note,
            ),
        ),
        controls_passed=True,
        error_type=None,
        error_message=None,
    )
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(trace.model_dump_json(indent=2) + "\n", encoding="utf-8")
    review_document = tmp_path / "review.md"
    review_document.write_text("# Exact reviewer decision\n", encoding="utf-8")
    decision = SumoCrosswalkReviewDecisionV1(
        case_id=case.case_id,
        state="rejected",
        evidence_quote=proposal.evidence_quote,
        rationale="The exact word 'thing' permits a non-autonomous cause.",
    )
    return trace_path, review_document, queue, decision


def test_compiler_emits_only_rejected_or_unresolved_ineligible_state(
    tmp_path: Path,
) -> None:
    trace_path, review_document, queue, decision = _review_inputs(tmp_path)
    review = build_sumo_crosswalk_review_batch_v1(
        proposal_trace_path=trace_path,
        review_document_path=review_document,
        reviewer_ref="agent:codex:independent-review",
        decisions=(decision,),
    )

    first = compile_governed_sumo_crosswalk_v1(
        queue,
        proposal_trace_path=trace_path,
        review_document_path=review_document,
        review=review,
    )
    second = compile_governed_sumo_crosswalk_v1(
        queue,
        proposal_trace_path=trace_path,
        review_document_path=review_document,
        review=review,
    )

    assert first == second
    assert first.rejected_count == 1
    assert first.unresolved_count == 0
    assert first.candidate_count == 0
    assert first.verified_count == 0
    assert first.runtime_eligible_count == 0
    assert first.records[0].state == "rejected"
    assert first.records[0].runtime_eligibility == "ineligible"
    assert first.records[0].replacement_role is None

    output = tmp_path / "governed.json"
    write_governed_sumo_crosswalk_v1(first, output)
    assert GovernedSumoCrosswalkV1.model_validate_json(output.read_bytes()) == first
    with pytest.raises(FileExistsError):
        write_governed_sumo_crosswalk_v1(first, output)

    review_output = tmp_path / "review.json"
    write_sumo_crosswalk_review_batch_v1(review, review_output)
    with pytest.raises(FileExistsError):
        write_sumo_crosswalk_review_batch_v1(review, review_output)


def test_compiler_rejects_population_trace_authority_and_evidence_corruption(
    tmp_path: Path,
) -> None:
    trace_path, review_document, queue, decision = _review_inputs(tmp_path)
    review = build_sumo_crosswalk_review_batch_v1(
        proposal_trace_path=trace_path,
        review_document_path=review_document,
        reviewer_ref="agent:codex:independent-review",
        decisions=(decision,),
    )

    extra = decision.model_copy(update={"case_id": "sumo-review:extra:Cause"})
    with pytest.raises(SumoGovernedCrosswalkError, match="do not cover"):
        compile_governed_sumo_crosswalk_v1(
            queue,
            proposal_trace_path=trace_path,
            review_document_path=review_document,
            review=build_sumo_crosswalk_review_batch_v1(
                proposal_trace_path=trace_path,
                review_document_path=review_document,
                reviewer_ref="agent:codex:independent-review",
                decisions=(extra, decision),
            ),
        )

    with pytest.raises(SumoGovernedCrosswalkError, match="cannot review its own"):
        compile_governed_sumo_crosswalk_v1(
            queue,
            proposal_trace_path=trace_path,
            review_document_path=review_document,
            review=build_sumo_crosswalk_review_batch_v1(
                proposal_trace_path=trace_path,
                review_document_path=review_document,
                reviewer_ref=review.proposer_model,
                decisions=(decision,),
            ),
        )

    changed_document = tmp_path / "changed-review.md"
    changed_document.write_text("# Substituted reviewer decision\n", encoding="utf-8")
    with pytest.raises(SumoGovernedCrosswalkError, match="decision document"):
        compile_governed_sumo_crosswalk_v1(
            queue,
            proposal_trace_path=trace_path,
            review_document_path=changed_document,
            review=review,
        )

    changed_quote = decision.model_copy(update={"evidence_quote": "affecting"})
    with pytest.raises(SumoGovernedCrosswalkError, match="exact proposal quote"):
        compile_governed_sumo_crosswalk_v1(
            queue,
            proposal_trace_path=trace_path,
            review_document_path=review_document,
            review=build_sumo_crosswalk_review_batch_v1(
                proposal_trace_path=trace_path,
                review_document_path=review_document,
                reviewer_ref="agent:codex:independent-review",
                decisions=(changed_quote,),
            ),
        )


def test_output_contract_rejects_verification_count_and_runtime_injection(
    tmp_path: Path,
) -> None:
    trace_path, review_document, queue, decision = _review_inputs(tmp_path)
    review = build_sumo_crosswalk_review_batch_v1(
        proposal_trace_path=trace_path,
        review_document_path=review_document,
        reviewer_ref="agent:codex:independent-review",
        decisions=(decision,),
    )
    crosswalk = compile_governed_sumo_crosswalk_v1(
        queue,
        proposal_trace_path=trace_path,
        review_document_path=review_document,
        review=review,
    )
    payload = crosswalk.model_dump(mode="json")

    with pytest.raises(ValidationError):
        GovernedSumoCrosswalkV1.model_validate({**payload, "verified_count": 1})
    with pytest.raises(ValidationError):
        GovernedSumoCrosswalkV1.model_validate(
            {**payload, "runtime_eligible_count": 1}
        )
    injected = json.loads(json.dumps(payload))
    injected["records"][0]["runtime_eligibility"] = "eligible"
    with pytest.raises(ValidationError):
        GovernedSumoCrosswalkV1.model_validate(injected)
