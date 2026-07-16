"""Build source-bound semantic-review cases without deciding or accepting them."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
from typing import Literal, TypedDict
import xml.etree.ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field, model_validator

from onto_canon6.packs.linguistic_source_audit_v1 import (
    normalize_propbank_donor_id_v1,
)
from onto_canon6.packs.sumo_crosswalk_audit_v1 import (
    SumoCrosswalkAuditV1,
    SumoRoleCandidateV1,
)
from onto_canon6.packs.sumo_projection_v1 import SumoFormulaRefV1


ResolutionStatus = Literal[
    "exact_current_source", "source_window_not_supplied", "conflicting_supplied_source"
]


class SumoCrosswalkReviewError(ValueError):
    """Raised when a review queue cannot be built from exact evidence."""


class PropBankReviewSourceFileV1(BaseModel):
    """One local byte source bound to its path and Git blob at the pinned commit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_relative_path: str = Field(
        pattern=r"^frames/[^/]+\.xml$", description="Exact upstream repository path."
    )
    local_path: Path = Field(description="Local file whose bytes must match the Git blob.")
    git_blob_sha: str = Field(
        pattern=r"^[0-9a-f]{40}$", description="Expected Git blob SHA-1 at the pinned commit."
    )


class PropBankReviewSourceV1(BaseModel):
    """Pinned PropBank identity plus only the files needed for this review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$", description="Pinned commit.")
    source_tree_sha: str = Field(pattern=r"^[0-9a-f]{40}$", description="Pinned tree.")
    selected_payload_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Complete selected-source payload digest."
    )
    files: tuple[PropBankReviewSourceFileV1, ...] = Field(
        min_length=1, description="Distinct exact files supplied to the bounded review."
    )

    @model_validator(mode="after")
    def _files_are_unique(self) -> "PropBankReviewSourceV1":
        paths = [item.source_relative_path for item in self.files]
        if paths != sorted(set(paths)):
            raise ValueError("PropBank review source files must be sorted and unique")
        return self


class PropBankArgumentEvidenceV1(BaseModel):
    """Exact current-source disposition for one donor PropBank numbered argument."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    donor_sense_id: str = Field(min_length=1, description="Exact donor sense identifier.")
    normalized_source_id: str = Field(
        min_length=1, description="Mechanical current-source identifier normalization."
    )
    argument_number: str = Field(min_length=1, description="Normalized numbered argument.")
    resolution_status: ResolutionStatus = Field(description="Exact source-resolution result.")
    roleset_name: str | None = Field(
        default=None, description="Exact roleset name only for unique resolution."
    )
    argument_description: str | None = Field(
        default=None, description="Exact argument description only for unique resolution."
    )
    source_relative_path: str | None = Field(
        default=None, description="Exact upstream file only for unique resolution."
    )
    source_file_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Complete exact source-file digest only for unique resolution.",
    )
    source_git_blob_sha: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{40}$",
        description=(
            "Caller-supplied Git blob matching the local bytes; commit-tree membership "
            "requires independent verification."
        ),
    )

    @model_validator(mode="after")
    def _resolution_is_consistent(self) -> "PropBankArgumentEvidenceV1":
        evidence = (
            self.roleset_name,
            self.source_relative_path,
            self.source_file_sha256,
            self.source_git_blob_sha,
        )
        if self.resolution_status == "exact_current_source":
            if any(value is None for value in evidence):
                raise ValueError("exact PropBank resolution requires complete source evidence")
        elif any(value is not None for value in evidence) or self.argument_description is not None:
            raise ValueError("non-exact PropBank resolution cannot carry selected source evidence")
        return self


