"""Compile exhaustive, non-promotional source crosswalk records for Plan 0147."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from onto_canon6.packs.linguistic_source_audit_v1 import LinguisticDonorLabelAuditV1
from onto_canon6.packs.semantic_provenance import SemanticMappingRecord
from onto_canon6.packs.sumo_governed_crosswalk_v1 import GovernedSumoCrosswalkV1


CrosswalkState = Literal["candidate", "rejected", "unresolved", "verified"]
SourceIdentityState = Literal[
    "exact_current_source", "missing_current_source", "invalid_donor_id", "not_applicable"
]


class LinguisticCrosswalkRecordV1(BaseModel):
    """One source-presence result that deliberately does not infer semantic truth."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(pattern=r"^lcx1_[0-9a-f]{24}$")
    canonical_id: str = Field(min_length=1)
    canonical_kind: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    producer_method: str = Field(min_length=1)
    producer_confidence: float | None = Field(default=None, ge=0, le=1)
    producer_method_scope: str | None = Field(default=None)
    evidence_ref: str = Field(min_length=1)
    source_identity_state: SourceIdentityState
    state: CrosswalkState
    verification_basis: Literal["none"] = "none"

    @model_validator(mode="after")
    def _non_promotional(self) -> "LinguisticCrosswalkRecordV1":
        expected = _record_id(
            self.canonical_id, self.source_key, self.source_id, self.relation, self.evidence_ref
        )
        if self.record_id != expected:
            raise ValueError("crosswalk record ID does not reconcile")
        if self.state == "verified":
            raise ValueError("compiler cannot emit verified crosswalk state")
        if self.verification_basis != "none":
            raise ValueError("compiler has no semantic verification basis")
        return self


