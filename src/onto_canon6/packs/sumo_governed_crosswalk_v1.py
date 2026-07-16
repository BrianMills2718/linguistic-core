"""Compile reviewed SUMO decisions without granting verification or pack authority."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from onto_canon6.packs.sumo_crosswalk_review_v1 import (
    EvidenceField,
    SemanticDisposition,
    SumoCrosswalkSemanticReviewCaseV1,
    SumoCrosswalkSemanticReviewQueueV1,
    SumoSemanticProposalRunV1,
)


ReviewDecisionState = Literal["rejected", "unresolved"]
DecisionBasis = Literal[
    "reviewed_non_agentive_evidence",
    "reviewed_insufficient_evidence",
    "source_evidence_unavailable",
]


class SumoGovernedCrosswalkError(ValueError):
    """Raised when reviewed evidence cannot support an exact crosswalk transition."""


class _ReviewContentV1(TypedDict):
    """Typed review fields covered by the normalized content digest."""

    schema_version: Literal["sumo-crosswalk-review-batch-v1"]
    queue_content_sha256: str
    proposal_trace_id: str
    proposal_trace_sha256: str
    proposal_raw_response_sha256: str
    review_document_sha256: str
    proposer_model: str
    reviewer_ref: str
    reviewer_identity_authority: Literal["caller_attested"]
    reviewer_separation: Literal[
        "different_model_from_proposer_same_operator_session"
    ]
    decisions: tuple[SumoCrosswalkReviewDecisionV1, ...]


def _canonical_sha256(value: object) -> str:
    """Hash Pydantic-compatible content using one stable JSON representation."""

    def default(item: object) -> object:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, tuple):
            return list(item)
        raise TypeError(f"cannot encode governed crosswalk content: {type(item).__name__}")

    payload = json.dumps(
        value,
        default=default,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SumoCrosswalkReviewDecisionV1(BaseModel):
    """One reviewer disposition over an exact proposal case and evidence quote."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(pattern=r"^sumo-review:[^:]+:[^:]+$", description="Exact case.")
    state: ReviewDecisionState = Field(
        description="Reviewed rejection or unresolved disposition; never verification."
    )
    evidence_quote: str = Field(
        min_length=1, description="Exact proposal evidence quote reopened by the reviewer."
    )
    rationale: str = Field(
        min_length=1, description="Independent reviewer rationale limited to supplied evidence."
    )