class SumoCrosswalkSemanticReviewCaseV1(BaseModel):
    """One unresolved semantic judgment with exact donor and source evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(pattern=r"^sumo-review:[^:]+:[^:]+$", description="Stable case key.")
    donor_predicate_id: str = Field(min_length=1, description="Exact donor predicate key.")
    donor_predicate_description: str = Field(
        min_length=1, description="Exact donor predicate description."
    )
    named_label: str = Field(min_length=1, description="Exact donor role label.")
    arg_position: str = Field(min_length=1, description="Exact donor argument position.")
    abstract_role: Literal["agent"] = Field(description="Observed disputed SUMO role candidate.")
    donor_type_constraint: Literal["Entity"] = Field(
        description="Observed donor type that is broader than the source domain."
    )
    source_constraint_types: tuple[Literal["AutonomousAgent"], ...] = Field(
        min_length=1, description="Exact SUMO source domain types."
    )
    role_source_refs: tuple[SumoFormulaRefV1, ...] = Field(
        min_length=1, description="Exact SUMO role identity evidence."
    )
    constraint_source_refs: tuple[SumoFormulaRefV1, ...] = Field(
        min_length=1, description="Exact SUMO domain evidence."
    )
    propbank: PropBankArgumentEvidenceV1 = Field(
        description="Exact current PropBank argument evidence or explicit non-resolution."
    )
    proposal_state: Literal["awaiting_semantic_proposal"] = Field(
        default="awaiting_semantic_proposal",
        description="This queue contains no semantic disposition or acceptance.",
    )

    @model_validator(mode="after")
    def _case_key_reconciles(self) -> "SumoCrosswalkSemanticReviewCaseV1":
        if self.case_id != f"sumo-review:{self.donor_predicate_id}:{self.named_label}":
            raise ValueError("semantic review case ID does not reconcile")
        return self


class SumoCrosswalkSemanticReviewQueueV1(BaseModel):
    """Complete proposal-only queue for one structural failure-class population."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["sumo-crosswalk-semantic-review-queue-v1"] = Field(
        default="sumo-crosswalk-semantic-review-queue-v1",
        description="Queue contract discriminator.",
    )
    crosswalk_report_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact upstream audit content digest."
    )
    donor_db_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="Exact donor DB.")
    propbank_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$", description="Pinned commit.")
    propbank_tree_sha: str = Field(pattern=r"^[0-9a-f]{40}$", description="Pinned tree.")
    propbank_payload_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Pinned complete payload."
    )
    population_status: Literal["incompatible_donor_supertype"] = Field(
        default="incompatible_donor_supertype",
        description="Sole structural status selected into this queue.",
    )
    review_authority: Literal["none_proposal_queue_only"] = Field(
        default="none_proposal_queue_only",
        description="Explicit denial of judgment, acceptance, or promotion authority.",
    )
    source_tree_membership_authority: Literal[
        "caller_supplied_requires_independent_verification"
    ] = Field(
        default="caller_supplied_requires_independent_verification",
        description=(
            "The builder verifies blob-to-byte identity but cannot certify that a caller's "
            "blob list belongs to the declared upstream commit tree."
        ),
    )
    cases: tuple[SumoCrosswalkSemanticReviewCaseV1, ...] = Field(
        description="Every selected case, sorted by stable identity."
    )
    queue_content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Normalized case-content digest."
    )

    @model_validator(mode="after")
    def _queue_reconciles(self) -> "SumoCrosswalkSemanticReviewQueueV1":
        keys = [item.case_id for item in self.cases]
        if keys != sorted(set(keys)):
            raise ValueError("semantic review cases must be sorted and unique")
        if self.queue_content_sha256 != _normalized_sha256(self.cases):
            raise ValueError("semantic review queue content SHA-256 does not reconcile")
        return self


