"""M4 acquisition-family mapping evidence over the existing construction seam.

This module does not promote a mapping into a published pack. It binds the
existing M1 construction cases to exact donor role rows and 0.3.3 directional
relation/correspondence rows, then emits a compact reproducible receipt.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from linguistic_core.semantic_construction_v1 import (
    ConstructionCaseV1,
    ExactPackClosureV1,
    SemanticConstructionError,
    apply_mapping,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DonorEvidenceV1(_StrictModel):
    """One exact source-native role row supporting a transform."""

    canonical_id: str = Field(min_length=1)
    source_key: Literal["propbank_nltk"]
    source_id: str = Field(min_length=1)
    relation: Literal["positional_role"]
    evidence_ref: str = Field(min_length=1)


class RoleTransformEvidenceV1(_StrictModel):
    source_role_id: str = Field(pattern=r"^lc\.role\.")
    target_role_id: str = Field(pattern=r"^lc\.role\.")
    correspondence_relation: str = Field(min_length=1)
    source_donor: DonorEvidenceV1
    target_donor: DonorEvidenceV1


class DirectionalMappingV1(_StrictModel):
    mapping_id: str = Field(pattern=r"^m4-acquisition-[a-z0-9-]+$")
    source_predicate_id: str = Field(pattern=r"^lc:")
    target_predicate_id: str = Field(pattern=r"^lc:")
    relation: Literal["narrowerThan"]
    direction: Literal["source_to_target"]
    conditions: tuple[str, ...]
    loss_classification: Literal["lossy"]
    lost_distinctions: tuple[str, ...]
    review_status: Literal["candidate"] = "candidate"
    role_transforms: tuple[RoleTransformEvidenceV1, ...]


class MappingCaseResultV1(_StrictModel):
    case_id: str
    expected_status: Literal["allowed", "rejected"]
    observed_status: Literal["allowed", "rejected"]
    passed: bool
    reason: str


class AcquisitionMappingReportV1(_StrictModel):
    schema_version: Literal["m4-acquisition-mapping-report.v1"]
    pack_target: str
    source_case_manifest: str
    donor_mapping_asset: str
    predicate_relation_asset: str
    role_correspondence_asset: str
    directional_mappings: tuple[DirectionalMappingV1, ...]
    cases: tuple[MappingCaseResultV1, ...]
    candidate_count: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def load_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    """Load one declared JSONL asset and fail visibly on malformed input."""

    try:
        rows = tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"INVALID_M4_JSONL path={path}") from exc
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"INVALID_M4_JSONL_ROW path={path}")
    return rows


def _donor_index(
    rows: tuple[dict[str, object], ...], predicate_id: str
) -> dict[str, DonorEvidenceV1]:
    """Index PropBank role rows for one canonical predicate."""

    result: dict[str, DonorEvidenceV1] = {}
    prefix = predicate_id + ":"
    for row in rows:
        canonical_id = row.get("canonical_id")
        if (
            row.get("source_key") != "propbank_nltk"
            or row.get("relation") != "positional_role"
            or not isinstance(canonical_id, str)
            or not canonical_id.startswith(prefix + "lc.role.")
        ):
            continue
        role_id = canonical_id[len(prefix) :].split(":", 1)[-1]
        result[role_id] = DonorEvidenceV1(
            canonical_id=canonical_id,
            source_key="propbank_nltk",
            source_id=str(row["source_id"]),
            relation="positional_role",
            evidence_ref=str(row["evidence_ref"]),
        )
    return result


def _build_mapping(
    case: ConstructionCaseV1,
    closure: ExactPackClosureV1,
    donor_rows: tuple[dict[str, object], ...],
) -> DirectionalMappingV1:
    """Bind one allowed acquisition case to source-native role evidence."""

    if case.expected_status != "allowed":
        raise ValueError(f"M4_MAPPING_CASE_NOT_ALLOWED case={case.case_id}")
    try:
        observed, relation = apply_mapping(case, closure)
    except SemanticConstructionError as exc:
        raise ValueError(f"M4_MAPPING_CASE_INVALID case={case.case_id} reason={exc}") from exc
    if observed != "allowed" or relation != "narrowerThan":
        raise ValueError(f"M4_MAPPING_RELATION_INVALID case={case.case_id}")

    source_donors = _donor_index(donor_rows, case.source.identity.predicate_id)
    target_donors = _donor_index(donor_rows, case.target.identity.predicate_id)
    transforms: list[RoleTransformEvidenceV1] = []
    for item in case.request.role_transforms:
        source_donor = source_donors.get(item.source_role_id)
        target_donor = target_donors.get(item.target_role_id)
        if source_donor is None or target_donor is None:
            raise ValueError(
                "M4_DONOR_ROLE_EVIDENCE_MISSING "
                f"source={item.source_role_id} target={item.target_role_id}"
            )
        correspondence = closure.role_correspondence(
            case.source.identity.predicate_id,
            item.source_role_id,
            case.target.identity.predicate_id,
            item.target_role_id,
        )
        if correspondence is None or correspondence.get("via_relation") != relation:
            raise ValueError(
                "M4_ROLE_CORRESPONDENCE_MISSING "
                f"source={item.source_role_id} target={item.target_role_id}"
            )
        transforms.append(
            RoleTransformEvidenceV1(
                source_role_id=item.source_role_id,
                target_role_id=item.target_role_id,
                correspondence_relation=relation,
                source_donor=source_donor,
                target_donor=target_donor,
            )
        )
    return DirectionalMappingV1(
        mapping_id="m4-acquisition-buy-to-acquire",
        source_predicate_id=case.source.identity.predicate_id,
        target_predicate_id=case.target.identity.predicate_id,
        relation="narrowerThan",
        direction=case.request.direction,
        conditions=case.request.conditions,
        loss_classification="lossy",
        lost_distinctions=case.request.loss.lost_distinctions,
        role_transforms=tuple(transforms),
    )


def build_report(
    *,
    closure: ExactPackClosureV1,
    cases: tuple[ConstructionCaseV1, ...],
    case_manifest: str,
    donor_mapping_asset: str,
    predicate_relation_asset: str,
    role_correspondence_asset: str,
    donor_rows: tuple[dict[str, object], ...],
) -> AcquisitionMappingReportV1:
    """Produce the M4 report from one exact closure and selected M1 cases."""

    selected_ids = {
        "purchase_to_acquisition_allowed",
        "acquisition_to_purchase_rejected",
        "buyer_seller_swap_rejected",
    }
    selected = tuple(case for case in cases if case.case_id in selected_ids)
    if {case.case_id for case in selected} != selected_ids:
        raise ValueError("M4_REQUIRED_CASE_MISSING")
    mapping = _build_mapping(
        next(case for case in selected if case.case_id == "purchase_to_acquisition_allowed"),
        closure,
        donor_rows,
    )
    results: list[MappingCaseResultV1] = []
    for case in selected:
        try:
            observed, _relation = apply_mapping(case, closure)
            reason = "ALLOWED"
        except SemanticConstructionError as exc:
            observed = "rejected"
            reason = str(exc)
        passed = observed == case.expected_status and (
            reason == case.expected_reason or reason.startswith(case.expected_reason)
        )
        results.append(
            MappingCaseResultV1(
                case_id=case.case_id,
                expected_status=case.expected_status,
                observed_status=observed,
                passed=passed,
                reason=reason,
            )
        )
    payload = {
        "schema_version": "m4-acquisition-mapping-report.v1",
        "pack_target": str(closure.target),
        "source_case_manifest": case_manifest,
        "donor_mapping_asset": donor_mapping_asset,
        "predicate_relation_asset": predicate_relation_asset,
        "role_correspondence_asset": role_correspondence_asset,
        "directional_mappings": [mapping.model_dump(mode="json")],
        "cases": [item.model_dump(mode="json") for item in results],
        "candidate_count": 1,
        "passed": sum(item.passed for item in results),
        "failed": sum(not item.passed for item in results),
    }
    return AcquisitionMappingReportV1(
        schema_version="m4-acquisition-mapping-report.v1",
        pack_target=str(closure.target),
        source_case_manifest=case_manifest,
        donor_mapping_asset=donor_mapping_asset,
        predicate_relation_asset=predicate_relation_asset,
        role_correspondence_asset=role_correspondence_asset,
        directional_mappings=(mapping,),
        cases=tuple(results),
        candidate_count=1,
        passed=payload["passed"],
        failed=payload["failed"],
        content_sha256=_digest(payload),
    )


def render_report(report: AcquisitionMappingReportV1) -> str:
    """Render a concise human-readable receipt without changing claim status."""

    mapping = report.directional_mappings[0]
    lines = [
        "# M4 acquisition mapping report v1",
        "",
        "Candidate-only integration evidence; no published pack or consumer changed.",
        "",
        f"- Pack target: `{report.pack_target}`",
        f"- Direction: `{mapping.source_predicate_id}` → `{mapping.target_predicate_id}` (`{mapping.relation}`)",
        f"- Conditions: `{', '.join(mapping.conditions)}`",
        f"- Loss: `{mapping.loss_classification}`; `{', '.join(mapping.lost_distinctions)}`",
        f"- Role transforms: `{len(mapping.role_transforms)}`",
        f"- Donor mapping asset: `{report.donor_mapping_asset}`",
        "",
        "## Focused cases",
        "",
    ]
    for case in report.cases:
        lines.append(
            f"- `{case.case_id}`: **{'PASS' if case.passed else 'FAIL'}** — "
            f"expected `{case.expected_status}`, observed `{case.observed_status}` (`{case.reason}`)."
        )
    lines.extend(
        [
            "",
            f"**Result:** {report.passed} passed, {report.failed} failed; "
            f"content digest `{report.content_sha256}`.",
            "",
            "Reverse direction and buyer/seller filler swaps remain visible rejection cases.",
            "",
        ]
    )
    return "\n".join(lines)
