"""Build source-bound semantic-review cases without deciding or accepting them."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Literal
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