def _normalized_sha256(value: object) -> str:
    """Hash Pydantic-compatible content with canonical JSON framing."""

    def default(item: object) -> object:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, tuple):
            return list(item)
        raise TypeError(f"cannot encode semantic review content: {type(item).__name__}")

    payload = json.dumps(
        value,
        default=default,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git_blob_sha(payload: bytes) -> str:
    """Compute Git's canonical SHA-1 object identity for complete file bytes."""

    framed = f"blob {len(payload)}\0".encode("ascii") + payload
    return hashlib.sha1(framed, usedforsecurity=False).hexdigest()


def _arg_number(role: SumoRoleCandidateV1) -> str:
    """Normalize a numbered donor ARG position without guessing adjunct roles."""

    if not role.arg_position.startswith("ARG"):
        raise SumoCrosswalkReviewError("review population contains a non-ARG role")
    number = role.arg_position.removeprefix("ARG")
    if not number.isdigit():
        raise SumoCrosswalkReviewError("review population contains a non-numbered ARG role")
    return str(int(number))


def _database_sha256(path: Path) -> str:
    """Hash the complete donor database as the review input identity."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_sumo_crosswalk_semantic_review_queue_v1(
    report: SumoCrosswalkAuditV1,
    *,
    donor_database: Path,
    propbank_source: PropBankReviewSourceV1,
) -> SumoCrosswalkSemanticReviewQueueV1:
    """Build the complete structural-conflict queue without semantic judgment."""

    database = donor_database.resolve()
    if _database_sha256(database) != report.donor_db_sha256:
        raise SumoCrosswalkReviewError("donor database does not match crosswalk report")
    descriptions: dict[str, str] = {}
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro&immutable=1", uri=True)
    try:
        for predicate_id, description in connection.execute(
            "SELECT name, description FROM predicates ORDER BY name"
        ):
            if not isinstance(description, str) or not description:
                raise SumoCrosswalkReviewError("donor predicate description is missing")
            descriptions[str(predicate_id)] = description
    finally:
        connection.close()

    rolesets: dict[str, list[tuple[str, str, str | None, str, str]]] = {}
    for source_file in propbank_source.files:
        payload = source_file.local_path.read_bytes()
        if _git_blob_sha(payload) != source_file.git_blob_sha:
            raise SumoCrosswalkReviewError(
                f"PropBank Git blob mismatch: {source_file.source_relative_path}"
            )
        try:
            root = ET.fromstring(payload.decode("utf-8"))
        except (UnicodeDecodeError, ET.ParseError) as exc:
            raise SumoCrosswalkReviewError(
                f"invalid PropBank XML: {source_file.source_relative_path}"
            ) from exc
        file_sha256 = hashlib.sha256(payload).hexdigest()
        for roleset in root.findall(".//roleset"):
            roleset_id = roleset.get("id")
            if not roleset_id:
                raise SumoCrosswalkReviewError("PropBank roleset lacks identity")
            for role_element in roleset.findall("./roles/role"):
                number = role_element.get("n")
                if number is None:
                    raise SumoCrosswalkReviewError("PropBank role lacks argument number")
                rolesets.setdefault(roleset_id, []).append(
                    (
                        number,
                        roleset.get("name") or "",
                        role_element.get("descr"),
                        source_file.source_relative_path,
                        file_sha256,
                    )
                )

    predicates = {item.donor_predicate_id: item for item in report.predicates}
    selected = [
        role for role in report.roles if role.constraint_status == report_status()
    ]
    cases: list[SumoCrosswalkSemanticReviewCaseV1] = []
    for candidate in selected:
        predicate = predicates[candidate.donor_predicate_id]
        if (
            candidate.abstract_role != "agent"
            or candidate.type_constraint != "Entity"
            or candidate.observed_constraint_types != ("AutonomousAgent",)
        ):
            raise SumoCrosswalkReviewError(
                "review population contains a second unregistered failure class"
            )
        donor_sense = predicate.propbank_sense_id
        normalized = normalize_propbank_donor_id_v1(donor_sense or "")
        if donor_sense is None or normalized is None:
            raise SumoCrosswalkReviewError("review case has invalid donor PropBank identity")
        number = _arg_number(candidate)
        matching_roles = [item for item in rolesets.get(normalized, ()) if item[0] == number]
        if len(matching_roles) == 1:
            _, name, description, relative_path, file_sha256 = matching_roles[0]
            blob_sha = next(
                item.git_blob_sha
                for item in propbank_source.files
                if item.source_relative_path == relative_path
            )
            propbank = PropBankArgumentEvidenceV1(
                donor_sense_id=donor_sense,
                normalized_source_id=normalized,
                argument_number=number,
                resolution_status="exact_current_source",
                roleset_name=name,
                argument_description=description,
                source_relative_path=relative_path,
                source_file_sha256=file_sha256,
                source_git_blob_sha=blob_sha,
            )
        else:
            propbank = PropBankArgumentEvidenceV1(
                donor_sense_id=donor_sense,
                normalized_source_id=normalized,
                argument_number=number,
                resolution_status=(
                    "source_window_not_supplied"
                    if not matching_roles
                    else "conflicting_supplied_source"
                ),
            )
        cases.append(
            SumoCrosswalkSemanticReviewCaseV1(
                case_id=(
                    f"sumo-review:{candidate.donor_predicate_id}:{candidate.named_label}"
                ),
                donor_predicate_id=candidate.donor_predicate_id,
                donor_predicate_description=descriptions[candidate.donor_predicate_id],
                named_label=candidate.named_label,
                arg_position=candidate.arg_position,
                abstract_role="agent",
                donor_type_constraint="Entity",
                source_constraint_types=("AutonomousAgent",),
                role_source_refs=candidate.role_source_refs,
                constraint_source_refs=candidate.constraint_source_refs,
                propbank=propbank,
            )
        )
    case_values = tuple(sorted(cases, key=lambda item: item.case_id))
    return SumoCrosswalkSemanticReviewQueueV1(
        crosswalk_report_content_sha256=report.report_content_sha256,
        donor_db_sha256=report.donor_db_sha256,
        propbank_commit_sha=propbank_source.source_commit_sha,
        propbank_tree_sha=propbank_source.source_tree_sha,
        propbank_payload_sha256=propbank_source.selected_payload_sha256,
        cases=case_values,
        queue_content_sha256=_normalized_sha256(case_values),
    )


def report_status() -> Literal["incompatible_donor_supertype"]:
    """Name the sole preregistered structural population selected for review."""

    return "incompatible_donor_supertype"


SemanticDisposition = Literal[
    "retain_role_narrow_type",
    "reject_role_mapping",
    "withhold_insufficient_evidence",
]
EvidenceField = Literal[
    "donor_predicate_description",
    "propbank_roleset_name",
    "propbank_argument_description",
]
_PROMPT_REF = "onto_canon6_plan0147_sumo_crosswalk_semantic_review@1.0"


class SumoSemanticDispositionProposalV1(BaseModel):
    """One fallible, evidence-citing semantic disposition proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    donor_predicate_id: str = Field(
        min_length=1, description="Copy the exact supplied donor predicate identifier."
    )
    named_label: str = Field(
        min_length=1, description="Copy the exact supplied donor role label."
    )
    disposition: SemanticDisposition = Field(
        description="Proposal category under the supplied agent-role rubric."
    )
    evidence_field: EvidenceField = Field(
        description="Supplied evidence field containing the exact supporting quote."
    )
    evidence_quote: str = Field(
        min_length=1, description="Exact verbatim substring from the named evidence field."
    )
    rationale: str = Field(
        min_length=1,
        description="Concise explanation limited to the cited linguistic evidence.",
    )
    ambiguity_note: str = Field(
        min_length=1,
        description="What remains uncertain, or 'none' when the evidence is decisive.",
    )


class SumoSemanticControlResultV1(BaseModel):
    """One preregistered detector control disposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    control_id: Literal["positive_autonomous_actor", "negative_inanimate_cause"] = Field(
        description="Exact supplied control identity."
    )
    disposition: SemanticDisposition = Field(description="Control disposition.")
    evidence_quote: str = Field(
        min_length=1, description="Exact substring from the supplied control evidence."
    )


class SumoSemanticProposalBatchV1(BaseModel):
    """Native-schema response containing all real proposals and both controls."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposals: tuple[SumoSemanticDispositionProposalV1, ...] = Field(
        min_length=1, description="Exactly one proposal for every supplied real case."
    )
    control_results: tuple[SumoSemanticControlResultV1, ...] = Field(
        min_length=2,
        max_length=2,
        description="Exactly the positive and negative control results.",
    )

    @model_validator(mode="after")
    def _identities_are_unique(self) -> "SumoSemanticProposalBatchV1":
        proposal_keys = [
            (item.donor_predicate_id, item.named_label) for item in self.proposals
        ]
        if len(proposal_keys) != len(set(proposal_keys)):
            raise ValueError("semantic proposal identities must be unique")
        control_ids = [item.control_id for item in self.control_results]
        if set(control_ids) != {"positive_autonomous_actor", "negative_inanimate_cause"}:
            raise ValueError("both preregistered semantic controls are required")
        return self


