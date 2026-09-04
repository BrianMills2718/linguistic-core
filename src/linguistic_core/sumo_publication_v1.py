"""Compile a fail-closed, module-scoped SUMO publication profile.

The full pinned SUMO projection remains an external-cache audit input.  This
module publishes only source facts whose every formula closes to an explicitly
approved module and whose exact notice is retained alongside the derived data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from linguistic_core.sumo_projection_v1 import (
    SumoArgumentConstraintV1,
    SumoBinaryAxiomV1,
    SumoFormulaRefV1,
    SumoInstanceAxiomV1,
    SumoProjectionV1,
)


class SumoPublicationError(ValueError):
    """Raised when a source module cannot be published under the reviewed profile."""


def _canonical_sha256(value: object) -> str:
    """Hash Pydantic-compatible evidence with deterministic JSON framing."""

    return hashlib.sha256(
        json.dumps(
            value,
            default=lambda item: item.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


class SumoOfficialEvidenceV1(BaseModel):
    """One public primary-source observation used by the technical review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str = Field(pattern=r"^https://", description="Official evidence URL.")
    accessed_on: str = Field(pattern=r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}$")
    observation: str = Field(min_length=1)


class ApprovedSumoModuleV1(BaseModel):
    """One exact source module approved for a named bounded profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license_id: Literal["LicenseRef-IEEE-SUMO-2004"]
    notice_start_line: int = Field(gt=0)
    notice_end_line: int = Field(gt=0)
    required_acknowledgement: str = Field(min_length=1)

    @model_validator(mode="after")
    def _safe_and_ordered(self) -> "ApprovedSumoModuleV1":
        path = PurePosixPath(self.path)
        if path.is_absolute() or path.name != self.path or ".." in path.parts:
            raise ValueError("approved SUMO module must be one safe root filename")
        if self.notice_end_line < self.notice_start_line:
            raise ValueError("SUMO notice line range is reversed")
        return self


class SumoModulePublicationConfigV1(BaseModel):
    """Reviewed publication decision, separate from automated header detection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["sumo-module-publication-config-v1"]
    profile_id: Literal["linguistic-bounded-context-v1"]
    source_key: Literal["sumo_root_kif"]
    source_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    selected_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_modules: tuple[ApprovedSumoModuleV1, ...] = Field(min_length=1)
    excluded_module_policy: Literal["excluded_pending_module_specific_review"]
    full_projection_publication_status: Literal["blocked_mixed_license"]
    official_evidence: tuple[SumoOfficialEvidenceV1, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _profile_is_narrow(self) -> "SumoModulePublicationConfigV1":
        paths = tuple(item.path for item in self.approved_modules)
        if paths != ("Merge.kif",):
            raise ValueError("publication v1 approves only exact Merge.kif-derived context")
        return self


HeaderClass = Literal[
    "ieee_custom_notice",
    "gpl_notice",
    "lgpl_notice",
    "creative_commons_notice",
    "mixed_notice",
    "unclassified_no_header_notice",
]


class SumoModuleDispositionV1(BaseModel):
    """Observed header class plus explicit profile inclusion decision for one module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    header_class: HeaderClass
    publication_disposition: Literal[
        "approved_for_linguistic_bounded_context",
        "excluded_pending_module_specific_review",
    ]


class PublishedSumoContextV1(BaseModel):
    """Exact Merge.kif-only context without the externally defined Leaving edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_module: Literal["Merge.kif"] = "Merge.kif"
    translocation_type_hierarchy: tuple[str, ...] = Field(min_length=2)
    autonomous_agent_type_hierarchy: tuple[str, ...] = Field(min_length=2)
    case_roles: tuple[str, ...] = Field(min_length=1)
    agent_constraints: tuple[SumoArgumentConstraintV1, ...] = Field(min_length=1)
    patient_constraints: tuple[SumoArgumentConstraintV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _is_exact_profile(self) -> "PublishedSumoContextV1":
        if self.translocation_type_hierarchy[0] != "Translocation":
            raise ValueError("published hierarchy must begin at exact Merge.kif Translocation")
        if "Leaving" in self.translocation_type_hierarchy:
            raise ValueError("Leaving is defined outside the approved Merge.kif module")
        if self.case_roles != ("agent", "patient"):
            raise ValueError("published context requires only the reviewed case roles")
        return self


class PublishedSumoBoundedContextV1(BaseModel):
    """Small distributable SUMO context derived only from one approved module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["published-sumo-bounded-context-v1"] = (
        "published-sumo-bounded-context-v1"
    )
    profile_id: Literal["linguistic-bounded-context-v1"]
    source_key: Literal["sumo_root_kif"]
    source_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    selected_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_module: Literal["Merge.kif"]
    source_module_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license_id: Literal["LicenseRef-IEEE-SUMO-2004"]
    license_notice_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    attribution_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_source_module_packaged: Literal[False] = False
    full_projection_packaged: Literal[False] = False
    bounded_context: PublishedSumoContextV1
    translocation_hierarchy_axioms: tuple[SumoBinaryAxiomV1, ...] = Field(min_length=1)
    autonomous_agent_hierarchy_axioms: tuple[SumoBinaryAxiomV1, ...] = Field(min_length=1)
    case_role_axioms: tuple[SumoInstanceAxiomV1, ...] = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _context_closes_to_approved_module(self) -> "PublishedSumoBoundedContextV1":
        expected_translocation_edges = tuple(
            zip(
                self.bounded_context.translocation_type_hierarchy,
                self.bounded_context.translocation_type_hierarchy[1:],
            )
        )
        expected_agent_edges = tuple(
            zip(
                self.bounded_context.autonomous_agent_type_hierarchy,
                self.bounded_context.autonomous_agent_type_hierarchy[1:],
            )
        )
        if tuple((item.child, item.parent) for item in self.translocation_hierarchy_axioms) != (
            expected_translocation_edges
        ):
            raise ValueError("published SUMO Translocation hierarchy axioms do not reconcile")
        if (
            tuple((item.child, item.parent) for item in self.autonomous_agent_hierarchy_axioms)
            != expected_agent_edges
        ):
            raise ValueError("published SUMO agent hierarchy axioms do not reconcile")
        if (
            tuple(item.instance for item in self.case_role_axioms)
            != self.bounded_context.case_roles
        ):
            raise ValueError("published SUMO case-role axioms do not reconcile")
        if any(item.class_term != "CaseRole" for item in self.case_role_axioms):
            raise ValueError("published SUMO case-role declaration has the wrong class")
        refs_list: list[SumoFormulaRefV1] = []
        refs_list.extend(item.source_ref for item in self.translocation_hierarchy_axioms)
        refs_list.extend(item.source_ref for item in self.autonomous_agent_hierarchy_axioms)
        refs_list.extend(item.source_ref for item in self.case_role_axioms)
        refs_list.extend(item.source_ref for item in self.bounded_context.agent_constraints)
        refs_list.extend(item.source_ref for item in self.bounded_context.patient_constraints)
        refs = tuple(refs_list)
        if self.bounded_context.source_module != self.source_module or any(
            ref.module_path != self.source_module or ref.module_sha256 != self.source_module_sha256
            for ref in refs
        ):
            raise ValueError("published SUMO context escapes its approved module")
        content = self.model_dump(mode="json", exclude={"content_sha256"})
        if self.content_sha256 != _canonical_sha256(content):
            raise ValueError("published SUMO context digest does not reconcile")
        return self


class SumoModulePublicationReviewV1(BaseModel):
    """Complete 66-module disposition and the one bounded publishable output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["sumo-module-publication-review-v1"] = (
        "sumo-module-publication-review-v1"
    )
    profile_id: Literal["linguistic-bounded-context-v1"]
    source_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    selected_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_module_count: int = Field(gt=0)
    approved_module_count: int = Field(gt=0)
    excluded_module_count: int = Field(ge=0)
    full_projection_publication_status: Literal["blocked_mixed_license"]
    module_dispositions: tuple[SumoModuleDispositionV1, ...]
    published_context_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    official_evidence: tuple[SumoOfficialEvidenceV1, ...]
    legal_advice_claimed: Literal[False] = False
    review_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _population_reconciles(self) -> "SumoModulePublicationReviewV1":
        paths = tuple(item.path for item in self.module_dispositions)
        if paths != tuple(sorted(set(paths))) or len(paths) != self.selected_module_count:
            raise ValueError("SUMO module review is not sorted, unique, and complete")
        approved = sum(
            item.publication_disposition == "approved_for_linguistic_bounded_context"
            for item in self.module_dispositions
        )
        if approved != self.approved_module_count:
            raise ValueError("approved SUMO module count does not reconcile")
        if approved + self.excluded_module_count != self.selected_module_count:
            raise ValueError("SUMO publication dispositions do not reconcile")
        content = self.model_dump(mode="json", exclude={"review_content_sha256"})
        if self.review_content_sha256 != _canonical_sha256(content):
            raise ValueError("SUMO publication review digest does not reconcile")
        return self


def load_sumo_module_publication_config_v1(path: Path) -> SumoModulePublicationConfigV1:
    """Load the reviewed profile without accepting unknown configuration fields."""

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SumoPublicationError("unable to load SUMO publication config") from exc
    return SumoModulePublicationConfigV1.model_validate(payload)


def _header_class(payload: bytes, *, approved: bool) -> HeaderClass:
    """Classify observed notice signals without turning detection into legal approval."""

    header = payload.splitlines()[:120]
    text = b"\n".join(header).decode("utf-8", errors="replace").lower()
    has_gpl = "gnu general public" in text or "gnu public license" in text
    has_lgpl = "gnu lesser general public" in text
    has_cc = "creative commons" in text or "create commons" in text
    if approved and "ieee" in text and "prepare derivative works" in text:
        return "ieee_custom_notice"
    if sum((has_gpl, has_lgpl, has_cc)) > 1:
        return "mixed_notice"
    if has_lgpl:
        return "lgpl_notice"
    if has_gpl:
        return "gpl_notice"
    if has_cc:
        return "creative_commons_notice"
    return "unclassified_no_header_notice"


def _attribution_text(
    *, config: SumoModulePublicationConfigV1, source_payload: bytes
) -> tuple[str, str]:
    """Return acknowledgement plus the exact reviewed source notice lines."""

    approved = config.approved_modules[0]
    lines = source_payload.decode("utf-8", errors="strict").splitlines()
    if len(lines) < approved.notice_end_line:
        raise SumoPublicationError("approved SUMO notice line range exceeds source module")
    # Source padding is layout-only; normalize it so the packaged notice is
    # stable in text tooling while retaining every non-whitespace character.
    notice = (
        "\n".join(
            line.rstrip()
            for line in lines[approved.notice_start_line - 1 : approved.notice_end_line]
        )
        + "\n"
    )
    if (
        "IEEE hereby grants Licensee" not in notice
        or "prepare derivative works" not in notice
        or "appropriately acknowledged" not in notice
    ):
        raise SumoPublicationError("approved SUMO notice no longer contains required grant")
    text = (
        "SUMO bounded linguistic context\n"
        f"Source: https://github.com/ontologyportal/sumo at {config.source_commit_sha}\n"
        f"Source module: {approved.path} ({approved.sha256})\n"
        f"Acknowledgement: {approved.required_acknowledgement}\n"
        "Only derived bounded facts are packaged; the raw module and full projection are not.\n\n"
        "Exact source license notice:\n"
        f"{notice}"
    )
    return text, hashlib.sha256(notice.encode("utf-8")).hexdigest()


def compile_sumo_publication_v1(
    projection: SumoProjectionV1,
    *,
    source_checkout: Path,
    config: SumoModulePublicationConfigV1,
) -> tuple[SumoModulePublicationReviewV1, PublishedSumoBoundedContextV1, str]:
    """Compile a complete disposition and one exact, license-scoped context."""

    if (
        projection.source_key != config.source_key
        or projection.source_commit_sha != config.source_commit_sha
        or projection.source_tree_sha != config.source_tree_sha
        or projection.selected_payload_sha256 != config.selected_payload_sha256
    ):
        raise SumoPublicationError("SUMO publication config targets another source projection")
    approved_by_path = {item.path: item for item in config.approved_modules}
    dispositions: list[SumoModuleDispositionV1] = []
    payload_by_path: dict[str, bytes] = {}
    for module in projection.modules:
        path = source_checkout / module.path
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise SumoPublicationError(
                f"unable to read selected SUMO module: {module.path}"
            ) from exc
        observed = hashlib.sha256(payload).hexdigest()
        if observed != module.sha256 or len(payload) != module.byte_count:
            raise SumoPublicationError(f"SUMO selected module identity changed: {module.path}")
        payload_by_path[module.path] = payload
        approved = approved_by_path.get(module.path)
        if approved is not None and approved.sha256 != observed:
            raise SumoPublicationError(f"approved SUMO module hash changed: {module.path}")
        header_class = _header_class(payload, approved=approved is not None)
        if approved is not None and header_class != "ieee_custom_notice":
            raise SumoPublicationError("approved SUMO module lacks the reviewed IEEE notice")
        dispositions.append(
            SumoModuleDispositionV1(
                path=module.path,
                sha256=observed,
                header_class=header_class,
                publication_disposition=(
                    "approved_for_linguistic_bounded_context"
                    if approved is not None
                    else "excluded_pending_module_specific_review"
                ),
            )
        )
    if set(approved_by_path) - set(payload_by_path):
        raise SumoPublicationError("approved SUMO module is absent from selected projection")
    source_payload = payload_by_path["Merge.kif"]
    attribution, notice_sha256 = _attribution_text(config=config, source_payload=source_payload)
    attribution_sha256 = hashlib.sha256(attribution.encode("utf-8")).hexdigest()

    def exact_merge_subclass_axiom(child: str, parent: str) -> SumoBinaryAxiomV1:
        matches = [
            item
            for item in projection.subclass_axioms
            if item.child == child
            and item.parent == parent
            and item.source_ref.module_path == "Merge.kif"
        ]
        if len(matches) != 1:
            raise SumoPublicationError(
                f"bounded SUMO hierarchy edge lacks one exact Merge.kif formula: {child}->{parent}"
            )
        return matches[0]

    def exact_merge_case_role(role: str) -> SumoInstanceAxiomV1:
        matches = [
            item
            for item in projection.instance_axioms
            if item.instance == role
            and item.class_term == "CaseRole"
            and item.source_ref.module_path == "Merge.kif"
        ]
        if len(matches) != 1:
            raise SumoPublicationError(
                f"bounded SUMO case role lacks one exact Merge.kif formula: {role}"
            )
        return matches[0]

    published_context = PublishedSumoContextV1(
        translocation_type_hierarchy=projection.bounded_context.leaving_type_hierarchy[1:],
        autonomous_agent_type_hierarchy=(
            projection.bounded_context.autonomous_agent_type_hierarchy
        ),
        case_roles=projection.bounded_context.case_roles,
        agent_constraints=projection.bounded_context.agent_constraints,
        patient_constraints=projection.bounded_context.patient_constraints,
    )
    translocation_axioms = tuple(
        exact_merge_subclass_axiom(child, parent)
        for child, parent in zip(
            published_context.translocation_type_hierarchy,
            published_context.translocation_type_hierarchy[1:],
        )
    )
    agent_axioms = tuple(
        exact_merge_subclass_axiom(child, parent)
        for child, parent in zip(
            projection.bounded_context.autonomous_agent_type_hierarchy,
            projection.bounded_context.autonomous_agent_type_hierarchy[1:],
        )
    )
    case_role_axioms = tuple(
        exact_merge_case_role(role) for role in projection.bounded_context.case_roles
    )
    context_content = {
        "schema_version": "published-sumo-bounded-context-v1",
        "profile_id": config.profile_id,
        "source_key": config.source_key,
        "source_commit_sha": config.source_commit_sha,
        "source_tree_sha": config.source_tree_sha,
        "selected_payload_sha256": config.selected_payload_sha256,
        "source_module": "Merge.kif",
        "source_module_sha256": approved_by_path["Merge.kif"].sha256,
        "license_id": approved_by_path["Merge.kif"].license_id,
        "license_notice_sha256": notice_sha256,
        "attribution_sha256": attribution_sha256,
        "raw_source_module_packaged": False,
        "full_projection_packaged": False,
        "bounded_context": published_context,
        "translocation_hierarchy_axioms": translocation_axioms,
        "autonomous_agent_hierarchy_axioms": agent_axioms,
        "case_role_axioms": case_role_axioms,
    }
    published = PublishedSumoBoundedContextV1.model_validate(
        {**context_content, "content_sha256": _canonical_sha256(context_content)}
    )
    review_content = {
        "schema_version": "sumo-module-publication-review-v1",
        "profile_id": config.profile_id,
        "source_commit_sha": config.source_commit_sha,
        "source_tree_sha": config.source_tree_sha,
        "selected_payload_sha256": config.selected_payload_sha256,
        "selected_module_count": len(dispositions),
        "approved_module_count": len(approved_by_path),
        "excluded_module_count": len(dispositions) - len(approved_by_path),
        "full_projection_publication_status": config.full_projection_publication_status,
        "module_dispositions": tuple(sorted(dispositions, key=lambda item: item.path)),
        "published_context_content_sha256": published.content_sha256,
        "official_evidence": config.official_evidence,
        "legal_advice_claimed": False,
    }
    review = SumoModulePublicationReviewV1.model_validate(
        {**review_content, "review_content_sha256": _canonical_sha256(review_content)}
    )
    return review, published, attribution
