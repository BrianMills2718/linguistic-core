"""Closed source-identity accounting for the Plan 0147 governed crosswalk."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from linguistic_core.framenet_projection_v1 import FrameNetProjectionV1
from linguistic_core.linguistic_crosswalk_v1 import LinguisticCrosswalkV1
from linguistic_core.linguistic_source_audit_v1 import LinguisticDonorLabelAuditV1
from linguistic_core.linguistic_source_projection_v1 import PropBankProjectionV1
from linguistic_core.sumo_projection_v1 import SumoProjectionV1


SourceFamily = Literal["propbank", "framenet", "sumo"]


def _sha256(value: object) -> str:
    """Return a canonical SHA-256 digest without mutating any input."""

    return hashlib.sha256(
        json.dumps(
            value,
            default=lambda item: item.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


class SourceIdentityCoverageV1(BaseModel):
    """Population equation for one exact source identity family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: SourceFamily
    source_identity_count: int = Field(ge=0)
    source_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    donor_identifier_count: int = Field(ge=0)
    matched_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    extra_current_source_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _closed(self) -> "SourceIdentityCoverageV1":
        if self.donor_identifier_count != sum(
            (self.matched_count, self.missing_count, self.invalid_count, self.unavailable_count)
        ):
            raise ValueError("donor identity disposition does not reconcile")
        if self.unavailable_count:
            raise ValueError("crosswalk coverage requires an available exact source")
        if self.source_identity_count != self.matched_count + self.extra_current_source_count:
            raise ValueError("source identity population does not reconcile")
        return self


class LinguisticCrosswalkCoverageV1(BaseModel):
    """Machine-consumed complete classification evidence for the crosswalk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-crosswalk-coverage-v1"] = "linguistic-crosswalk-coverage-v1"
    donor_audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    crosswalk_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    families: tuple[SourceIdentityCoverageV1, ...]
    crosswalk_record_count: int = Field(ge=0)
    exact_current_source_count: int = Field(ge=0)
    missing_current_source_count: int = Field(ge=0)
    invalid_donor_id_count: int = Field(ge=0)
    not_applicable_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    verified_count: Literal[0] = 0
    coverage_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _closed(self) -> "LinguisticCrosswalkCoverageV1":
        if [item.family for item in self.families] != ["propbank", "framenet", "sumo"]:
            raise ValueError("source-family coverage must be complete and sorted")
        if self.crosswalk_record_count != sum(
            (
                self.exact_current_source_count,
                self.missing_current_source_count,
                self.invalid_donor_id_count,
                self.not_applicable_count,
            )
        ):
            raise ValueError("crosswalk identity states do not reconcile")
        if self.crosswalk_record_count != sum(
            (self.candidate_count, self.rejected_count, self.unresolved_count, self.verified_count)
        ):
            raise ValueError("crosswalk semantic states do not reconcile")
        content = self.model_dump(mode="json", exclude={"coverage_content_sha256"})
        if self.coverage_content_sha256 != _sha256(content):
            raise ValueError("crosswalk coverage digest does not reconcile")
        return self


def build_linguistic_crosswalk_coverage_v1(
    audit: LinguisticDonorLabelAuditV1,
    crosswalk: LinguisticCrosswalkV1,
    propbank: PropBankProjectionV1,
    framenet: FrameNetProjectionV1,
    sumo: SumoProjectionV1,
) -> LinguisticCrosswalkCoverageV1:
    """Account for every donor and current-source identity without semantic promotion."""

    source_ids: dict[SourceFamily, set[str]] = {
        "propbank": {item.roleset_id for item in propbank.rolesets},
        "framenet": {item.name for item in framenet.frames},
        "sumo": {item.term for item in sumo.types},
    }
    source_id_sets = {family: tuple(sorted(ids)) for family, ids in source_ids.items()}
    summaries = audit.summary_by_family()
    family_order: tuple[SourceFamily, ...] = ("propbank", "framenet", "sumo")
    families = tuple(
        SourceIdentityCoverageV1(
            family=family,
            source_identity_count=len(source_id_sets[family]),
            source_identity_sha256=_sha256(source_id_sets[family]),
            donor_identifier_count=summaries[family].donor_identifier_count,
            matched_count=summaries[family].matched_count,
            missing_count=summaries[family].missing_count,
            invalid_count=summaries[family].invalid_count,
            unavailable_count=summaries[family].unavailable_count,
            extra_current_source_count=len(source_id_sets[family])
            - summaries[family].matched_count,
        )
        for family in family_order
    )
    identity_counts = {
        f"{state}_count": sum(item.source_identity_state == state for item in crosswalk.records)
        for state in (
            "exact_current_source",
            "missing_current_source",
            "invalid_donor_id",
            "not_applicable",
        )
    }
    state_counts = {
        f"{state}_count": sum(item.state == state for item in crosswalk.records)
        for state in ("candidate", "rejected", "unresolved")
    }
    content = {
        "schema_version": "linguistic-crosswalk-coverage-v1",
        "donor_audit_sha256": _sha256(audit.model_dump(mode="json")),
        "crosswalk_content_sha256": crosswalk.content_sha256,
        "families": families,
        "crosswalk_record_count": len(crosswalk.records),
        **identity_counts,
        **state_counts,
        "verified_count": 0,
    }
    return LinguisticCrosswalkCoverageV1.model_validate(
        {**content, "coverage_content_sha256": _sha256(content)}
    )