class CompiledSumoSemanticProposalV1(BaseModel):
    """Proposal with system-verified evidence location, still without review authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1, description="System-assigned review case identity.")
    disposition: SemanticDisposition = Field(description="Fallible model proposal.")
    evidence_field: EvidenceField = Field(description="Verified supplied evidence field.")
    evidence_quote: str = Field(description="Verified exact evidence substring.")
    evidence_start: int = Field(ge=0, description="System-computed substring start offset.")
    evidence_end: int = Field(gt=0, description="System-computed exclusive end offset.")
    rationale: str = Field(description="Fallible model rationale.")
    ambiguity_note: str = Field(description="Fallible model ambiguity note.")
    review_state: Literal["proposal_unreviewed"] = Field(
        default="proposal_unreviewed", description="No acceptance or promotion authority."
    )

    @model_validator(mode="after")
    def _offset_is_consistent(self) -> "CompiledSumoSemanticProposalV1":
        if self.evidence_end != self.evidence_start + len(self.evidence_quote):
            raise ValueError("semantic proposal evidence offsets do not reconcile")
        return self


class SumoSemanticProposalRunConfigV1(BaseModel):
    """Explicit one-attempt MiniMax proposal-run configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1, description="Unique local run identity.")
    trace_id: str = Field(min_length=1, description="Unique llm_client trace identity.")
    model: Literal["openrouter/minimax/minimax-m3"] = Field(
        description="Exact requested OpenRouter MiniMax-M3 model."
    )
    max_budget: float = Field(
        gt=0, description="Technical llm_client ceiling, not a semantic decision gate."
    )
    llm_client_commit: str = Field(
        pattern=r"^[0-9a-f]{40}$", description="Exact clean llm_client execution revision."
    )


