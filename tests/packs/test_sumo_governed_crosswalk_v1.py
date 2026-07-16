"""Governed SUMO crosswalk transition tests for Plan 0147 Slice 3."""

from __future__ import annotations

import hashlib
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
    verify_sumo_semantic_proposal_trace_v1,
)
from onto_canon6.packs.sumo_governed_crosswalk_v1 import (
    GovernedSumoCrosswalkV1,
    SumoCrosswalkReviewBatchV1,
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
        rendered_messages=(
            {
                "role": "user",
                "content": (
                    "<positive_control>\n"
                    '{"control_id":"positive_autonomous_actor","evidence":"An autonomous actor initiated the event."}'
                    "\n</positive_control>\n"
                    "<negative_control>\n"
                    '{"control_id":"negative_inanimate_cause","evidence":"A storm caused the outage."}'
                    "\n</negative_control>"
                ),
            },
        ),
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
        queue=queue,
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
        queue=queue,
        proposal_trace_path=trace_path,
        review_document_path=review_document,
        reviewer_ref="agent:codex:independent-review",
        decisions=(decision,),
    )

    missing = review.model_copy(update={"decisions": ()})
    with pytest.raises(ValidationError, match="at least 1 item"):
        compile_governed_sumo_crosswalk_v1(
            queue,
            proposal_trace_path=trace_path,
            review_document_path=review_document,
            review=missing,
        )

    extra = decision.model_copy(update={"case_id": "sumo-review:extra:Cause"})
    with pytest.raises(SumoGovernedCrosswalkError, match="do not cover"):
        compile_governed_sumo_crosswalk_v1(
            queue,
            proposal_trace_path=trace_path,
            review_document_path=review_document,
            review=build_sumo_crosswalk_review_batch_v1(
                queue=queue,
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
                queue=queue,
                proposal_trace_path=trace_path,
                review_document_path=review_document,
                reviewer_ref=review.proposer_model,
                decisions=(decision,),
            ),
        )

    substituted_trace = tmp_path / "substituted-trace.json"
    trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
    trace_payload["run_id"] = "substituted-run"
    substituted_trace.write_text(json.dumps(trace_payload), encoding="utf-8")
    with pytest.raises(SumoGovernedCrosswalkError, match="proposal trace bytes"):
        compile_governed_sumo_crosswalk_v1(
            queue,
            proposal_trace_path=substituted_trace,
            review_document_path=review_document,
            review=review,
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
                queue=queue,
                proposal_trace_path=trace_path,
                review_document_path=review_document,
                reviewer_ref="agent:codex:independent-review",
                decisions=(changed_quote,),
            ),
        )

    raw_divergence = json.loads(trace_path.read_text(encoding="utf-8"))
    raw_divergence["batch"]["proposals"][0]["disposition"] = "withhold_insufficient_evidence"
    raw_path = tmp_path / "raw-divergence.json"
    raw_path.write_text(json.dumps(raw_divergence), encoding="utf-8")
    with pytest.raises(SumoGovernedCrosswalkError, match="cannot be replayed"):
        build_sumo_crosswalk_review_batch_v1(
            queue=queue,
            proposal_trace_path=raw_path,
            review_document_path=review_document,
            reviewer_ref="agent:codex:independent-review",
            decisions=(decision,),
        )

    substituted_queue = queue.model_copy(
        update={"donor_db_sha256": "f" * 64}
    )
    with pytest.raises(ValidationError, match="identity SHA-256"):
        SumoCrosswalkSemanticReviewQueueV1.model_validate(
            substituted_queue.model_dump(mode="json")
        )


def test_output_contract_rejects_verification_count_and_runtime_injection(
    tmp_path: Path,
) -> None:
    trace_path, review_document, queue, decision = _review_inputs(tmp_path)
    review = build_sumo_crosswalk_review_batch_v1(
        queue=queue,
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


def test_committed_review_and_crosswalk_are_exact_non_promotable_artifacts() -> None:
    """Keep the bounded observed result schema-valid and authority-denying."""

    repository = Path(__file__).parents[2]
    trace_path = (
        repository
        / "docs/runs/artifacts/plan0147_sumo_semantic_proposal_v3_trace.json"
    )
    trace_payload = trace_path.read_bytes()
    trace = SumoSemanticProposalRunV1.model_validate_json(trace_payload)
    queue = SumoCrosswalkSemanticReviewQueueV1.model_validate_json(
        (
            repository
            / "docs/runs/artifacts/plan0147_sumo_semantic_review_queue_v1.json"
        ).read_bytes()
    )
    review = SumoCrosswalkReviewBatchV1.model_validate_json(
        (
            repository
            / "docs/runs/2026-07-15_plan0147_sumo_semantic_review.json"
        ).read_bytes()
    )
    crosswalk = GovernedSumoCrosswalkV1.model_validate_json(
        (
            repository
            / "docs/runs/2026-07-15_plan0147_sumo_governed_crosswalk.json"
        ).read_bytes()
    )

    assert len(review.decisions) == 31
    assert review.reviewer_identity_authority == "caller_attested"
    assert len(crosswalk.records) == 34
    assert (crosswalk.rejected_count, crosswalk.unresolved_count) == (8, 26)
    assert (
        crosswalk.candidate_count,
        crosswalk.verified_count,
        crosswalk.runtime_eligible_count,
    ) == (0, 0, 0)
    assert crosswalk.queue_content_sha256 == review.queue_content_sha256
    assert trace.queue_content_sha256 == review.queue_content_sha256
    assert review.queue_identity_sha256 == queue.queue_identity_sha256
    assert crosswalk.queue_identity_sha256 == queue.queue_identity_sha256
    assert trace.trace_id == review.proposal_trace_id
    assert hashlib.sha256(trace_payload).hexdigest() == review.proposal_trace_sha256
    assert trace.lifecycle == "proposal_generated"
    assert trace.controls_passed is True
    assert trace.review_authority == "none_proposals_only"
    assert trace.raw_content is not None
    assert (
        hashlib.sha256(trace.raw_content.encode("utf-8")).hexdigest()
        == review.proposal_raw_response_sha256
    )
    assert crosswalk.proposal_trace_id == review.proposal_trace_id
    assert crosswalk.proposal_trace_sha256 == review.proposal_trace_sha256
    assert (
        crosswalk.proposal_raw_response_sha256
        == review.proposal_raw_response_sha256
    )
    assert crosswalk.review_content_sha256 == review.review_content_sha256
    assert {
        item.case_id for item in crosswalk.records if item.state == "rejected"
    } == {
        "sumo-review:affect_have_effect:Cause",
        "sumo-review:concern_deal_with:Phenomenon",
        "sumo-review:galvanize_cause_response:Cause",
        "sumo-review:hamper_obstruct_hinder:Hindrance",
        "sumo-review:lead_result_outcome:Cause",
        "sumo-review:obstruct_to_block:Hindrance",
        "sumo-review:pertain_have_reference:Phenomenon",
        "sumo-review:redound_have_consequence:Cause",
    }
    assert {
        item.case_id
        for item in crosswalk.records
        if item.decision_basis == "source_evidence_unavailable"
    } == {
        "sumo-review:damp_restrain_weaken:Hindrance",
        "sumo-review:effect_cause_effect:Cause",
        "sumo-review:usher_signal_start:Cause",
    }
    assert all(item.runtime_eligibility == "ineligible" for item in crosswalk.records)
    assert all(item.replacement_role is None for item in crosswalk.records)
    verify_sumo_semantic_proposal_trace_v1(queue, trace)