class SumoCrosswalkReviewBatchV1(BaseModel):
    """Typed review decisions bound to one exact queue, trace, and review document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["sumo-crosswalk-review-batch-v1"] = Field(
        default="sumo-crosswalk-review-batch-v1", description="Review batch discriminator."
    )
    queue_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="Exact queue.")
    proposal_trace_id: str = Field(min_length=1, description="Exact successful proposal trace.")
    proposal_trace_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Complete terminal trace file digest."
    )
    proposal_raw_response_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact provider response content digest."
    )
    review_document_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact human-readable decision record."
    )
    proposer_model: str = Field(min_length=1, description="Observed proposal model identity.")
    reviewer_ref: str = Field(min_length=1, description="Configured reviewer identity.")
    reviewer_identity_authority: Literal["caller_attested"] = Field(
        default="caller_attested",
        description="The compiler records but cannot authenticate reviewer identity.",
    )
    reviewer_separation: Literal[
        "different_model_from_proposer_same_operator_session"
    ] = Field(description="Honest independence scope for this bounded review.")
    decisions: tuple[SumoCrosswalkReviewDecisionV1, ...] = Field(
        min_length=1, description="Sorted exact decisions for every model-eligible case."
    )
    review_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Normalized review batch content digest."
    )

    @model_validator(mode="after")
    def _review_batch_reconciles(self) -> "SumoCrosswalkReviewBatchV1":
        ids = [item.case_id for item in self.decisions]
        if ids != sorted(set(ids)):
            raise ValueError("review decisions must be sorted and unique")
        content = self.model_dump(mode="json", exclude={"review_content_sha256"})
        if self.review_content_sha256 != _canonical_sha256(content):
            raise ValueError("review batch content SHA-256 does not reconcile")
        return self


class GovernedSumoCrosswalkRecordV1(BaseModel):
    """One immutable non-promotable transition from the donor candidate state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(pattern=r"^sumo-review:[^:]+:[^:]+$", description="Exact case.")
    donor_predicate_id: str = Field(min_length=1, description="Exact donor predicate.")
    named_label: str = Field(min_length=1, description="Exact donor role label.")
    prior_state: Literal["candidate_unreviewed"] = Field(
        default="candidate_unreviewed", description="Exact audit input state."
    )
    state: Literal["rejected", "unresolved"] = Field(
        description="Governed non-promotable state emitted by this compiler."
    )
    decision_basis: DecisionBasis = Field(description="Evidence basis for the transition.")
    queue_case_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact source-bound queue case digest."
    )
    proposal_disposition: SemanticDisposition | None = Field(
        default=None, description="Fallible proposal when the source case was model-eligible."
    )
    proposal_evidence_field: EvidenceField | None = Field(
        default=None, description="Verified proposal evidence field when eligible."
    )
    evidence_quote: str | None = Field(
        default=None, description="Reviewer-reopened exact proposal quote when eligible."
    )
    review_rationale: str | None = Field(
        default=None, description="Reviewer rationale when semantic review occurred."
    )
    proposal_trace_id: str | None = Field(
        default=None, description="Successful proposal trace when semantic review occurred."
    )
    review_batch_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$", description="Exact review batch when reviewed."
    )
    runtime_eligibility: Literal["ineligible"] = Field(
        default="ineligible", description="Rejected and unresolved rows cannot compile."
    )
    replacement_role: None = Field(
        default=None, description="This review never invents a replacement SUMO role."
    )

    @model_validator(mode="after")
    def _record_reconciles(self) -> "GovernedSumoCrosswalkRecordV1":
        if self.case_id != f"sumo-review:{self.donor_predicate_id}:{self.named_label}":
            raise ValueError("governed record identity does not reconcile")
        semantic_values = (
            self.proposal_disposition,
            self.proposal_evidence_field,
            self.evidence_quote,
            self.review_rationale,
            self.proposal_trace_id,
            self.review_batch_sha256,
        )
        if self.decision_basis == "source_evidence_unavailable":
            if self.state != "unresolved" or any(value is not None for value in semantic_values):
                raise ValueError("source-unavailable record must remain unreviewed unresolved")
        else:
            if any(value is None for value in semantic_values):
                raise ValueError("reviewed record requires complete proposal and review lineage")
            expected_basis = (
                "reviewed_non_agentive_evidence"
                if self.state == "rejected"
                else "reviewed_insufficient_evidence"
            )
            if self.decision_basis != expected_basis:
                raise ValueError("reviewed state and decision basis do not reconcile")
        return self