class SumoSemanticProposalRunV1(BaseModel):
    """Terminal exact-call trace for one proposal-only semantic run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["sumo-semantic-proposal-run-v1"] = Field(
        default="sumo-semantic-proposal-run-v1", description="Trace discriminator."
    )
    lifecycle: Literal[
        "proposal_generated",
        "proposal_generated_controls_failed",
        "provider_or_schema_failed",
        "evidence_validation_failed",
    ] = Field(
        description="Terminal execution disposition."
    )
    run_id: str = Field(description="Bound local run identity.")
    trace_id: str = Field(description="Bound llm_client trace identity.")
    queue_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="Exact queue.")
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="Exact prompt bytes.")
    response_schema_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="Exact native response schema."
    )
    llm_client_commit: str = Field(pattern=r"^[0-9a-f]{40}$", description="Executed client.")
    requested_model: str = Field(description="Requested model identity.")
    resolved_model: str | None = Field(description="Observed resolved model when available.")
    execution_model: str | None = Field(description="Observed execution model when available.")
    cache_hit: bool | None = Field(description="Observed cache state when available.")
    cost_usd: float | None = Field(ge=0, description="Observed call cost when available.")
    eligible_case_ids: tuple[str, ...] = Field(description="Cases sent to the model.")
    withheld_case_ids: tuple[str, ...] = Field(description="Cases withheld before dispatch.")
    rendered_messages: tuple[dict[str, str], ...] = Field(
        description="Exact messages passed to llm_client."
    )
    raw_content: str | None = Field(description="Exact exposed provider response content.")
    batch: SumoSemanticProposalBatchV1 | None = Field(
        description="Schema-valid fallible output on success."
    )
    compiled_proposals: tuple[CompiledSumoSemanticProposalV1, ...] = Field(
        description="Evidence-checked proposals on success."
    )
    controls_passed: bool = Field(description="Whether both preregistered controls passed.")
    error_type: str | None = Field(description="Terminal failure class when applicable.")
    error_message: str | None = Field(description="Bounded redacted failure detail.")
    retry_count_allowed: Literal[0] = Field(default=0, description="No retry authority.")
    fallback_models: tuple[()] = Field(default=(), description="No model fallback chain.")
    cache_enabled: Literal[False] = Field(default=False, description="No application cache.")
    native_json_schema_required: Literal[True] = Field(
        default=True, description="No Instructor or permissive JSON path."
    )
    review_authority: Literal["none_proposals_only"] = Field(
        default="none_proposals_only", description="No acceptance or promotion authority."
    )

    @model_validator(mode="after")
    def _terminal_state_is_consistent(self) -> "SumoSemanticProposalRunV1":
        if self.lifecycle == "provider_or_schema_failed":
            if self.batch is not None or self.compiled_proposals or self.controls_passed:
                raise ValueError("provider failure cannot carry successful proposal output")
        elif self.lifecycle == "evidence_validation_failed":
            if self.batch is None or self.compiled_proposals or self.controls_passed:
                raise ValueError("evidence failure must preserve only the schema-valid batch")
        else:
            if self.batch is None or not self.compiled_proposals:
                raise ValueError("generated proposal lifecycle requires compiled proposals")
            if len(self.compiled_proposals) != len(self.batch.proposals):
                raise ValueError("compiled proposal count must match the response batch")
            if self.lifecycle == "proposal_generated" and not self.controls_passed:
                raise ValueError("successful proposal lifecycle requires passing controls")
            if self.lifecycle == "proposal_generated_controls_failed" and self.controls_passed:
                raise ValueError("control-failure lifecycle requires failed controls")
        if (self.error_type is None) != (self.error_message is None):
            raise ValueError("terminal error type and message must appear together")
        has_error = self.error_type is not None
        if self.lifecycle == "proposal_generated" and has_error:
            raise ValueError("successful proposal lifecycle cannot carry an error")
        if self.lifecycle != "proposal_generated" and not has_error:
            raise ValueError("non-success lifecycle requires a terminal error")
        return self


class _RunCommonV1(TypedDict):
    """Typed constructor fields shared by successful and failed run traces."""

    run_id: str
    trace_id: str
    queue_content_sha256: str
    prompt_sha256: str
    response_schema_sha256: str
    llm_client_commit: str
    requested_model: str
    eligible_case_ids: tuple[str, ...]
    withheld_case_ids: tuple[str, ...]
    rendered_messages: tuple[dict[str, str], ...]


def _proposal_evidence(case: SumoCrosswalkSemanticReviewCaseV1) -> dict[EvidenceField, str]:
    """Expose only exact semantic evidence fields addressable by model citations."""

    if case.propbank.resolution_status != "exact_current_source":
        raise SumoCrosswalkReviewError("semantic proposal case lacks exact PropBank evidence")
    values: dict[EvidenceField, str | None] = {
        "donor_predicate_description": case.donor_predicate_description,
        "propbank_roleset_name": case.propbank.roleset_name,
        "propbank_argument_description": case.propbank.argument_description,
    }
    if any(value is None for value in values.values()):
        raise SumoCrosswalkReviewError("semantic proposal case has incomplete evidence text")
    return {key: value for key, value in values.items() if value is not None}


def _redact_openrouter_error(error: Exception) -> str:
    """Bound diagnostics and redact any configured OpenRouter credentials."""

    message = str(error).strip() or type(error).__name__
    candidates = [os.environ.get("OPENROUTER_API_KEY", "")]
    candidates.extend(os.environ.get("OPENROUTER_API_KEYS", "").split(","))
    for candidate in candidates:
        if candidate.strip():
            message = message.replace(candidate.strip(), "<redacted-openrouter-key>")
    return message[:4_000]


def _optional_string(value: object) -> str | None:
    """Retain observed client metadata only when it has the declared type."""

    return value if isinstance(value, str) else None


def _optional_bool(value: object) -> bool | None:
    """Retain an observed cache state without truthiness coercion."""

    return value if isinstance(value, bool) else None


def _optional_cost(value: object) -> float | None:
    """Retain a finite non-negative observed cost without guessing units."""

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        cost = float(value)
        return cost if math.isfinite(cost) and cost >= 0 else None
    return None


def verify_llm_client_revision_v1(package_file: Path, expected_commit: str) -> Path:
    """Fail before dispatch unless the imported client is the exact clean revision."""

    package = package_file.resolve()
    try:
        root_result = subprocess.run(
            ["git", "-C", str(package.parent), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        checkout_root = Path(root_result.stdout.strip()).resolve()
        head_result = subprocess.run(
            ["git", "-C", str(checkout_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        status_result = subprocess.run(
            ["git", "-C", str(checkout_root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SumoCrosswalkReviewError(
            "cannot verify imported llm_client Git revision"
        ) from exc
    if head_result.stdout.strip() != expected_commit:
        raise SumoCrosswalkReviewError("imported llm_client revision does not match pin")
    if status_result.stdout.strip():
        raise SumoCrosswalkReviewError("imported llm_client checkout is dirty")
    if checkout_root not in package.parents:
        raise SumoCrosswalkReviewError("llm_client package is outside verified checkout")
    return checkout_root


def compile_sumo_semantic_proposals_v1(
    eligible: tuple[SumoCrosswalkSemanticReviewCaseV1, ...],
    batch: SumoSemanticProposalBatchV1,
    *,
    positive_evidence: str,
    negative_evidence: str,
) -> tuple[tuple[CompiledSumoSemanticProposalV1, ...], bool]:
    """Verify complete proposal coverage, evidence offsets, and detector controls."""

    expected = {(case.donor_predicate_id, case.named_label) for case in eligible}
    observed = {(item.donor_predicate_id, item.named_label) for item in batch.proposals}
    if observed != expected:
        raise SumoCrosswalkReviewError("model proposal coverage does not match queue")
    cases = {(case.donor_predicate_id, case.named_label): case for case in eligible}
    compiled: list[CompiledSumoSemanticProposalV1] = []
    for proposal in batch.proposals:
        case = cases[(proposal.donor_predicate_id, proposal.named_label)]
        evidence = _proposal_evidence(case)[proposal.evidence_field]
        if evidence.count(proposal.evidence_quote) != 1:
            raise SumoCrosswalkReviewError("proposal quote is not uniquely grounded")
        start = evidence.index(proposal.evidence_quote)
        compiled.append(
            CompiledSumoSemanticProposalV1(
                case_id=case.case_id,
                disposition=proposal.disposition,
                evidence_field=proposal.evidence_field,
                evidence_quote=proposal.evidence_quote,
                evidence_start=start,
                evidence_end=start + len(proposal.evidence_quote),
                rationale=proposal.rationale,
                ambiguity_note=proposal.ambiguity_note,
            )
        )
    controls = {item.control_id: item for item in batch.control_results}
    controls_passed = (
        controls["positive_autonomous_actor"].disposition
        == "retain_role_narrow_type"
        and positive_evidence.count(
            controls["positive_autonomous_actor"].evidence_quote
        )
        == 1
        and controls["negative_inanimate_cause"].disposition == "reject_role_mapping"
        and negative_evidence.count(
            controls["negative_inanimate_cause"].evidence_quote
        )
        == 1
    )
    return tuple(sorted(compiled, key=lambda item: item.case_id)), controls_passed


def run_sumo_semantic_proposals_v1(
    queue: SumoCrosswalkSemanticReviewQueueV1,
    *,
    repo_root: Path,
    run_root: Path,
    config: SumoSemanticProposalRunConfigV1,
) -> tuple[SumoSemanticProposalRunV1, Path]:
    """Make one strict MiniMax proposal call and persist its exact terminal trace."""

    if run_root.exists():
        raise SumoCrosswalkReviewError("semantic proposal run root already exists")
    prompt_path = repo_root / "prompts/linguistic/sumo_crosswalk_semantic_review_v1.yaml"
    prompt_bytes = prompt_path.read_bytes()
    eligible = tuple(
        case
        for case in queue.cases
        if case.propbank.resolution_status == "exact_current_source"
    )
    withheld = tuple(
        case for case in queue.cases if case.propbank.resolution_status != "exact_current_source"
    )
    if not eligible:
        raise SumoCrosswalkReviewError("semantic proposal queue has no exact evidence cases")
    case_payload = [
        {
            "donor_predicate_id": case.donor_predicate_id,
            "named_label": case.named_label,
            **_proposal_evidence(case),
        }
        for case in eligible
    ]
    positive = {
        "control_id": "positive_autonomous_actor",
        "evidence": "An intentional autonomous actor deliberately initiated the event.",
    }
    negative = {
        "control_id": "negative_inanimate_cause",
        "evidence": "A severe storm caused the outage without intention or agency.",
    }
    import llm_client
    from llm_client import (
        RetryPolicy,
        StructuredOutputPolicy,
        call_llm_structured,
        render_prompt,
    )

    package_file = getattr(llm_client, "__file__", None)
    if not isinstance(package_file, str):
        raise SumoCrosswalkReviewError("imported llm_client has no source file")
    verify_llm_client_revision_v1(Path(package_file), config.llm_client_commit)
    run_root.mkdir(parents=True, exist_ok=False)

    messages = render_prompt(
        prompt_path,
        positive_control_json=json.dumps(positive, sort_keys=True),
        negative_control_json=json.dumps(negative, sort_keys=True),
        review_cases_json=json.dumps(case_payload, sort_keys=True),
    )
    schema_json = json.dumps(
        SumoSemanticProposalBatchV1.model_json_schema(),
        sort_keys=True,
        separators=(",", ":"),
    )
    common: _RunCommonV1 = {
        "run_id": config.run_id,
        "trace_id": config.trace_id,
        "queue_content_sha256": queue.queue_content_sha256,
        "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "response_schema_sha256": hashlib.sha256(schema_json.encode()).hexdigest(),
        "llm_client_commit": config.llm_client_commit,
        "requested_model": config.model,
        "eligible_case_ids": tuple(case.case_id for case in eligible),
        "withheld_case_ids": tuple(case.case_id for case in withheld),
        "rendered_messages": tuple(messages),
    }
    try:
        batch, result = call_llm_structured(
            config.model,
            messages,
            SumoSemanticProposalBatchV1,
            num_retries=0,
            retry=RetryPolicy(max_retries=0),
            fallback_models=[],
            cache=None,
            structured_output_policy=StructuredOutputPolicy(
                mode="require_native_json_schema"
            ),
            task="judging",
            trace_id=config.trace_id,
            max_budget=config.max_budget,
            prompt_ref=_PROMPT_REF,
        )
    except Exception as exc:
        raw_content = _optional_string(getattr(exc, "raw_content", None))
        trace = SumoSemanticProposalRunV1(
            lifecycle="provider_or_schema_failed",
            resolved_model=None,
            execution_model=None,
            cache_hit=None,
            cost_usd=None,
            raw_content=raw_content,
            batch=None,
            compiled_proposals=(),
            controls_passed=False,
            error_type=type(exc).__name__,
            error_message=_redact_openrouter_error(exc),
            **common,
        )
    else:
        raw_content = _optional_string(getattr(result, "content", None))
        try:
            compiled, controls_passed = compile_sumo_semantic_proposals_v1(
                eligible,
                batch,
                positive_evidence=positive["evidence"],
                negative_evidence=negative["evidence"],
            )
        except SumoCrosswalkReviewError as exc:
            trace = SumoSemanticProposalRunV1(
                lifecycle="evidence_validation_failed",
                resolved_model=_optional_string(getattr(result, "resolved_model", None)),
                execution_model=_optional_string(getattr(result, "execution_model", None)),
                cache_hit=_optional_bool(getattr(result, "cache_hit", None)),
                cost_usd=_optional_cost(getattr(result, "cost", None)),
                raw_content=raw_content,
                batch=batch,
                compiled_proposals=(),
                controls_passed=False,
                error_type=type(exc).__name__,
                error_message=_redact_openrouter_error(exc),
                **common,
            )
        else:
            controls_error_type = None if controls_passed else "SemanticControlFailure"
            controls_error_message = (
                None
                if controls_passed
                else "one or more preregistered semantic controls failed"
            )
            trace = SumoSemanticProposalRunV1(
                lifecycle=(
                    "proposal_generated"
                    if controls_passed
                    else "proposal_generated_controls_failed"
                ),
                resolved_model=_optional_string(getattr(result, "resolved_model", None)),
                execution_model=_optional_string(getattr(result, "execution_model", None)),
                cache_hit=_optional_bool(getattr(result, "cache_hit", None)),
                cost_usd=_optional_cost(getattr(result, "cost", None)),
                raw_content=raw_content,
                batch=batch,
                compiled_proposals=compiled,
                controls_passed=controls_passed,
                error_type=controls_error_type,
                error_message=controls_error_message,
                **common,
            )
    trace_path = run_root / "sumo_semantic_proposal_trace.json"
    payload = trace.model_dump_json(indent=2) + "\n"
    with trace_path.open("x", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return trace, trace_path