class LinguisticCrosswalkV1(BaseModel):
    """Closed crosswalk population compiled from all immutable donor mapping rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-crosswalk-v1"] = "linguistic-crosswalk-v1"
    donor_audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_mapping_count: int = Field(ge=0)
    reviewed_record_count: int = Field(ge=0)
    records: tuple[LinguisticCrosswalkRecordV1, ...]
    candidate_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    verified_count: Literal[0] = 0
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _closed(self) -> "LinguisticCrosswalkV1":
        if self.input_mapping_count + self.reviewed_record_count != len(self.records):
            raise ValueError("crosswalk input population does not reconcile")
        record_ids = [item.record_id for item in self.records]
        if record_ids != sorted(record_ids):
            raise ValueError("crosswalk records must be sorted")
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("crosswalk record IDs must be unique")
        if self.reviewed_record_count != sum(
            item.source_key == "sumo_governed_review_v1" for item in self.records
        ):
            raise ValueError("reviewed crosswalk population does not reconcile")
        counts = {
            state: sum(item.state == state for item in self.records)
            for state in ("candidate", "rejected", "unresolved")
        }
        if (self.candidate_count, self.rejected_count, self.unresolved_count) != (
            counts["candidate"],
            counts["rejected"],
            counts["unresolved"],
        ):
            raise ValueError("crosswalk state counts do not reconcile")
        if self.content_sha256 != _sha256(self.records):
            raise ValueError("crosswalk content digest does not reconcile")
        return self


def _sha256(value: object) -> str:
    """Hash Pydantic values with one canonical representation."""

    return hashlib.sha256(
        json.dumps(
            value,
            default=lambda item: item.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _record_id(
    canonical_id: str, source_key: str, source_id: str, relation: str, evidence_ref: str
) -> str:
    """Return the stable identity for one mapping occurrence, including its evidence."""

    return (
        "lcx1_"
        + hashlib.sha256(
            f"{canonical_id}\0{source_key}\0{source_id}\0{relation}\0{evidence_ref}".encode()
        ).hexdigest()[:24]
    )


def compile_linguistic_crosswalk_v1(
    mappings: tuple[SemanticMappingRecord, ...], audit: LinguisticDonorLabelAuditV1
) -> LinguisticCrosswalkV1:
    """Classify every mapping row without accepting semantic equivalence."""

    audit_sha = _sha256(audit.model_dump(mode="json"))
    comparisons: dict[tuple[str, str], str] = {
        (item.family, item.donor_id): item.status for item in audit.comparisons
    }
    family_by_key = {
        "propbank_nltk": "propbank",
        "framenet_candidate": "framenet",
        "sumo_donor_types": "sumo",
    }
    records: list[LinguisticCrosswalkRecordV1] = []
    for mapping in mappings:
        family = family_by_key.get(mapping.source_key)
        source_id = (
            mapping.source_id.rsplit(":", 1)[0]
            if mapping.source_key == "propbank_nltk"
            else mapping.source_id
        )
        status = comparisons.get((family, source_id)) if family is not None else None
        identity = cast(
            SourceIdentityState,
            {
                "matched_current_source": "exact_current_source",
                "missing_current_source": "missing_current_source",
                "invalid_donor_id": "invalid_donor_id",
            }.get(status or "", "not_applicable"),
        )
        state: CrosswalkState = (
            "candidate" if mapping.relation == "candidate_alignment" else "unresolved"
        )
        records.append(
            LinguisticCrosswalkRecordV1(
                record_id=_record_id(
                    mapping.canonical_id,
                    mapping.source_key,
                    mapping.source_id,
                    mapping.relation,
                    mapping.evidence_ref,
                ),
                canonical_id=mapping.canonical_id,
                canonical_kind=mapping.canonical_kind,
                source_key=mapping.source_key,
                source_id=mapping.source_id,
                relation=mapping.relation,
                producer_method=mapping.derivation_method,
                producer_confidence=mapping.row_mapping_confidence,
                producer_method_scope=mapping.row_mapping_method_scope,
                evidence_ref=mapping.evidence_ref,
                source_identity_state=identity,
                state=state,
            )
        )
    ordered = tuple(sorted(records, key=lambda item: item.record_id))
    return LinguisticCrosswalkV1(
        donor_audit_sha256=audit_sha,
        input_mapping_count=len(mappings),
        reviewed_record_count=0,
        records=ordered,
        candidate_count=sum(item.state == "candidate" for item in ordered),
        rejected_count=0,
        unresolved_count=sum(item.state == "unresolved" for item in ordered),
        content_sha256=_sha256(ordered),
    )


def append_reviewed_sumo_role_records_v1(
    crosswalk: LinguisticCrosswalkV1,
    *,
    reviewed_roles: tuple[tuple[str, str, str, Literal["rejected", "unresolved"]], ...],
) -> LinguisticCrosswalkV1:
    """Append exact reviewed SUMO role outcomes without rewriting donor mappings.

    Each input carries the donor predicate, canonical role ID, exact ARG source
    identifier, and the retained governed-review disposition.  It therefore
    remains distinct from the donor's direct role-identity traceability row.
    """

    records = list(crosswalk.records)
    for predicate_id, canonical_role_id, arg_source_id, state in reviewed_roles:
        records.append(
            LinguisticCrosswalkRecordV1(
                record_id=_record_id(
                    canonical_role_id,
                    "sumo_governed_review_v1",
                    arg_source_id,
                    "agent_role_mapping",
                    f"sumo-review:{predicate_id}",
                ),
                canonical_id=canonical_role_id,
                canonical_kind="role_slot",
                source_key="sumo_governed_review_v1",
                source_id=arg_source_id,
                relation="agent_role_mapping",
                producer_method="independent_review_of_proposal",
                producer_confidence=None,
                producer_method_scope="reviewed_case_specific",
                evidence_ref=f"sumo-review:{predicate_id}",
                source_identity_state="exact_current_source",
                state=state,
            )
        )
    ordered = tuple(sorted(records, key=lambda item: item.record_id))
    return LinguisticCrosswalkV1(
        donor_audit_sha256=crosswalk.donor_audit_sha256,
        input_mapping_count=crosswalk.input_mapping_count,
        reviewed_record_count=crosswalk.reviewed_record_count + len(reviewed_roles),
        records=ordered,
        candidate_count=sum(item.state == "candidate" for item in ordered),
        rejected_count=sum(item.state == "rejected" for item in ordered),
        unresolved_count=sum(item.state == "unresolved" for item in ordered),
        content_sha256=_sha256(ordered),
    )


def bind_reviewed_sumo_roles_v1(
    mappings: tuple[SemanticMappingRecord, ...],
    *,
    donor_database: Path,
    governed: GovernedSumoCrosswalkV1,
) -> tuple[tuple[str, str, str, Literal["rejected", "unresolved"]], ...]:
    """Close every reviewed case through exact donor role and mapping identities."""

    role_index = {
        mapping.source_id: mapping.canonical_id
        for mapping in mappings
        if mapping.source_key == "onto_canon_sumo_plus"
        and mapping.canonical_kind == "role_slot"
        and mapping.relation == "positional_role"
    }
    database = donor_database.resolve()
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro&immutable=1", uri=True)
    try:
        rows: list[tuple[str, str, str, Literal["rejected", "unresolved"]]] = []
        for record in governed.records:
            row = connection.execute(
                "SELECT arg_position FROM role_slots WHERE event_sense_id = ? AND named_label = ?",
                (record.donor_predicate_id, record.named_label),
            ).fetchone()
            if row is None:
                raise ValueError("reviewed SUMO case has no donor role row")
            source_id = f"{record.donor_predicate_id}:{row[0]}"
            canonical_id = role_index.get(source_id)
            if canonical_id is None:
                raise ValueError("reviewed SUMO case has no canonical role mapping")
            rows.append((record.donor_predicate_id, canonical_id, source_id, record.state))
    finally:
        connection.close()
    if hashlib.sha256(database.read_bytes()).hexdigest() != before:
        raise ValueError("donor database changed during reviewed SUMO role binding")
    return tuple(sorted(rows))