class GovernedSumoCrosswalkV1(BaseModel):
    """Complete reviewed state for one exact SUMO structural-conflict population."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["governed-sumo-crosswalk-v1"] = Field(
        default="governed-sumo-crosswalk-v1", description="Crosswalk discriminator."
    )
    queue_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="Exact queue.")
    proposal_trace_id: str = Field(description="Exact successful proposal trace.")
    proposal_trace_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact proposal trace file."
    )
    proposal_raw_response_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact provider response."
    )
    review_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact typed review batch."
    )
    records: tuple[GovernedSumoCrosswalkRecordV1, ...] = Field(
        min_length=1, description="Complete sorted governed population."
    )
    rejected_count: int = Field(ge=0, description="Derived rejected-row count.")
    unresolved_count: int = Field(ge=0, description="Derived unresolved-row count.")
    candidate_count: Literal[0] = Field(
        default=0, description="Every row in this bounded population is dispositioned."
    )
    verified_count: Literal[0] = Field(
        default=0, description="This compiler has no verification authority."
    )
    runtime_eligible_count: Literal[0] = Field(
        default=0, description="No emitted row can enter a runtime successor."
    )
    crosswalk_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Normalized governed-record digest."
    )

    @model_validator(mode="after")
    def _crosswalk_reconciles(self) -> "GovernedSumoCrosswalkV1":
        ids = [item.case_id for item in self.records]
        if ids != sorted(set(ids)):
            raise ValueError("governed crosswalk records must be sorted and unique")
        counts = Counter(item.state for item in self.records)
        if self.rejected_count != counts["rejected"]:
            raise ValueError("rejected count does not reconcile")
        if self.unresolved_count != counts["unresolved"]:
            raise ValueError("unresolved count does not reconcile")
        if self.crosswalk_content_sha256 != _canonical_sha256(self.records):
            raise ValueError("governed crosswalk content SHA-256 does not reconcile")
        return self


def _case_evidence(case: SumoCrosswalkSemanticReviewCaseV1) -> dict[EvidenceField, str]:
    """Return only the exact semantic fields addressable by proposal citations."""

    values: dict[EvidenceField, str | None] = {
        "donor_predicate_description": case.donor_predicate_description,
        "propbank_roleset_name": case.propbank.roleset_name,
        "propbank_argument_description": case.propbank.argument_description,
    }
    if any(value is None for value in values.values()):
        raise SumoGovernedCrosswalkError("reviewed case lacks complete exact evidence")
    return {key: value for key, value in values.items() if value is not None}


def build_sumo_crosswalk_review_batch_v1(
    *,
    proposal_trace_path: Path,
    review_document_path: Path,
    reviewer_ref: str,
    decisions: tuple[SumoCrosswalkReviewDecisionV1, ...],
) -> SumoCrosswalkReviewBatchV1:
    """Bind typed reviewer decisions to exact trace, response, and document bytes."""

    trace_payload = proposal_trace_path.read_bytes()
    try:
        trace = SumoSemanticProposalRunV1.model_validate_json(trace_payload)
    except ValueError as exc:
        raise SumoGovernedCrosswalkError("proposal trace is invalid") from exc
    if trace.raw_content is None or trace.execution_model is None:
        raise SumoGovernedCrosswalkError("proposal trace lacks terminal response identity")
    content: _ReviewContentV1 = {
        "schema_version": "sumo-crosswalk-review-batch-v1",
        "queue_content_sha256": trace.queue_content_sha256,
        "proposal_trace_id": trace.trace_id,
        "proposal_trace_sha256": hashlib.sha256(trace_payload).hexdigest(),
        "proposal_raw_response_sha256": hashlib.sha256(
            trace.raw_content.encode("utf-8")
        ).hexdigest(),
        "review_document_sha256": hashlib.sha256(
            review_document_path.read_bytes()
        ).hexdigest(),
        "proposer_model": trace.execution_model,
        "reviewer_ref": reviewer_ref,
        "reviewer_identity_authority": "caller_attested",
        "reviewer_separation": "different_model_from_proposer_same_operator_session",
        "decisions": decisions,
    }
    return SumoCrosswalkReviewBatchV1(
        **content,
        review_content_sha256=_canonical_sha256(content),
    )


def compile_governed_sumo_crosswalk_v1(
    queue: SumoCrosswalkSemanticReviewQueueV1,
    *,
    proposal_trace_path: Path,
    review_document_path: Path,
    review: SumoCrosswalkReviewBatchV1,
) -> GovernedSumoCrosswalkV1:
    """Replay one exact review into rejected/unresolved state without promotion."""

    review = SumoCrosswalkReviewBatchV1.model_validate(review.model_dump(mode="python"))
    trace_payload = proposal_trace_path.read_bytes()
    trace_sha256 = hashlib.sha256(trace_payload).hexdigest()
    try:
        trace = SumoSemanticProposalRunV1.model_validate_json(trace_payload)
    except ValueError as exc:
        raise SumoGovernedCrosswalkError("proposal trace is invalid") from exc
    if trace.lifecycle != "proposal_generated" or not trace.controls_passed:
        raise SumoGovernedCrosswalkError("proposal trace is not a successful controlled run")
    if trace.review_authority != "none_proposals_only":
        raise SumoGovernedCrosswalkError("proposal trace unexpectedly claims review authority")
    if trace.queue_content_sha256 != queue.queue_content_sha256:
        raise SumoGovernedCrosswalkError("proposal trace does not bind the supplied queue")
    if review.queue_content_sha256 != queue.queue_content_sha256:
        raise SumoGovernedCrosswalkError("review does not bind the supplied queue")
    if review.proposal_trace_id != trace.trace_id:
        raise SumoGovernedCrosswalkError("review does not bind the proposal trace identity")
    if review.proposal_trace_sha256 != trace_sha256:
        raise SumoGovernedCrosswalkError("review does not bind the proposal trace bytes")
    raw_content = trace.raw_content
    if raw_content is None:
        raise SumoGovernedCrosswalkError("successful proposal trace lacks raw response")
    raw_sha256 = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
    if review.proposal_raw_response_sha256 != raw_sha256:
        raise SumoGovernedCrosswalkError("review does not bind the raw proposal response")
    if review.proposer_model != trace.execution_model:
        raise SumoGovernedCrosswalkError("review proposer model does not match execution")
    if review.reviewer_ref == review.proposer_model:
        raise SumoGovernedCrosswalkError("proposal model cannot review its own output")
    document_sha256 = hashlib.sha256(review_document_path.read_bytes()).hexdigest()
    if review.review_document_sha256 != document_sha256:
        raise SumoGovernedCrosswalkError("review does not bind the decision document")

    cases = {item.case_id: item for item in queue.cases}
    eligible_ids = {
        item.case_id
        for item in queue.cases
        if item.propbank.resolution_status == "exact_current_source"
    }
    withheld_ids = set(cases) - eligible_ids
    if set(trace.eligible_case_ids) != eligible_ids or set(trace.withheld_case_ids) != withheld_ids:
        raise SumoGovernedCrosswalkError("proposal trace population does not match queue")
    proposals = {item.case_id: item for item in trace.compiled_proposals}
    if set(proposals) != eligible_ids:
        raise SumoGovernedCrosswalkError("compiled proposals do not cover eligible queue")
    decisions = {item.case_id: item for item in review.decisions}
    if set(decisions) != eligible_ids:
        raise SumoGovernedCrosswalkError("review decisions do not cover eligible queue")

    records: list[GovernedSumoCrosswalkRecordV1] = []
    for case_id in sorted(cases):
        case = cases[case_id]
        case_sha256 = _canonical_sha256(case)
        if case_id in withheld_ids:
            records.append(
                GovernedSumoCrosswalkRecordV1(
                    case_id=case.case_id,
                    donor_predicate_id=case.donor_predicate_id,
                    named_label=case.named_label,
                    state="unresolved",
                    decision_basis="source_evidence_unavailable",
                    queue_case_sha256=case_sha256,
                )
            )
            continue
        proposal = proposals[case_id]
        decision = decisions[case_id]
        evidence = _case_evidence(case)[proposal.evidence_field]
        if evidence.count(proposal.evidence_quote) != 1:
            raise SumoGovernedCrosswalkError("proposal quote is not uniquely grounded")
        if evidence[proposal.evidence_start : proposal.evidence_end] != proposal.evidence_quote:
            raise SumoGovernedCrosswalkError("proposal evidence offsets do not reconcile")
        if decision.evidence_quote != proposal.evidence_quote:
            raise SumoGovernedCrosswalkError("review did not reopen the exact proposal quote")
        records.append(
            GovernedSumoCrosswalkRecordV1(
                case_id=case.case_id,
                donor_predicate_id=case.donor_predicate_id,
                named_label=case.named_label,
                state=decision.state,
                decision_basis=(
                    "reviewed_non_agentive_evidence"
                    if decision.state == "rejected"
                    else "reviewed_insufficient_evidence"
                ),
                queue_case_sha256=case_sha256,
                proposal_disposition=proposal.disposition,
                proposal_evidence_field=proposal.evidence_field,
                evidence_quote=decision.evidence_quote,
                review_rationale=decision.rationale,
                proposal_trace_id=trace.trace_id,
                review_batch_sha256=review.review_content_sha256,
            )
        )
    record_values = tuple(records)
    counts = Counter(item.state for item in record_values)
    return GovernedSumoCrosswalkV1(
        queue_content_sha256=queue.queue_content_sha256,
        proposal_trace_id=trace.trace_id,
        proposal_trace_sha256=trace_sha256,
        proposal_raw_response_sha256=raw_sha256,
        review_content_sha256=review.review_content_sha256,
        records=record_values,
        rejected_count=counts["rejected"],
        unresolved_count=counts["unresolved"],
        crosswalk_content_sha256=_canonical_sha256(record_values),
    )


def write_governed_sumo_crosswalk_v1(
    crosswalk: GovernedSumoCrosswalkV1, output_path: Path
) -> None:
    """Persist one immutable governed artifact and refuse replacement."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as stream:
        stream.write(crosswalk.model_dump_json(indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def write_sumo_crosswalk_review_batch_v1(
    review: SumoCrosswalkReviewBatchV1, output_path: Path
) -> None:
    """Persist one immutable typed reviewer batch and refuse replacement."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as stream:
        stream.write(review.model_dump_json(indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
