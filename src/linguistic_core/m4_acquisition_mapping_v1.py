"""M4 acquisition-family mapping evidence over the existing construction seam.

This module does not promote a mapping into a published pack. It binds the
existing M1 construction cases to the retained M3 PropBank evidence and exact
0.3.0/0.3.3 rows, then emits a compact reproducible receipt.
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


class PropBankEvidenceV1(_StrictModel):
    """Exact retained M3 metadata and one source-native ``buy.01`` example."""

    source_key: Literal["propbank_frames_34"]
    source_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    selected_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    projection_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    roleset_id: Literal["buy.01"]
    source_relative_path: Literal["frames/buy.xml"]
    example_index: int = Field(ge=0)
    sentence: str = Field(min_length=1)
    relation_text: str = Field(min_length=1)
    relation_token_locations: str = Field(min_length=1)
    arguments: tuple[tuple[str, str, str, str], ...]


class RoleTransformEvidenceV1(_StrictModel):
    source_role_id: str = Field(pattern=r"^lc\.role\.")
    target_role_id: str = Field(pattern=r"^lc\.role\.")
    correspondence_relation: str = Field(min_length=1)
    source_donor: DonorEvidenceV1
    target_donor: DonorEvidenceV1
    donor_assertion: Literal["source_native_propbank_role"]
    authored_mapping: str = Field(min_length=1)
    evidence_sentence: str = Field(min_length=1)
    ambiguity_disposition: Literal["resolved_by_exact_source_alignment"]


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
    ambiguity_disposition: Literal["resolved_by_exact_source_alignment"]
    unresolved: tuple[str, ...]
    source_evidence: PropBankEvidenceV1
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
    m3_reconciliation_asset: str
    m3_projection_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
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


_M3_EXPECTED = {
    "source_key": "propbank_frames_34",
    "source_commit_sha": "c66e0ccf28b53f00051b187db83e937b5bee2e32",
    "source_tree_sha": "d1e1ef0c13c5ec6e06096b1448cb5f65d4e1b8c7",
    "selected_payload_sha256": "22606e705b97b8d9c90f673e6a7023e4852aef736b9d935e01fd31049b29fb04",
    "projection_content_sha256": "e2628942b04c0bc66bb6081c4e953548a29970574ac8ec73fa626f9ce2dd59b0",
}
_DONOR_SHA256 = "16f18feafe28a2cce14e8e25f417c082f8dd910b2fd6b859b01d337d86b0c6a9"
_EXPECTED_DONORS = {
    "lc:buy_purchase:lc.role.buyer": ("buy-01:ARG0", "sqlite:role_slots[event_sense_id=buy_purchase,arg_position=ARG0]"),
    "lc:buy_purchase:lc.role.goods": ("buy-01:ARG1", "sqlite:role_slots[event_sense_id=buy_purchase,arg_position=ARG1]"),
    "lc:buy_purchase:lc.role.seller": ("buy-01:ARG2", "sqlite:role_slots[event_sense_id=buy_purchase,arg_position=ARG2]"),
    "lc:acquire_get_obtain:lc.role.recipient": ("acquire-01:ARG0", "sqlite:role_slots[event_sense_id=acquire_get_obtain,arg_position=ARG0]"),
    "lc:acquire_get_obtain:lc.role.theme": ("acquire-01:ARG1", "sqlite:role_slots[event_sense_id=acquire_get_obtain,arg_position=ARG1]"),
    "lc:acquire_get_obtain:lc.role.source": ("acquire-01:ARG2", "sqlite:role_slots[event_sense_id=acquire_get_obtain,arg_position=ARG2]"),
}


def load_m3_evidence(path: Path) -> PropBankEvidenceV1:
    """Load and validate the exact retained M3 reconciliation record."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = payload["acquisition_example"]
        meta = {key: payload[key] for key in _M3_EXPECTED}
        example = record["record"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"M4_M3_EVIDENCE_INVALID path={path}") from exc
    if payload.get("schema_version") != "propbank-example-reconciliation-v1":
        raise ValueError("M4_M3_EVIDENCE_SCHEMA_DRIFT")
    if meta != _M3_EXPECTED or record.get("roleset_id") != "buy.01":
        raise ValueError("M4_M3_EVIDENCE_PROVENANCE_DRIFT")
    expected_args = (
        ("ARG0", "0", "1", "The company"),
        ("ARG1", "3", "6", "a wheel - loader"),
        ("ARG2", "7", "8", "from Dresser"),
    )
    observed_args = tuple(
        (str(item["argument_type"]), str(item["start"]), str(item["end"]), str(item["text"]))
        for item in example.get("arguments", ())
    )
    if (
        record.get("example_index") != 4
        or record.get("source_relative_path") != "frames/buy.xml"
        or example.get("text") != "The company bought a wheel - loader from Dresser ."
        or example.get("relation") != {"text": "bought", "token_locations": "2"}
        or observed_args != expected_args
    ):
        raise ValueError("M4_M3_EVIDENCE_EXAMPLE_DRIFT")
    return PropBankEvidenceV1(
        **meta,
        roleset_id="buy.01",
        source_relative_path="frames/buy.xml",
        example_index=4,
        sentence=example["text"],
        relation_text=example["relation"]["text"],
        relation_token_locations=example["relation"]["token_locations"],
        arguments=observed_args,
    )


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
        expected = _EXPECTED_DONORS.get(canonical_id)
        if expected is None:
            continue
        if row.get("source_id") != expected[0] or row.get("evidence_ref") != expected[1]:
            raise ValueError(f"M4_DONOR_PROVENANCE_INVALID canonical_id={canonical_id}")
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
    m3_evidence: PropBankEvidenceV1,
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
                donor_assertion="source_native_propbank_role",
                authored_mapping=f"{item.source_role_id}->{item.target_role_id} via {relation}",
                evidence_sentence=m3_evidence.sentence,
                ambiguity_disposition="resolved_by_exact_source_alignment",
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
        ambiguity_disposition="resolved_by_exact_source_alignment",
        unresolved=(),
        source_evidence=m3_evidence,
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
    m3_evidence: PropBankEvidenceV1 | None = None,
    m3_reconciliation_asset: str = "evaluation/propbank_examples/propbank_examples_reconciliation_v1.json",
    manifest_case_ids: tuple[str, ...] | None = None,
) -> AcquisitionMappingReportV1:
    """Produce the M4 report from one exact closure and selected M1 cases."""

    selected = tuple(cases)
    selected_ids = tuple(case.case_id for case in selected)
    if manifest_case_ids is None:
        manifest_case_ids = selected_ids
    if len(set(manifest_case_ids)) != len(manifest_case_ids) or set(selected_ids) != set(manifest_case_ids):
        raise ValueError("M4_SELECTION_MANIFEST_MISMATCH")
    required = {"purchase_to_acquisition_allowed", "acquisition_to_purchase_rejected", "buyer_seller_swap_rejected"}
    if set(manifest_case_ids) != required:
        raise ValueError("M4_REQUIRED_CASE_MISSING")
    if m3_evidence is None:
        m3_evidence = load_m3_evidence(Path(__file__).parents[2] / "evaluation/propbank_examples/propbank_examples_reconciliation_v1.json")
    if hashlib.sha256(Path(donor_mapping_asset).read_bytes()).hexdigest() != _DONOR_SHA256:
        raise ValueError("M4_DONOR_ASSET_DRIFT")
    mapping = _build_mapping(
        next(case for case in selected if case.case_id == "purchase_to_acquisition_allowed"),
        closure,
        donor_rows,
        m3_evidence,
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
        "m3_reconciliation_asset": m3_reconciliation_asset,
        "m3_projection_content_sha256": m3_evidence.projection_content_sha256,
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
        m3_reconciliation_asset=m3_reconciliation_asset,
        m3_projection_content_sha256=m3_evidence.projection_content_sha256,
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
        f"- M3 reconciliation: `{report.m3_reconciliation_asset}` (projection `{report.m3_projection_content_sha256}`)",
        f"- Source-native evidence: `{mapping.source_evidence.roleset_id}` — {mapping.source_evidence.sentence}",
        f"- Ambiguity disposition: `{mapping.ambiguity_disposition}`; unresolved: `{', '.join(mapping.unresolved) or 'none'}`",
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
